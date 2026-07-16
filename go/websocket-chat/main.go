// Package main — WebSocket 实时聊天室 (gorilla/websocket)
// 支持多房间、在线列表、消息广播
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// ─── 消息类型 ─────────────────────────────────────────────

type Message struct {
	Type      string `json:"type"`                // join, leave, message, system
	Username  string `json:"username,omitempty"`
	Content   string `json:"content,omitempty"`
	Room      string `json:"room,omitempty"`
	Timestamp int64  `json:"timestamp"`
	Online    int    `json:"online,omitempty"`
}

// ─── 客户端 ───────────────────────────────────────────────

type Client struct {
	conn     *websocket.Conn
	username string
	room     string
	send     chan []byte
}

// ─── 聊天室 ───────────────────────────────────────────────

type ChatRoom struct {
	clients map[*Client]bool
	mu      sync.RWMutex
}

func NewChatRoom() *ChatRoom {
	return &ChatRoom{clients: make(map[*Client]bool)}
}

func (r *ChatRoom) Join(c *Client) {
	r.mu.Lock()
	r.clients[c] = true
	r.mu.Unlock()

	r.Broadcast(Message{
		Type:      "join",
		Username:  c.username,
		Timestamp: time.Now().Unix(),
		Online:    r.Len(),
	})
}

func (r *ChatRoom) Leave(c *Client) {
	r.mu.Lock()
	delete(r.clients, c)
	r.mu.Unlock()

	r.Broadcast(Message{
		Type:      "leave",
		Username:  c.username,
		Timestamp: time.Now().Unix(),
		Online:    r.Len(),
	})
}

func (r *ChatRoom) Broadcast(msg Message) {
	data, _ := json.Marshal(msg)
	r.mu.RLock()
	defer r.mu.RUnlock()
	for c := range r.clients {
		select {
		case c.send <- data:
		default:
			go func(c *Client) {
				r.Leave(c)
				c.conn.Close()
			}(c)
		}
	}
}

func (r *ChatRoom) Len() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.clients)
}

// ─── 聊天服务器 ───────────────────────────────────────────

type ChatServer struct {
	rooms  map[string]*ChatRoom
	mu     sync.RWMutex
}

func NewChatServer() *ChatServer {
	return &ChatServer{rooms: make(map[string]*ChatRoom)}
}

func (s *ChatServer) GetOrCreateRoom(name string) *ChatRoom {
	s.mu.Lock()
	defer s.mu.Unlock()
	if room, ok := s.rooms[name]; ok {
		return room
	}
	room := NewChatRoom()
	s.rooms[name] = room
	return room
}

// ─── WebSocket 升级器 ─────────────────────────────────────

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true // 开发环境允许所有来源
	},
}

// ─── WebSocket 处理 ───────────────────────────────────────

func (s *ChatServer) handleWS(w http.ResponseWriter, r *http.Request) {
	username := r.URL.Query().Get("username")
	room := r.URL.Query().Get("room")

	if username == "" {
		username = "匿名用户"
	}
	if room == "" {
		room = "公共大厅"
	}

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket 升级失败: %v", err)
		return
	}

	client := &Client{
		conn:     conn,
		username: username,
		room:     room,
		send:     make(chan []byte, 64),
	}

	chatRoom := s.GetOrCreateRoom(room)
	chatRoom.Join(client)

	// 发送欢迎消息
	welcome, _ := json.Marshal(Message{
		Type:      "system",
		Content:   "欢迎 " + username + " 加入 " + room + "！",
		Timestamp: time.Now().Unix(),
	})
	client.send <- welcome

	// 写协程
	go client.writePump()
	// 读协程
	client.readPump(chatRoom)
}

func (c *Client) readPump(room *ChatRoom) {
	defer func() {
		room.Leave(c)
		c.conn.Close()
	}()

	c.conn.SetReadLimit(4096)
	c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	for {
		_, msgBytes, err := c.conn.ReadMessage()
		if err != nil {
			break
		}

		room.Broadcast(Message{
			Type:      "message",
			Username:  c.username,
			Content:   string(msgBytes),
			Timestamp: time.Now().Unix(),
		})
	}
}

func (c *Client) writePump() {
	ticker := time.NewTicker(30 * time.Second)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case msg, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			if err := c.conn.WriteMessage(websocket.TextMessage, msg); err != nil {
				return
			}
		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// ─── 静态页面 ─────────────────────────────────────────────

func homePage(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "index.html")
}

// ─── 主入口 ───────────────────────────────────────────────

func main() {
	server := NewChatServer()

	http.HandleFunc("/ws", server.handleWS)
	http.HandleFunc("/", homePage)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("🚀 WebSocket 聊天室启动: http://localhost:%s", port)
	log.Printf("💬 连接示例: ws://localhost:%s/ws?username=Alice&room=公共大厅", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("服务器启动失败: %v", err)
	}
}
