#!/usr/bin/env python3
"""
多轮对话智能客服系统
依赖: pip install langchain langchain-openai fastapi uvicorn websockets redis
"""
import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import AsyncIterator, Optional

import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CSBot")

# ─── 配置 ─────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-xxx")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
MAX_HISTORY = 10
SESSION_TTL = 3600  # 会话过期 1 小时

# ─── 意图枚举 ─────────────────────────────────────────────
class Intent(str, Enum):
    GREETING = "greeting"           # 问候
    PRODUCT_INQUIRY = "product_inquiry"  # 产品咨询
    ORDER_STATUS = "order_status"   # 订单查询
    RETURN_REFUND = "return_refund" # 退换货
    COMPLAINT = "complaint"         # 投诉
    TECHNICAL_SUPPORT = "tech_support"  # 技术支持
    HUMAN_SERVICE = "human_service" # 转人工
    UNKNOWN = "unknown"

# ─── 数据模型 ─────────────────────────────────────────────
@dataclass
class SlotValues:
    """槽位填充"""
    product_name: Optional[str] = None
    order_id: Optional[str] = None
    issue_category: Optional[str] = None
    contact_phone: Optional[str] = None
    urgency: Optional[str] = None

@dataclass
class ConversationState:
    session_id: str
    user_id: str = "anonymous"
    intent: Intent = Intent.UNKNOWN
    slots: SlotValues = field(default_factory=SlotValues)
    turn_count: int = 0
    escalated: bool = False
    history: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

# ─── 意图分类器 ───────────────────────────────────────────
INTENT_PROMPT = """你是一个电商客服的意图分类器。分析用户消息，输出 JSON 格式：
{
  "intent": "greeting|product_inquiry|order_status|return_refund|complaint|tech_support|human_service|unknown",
  "slots": {"product_name": "string or null", "order_id": "string or null", "issue_category": "string or null", "contact_phone": "string or null", "urgency": "low|medium|high"}
}

用户消息: {user_message}
当前意图: {current_intent}
已有信息: {current_slots}"""

class IntentClassifier:
    """基于 LLM 的意图识别 + 槽位填充"""

    SYSTEM_PROMPT = """你是一个专业的电商客服意图分类器和信息提取器。
规则:
1. order_status: 用户询问订单状态、物流
2. return_refund: 退换货、退款申请
3. complaint: 投诉、不满
4. tech_support: 产品使用问题、技术问题
5. human_service: 明确要求转人工
6. product_inquiry: 询问产品信息、价格
7. greeting: 问候、闲聊
8. unknown: 无法分类
提取 slots 时只填明确提到的信息，不要臆测。"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    async def classify(self, message: str, state: ConversationState) -> tuple[Intent, dict]:
        slots_json = json.dumps(state.slots.__dict__, ensure_ascii=False, default=str)
        prompt = INTENT_PROMPT.format(
            user_message=message,
            current_intent=state.intent.value,
            current_slots=slots_json,
        )
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            result = json.loads(
                re.search(r'\{.*\}', response.content, re.DOTALL).group()
            )
            intent = Intent(result.get("intent", "unknown"))
            slots = result.get("slots", {})
            return intent, slots
        except Exception as e:
            logger.warning(f"意图分类失败: {e}")
            return Intent.UNKNOWN, {}

# ─── 知识库检索器 ─────────────────────────────────────────
class KnowledgeRetriever:
    """简易关键词 + FAQ 匹配检索（完整 RAG 见 [[AI-实战-RAG知识库]]）"""

    FAQ_DB = [
        {"q": "如何查询订单", "a": "您可以在「我的订单」中查看所有订单。输入订单号我可以帮您查询详情。"},
        {"q": "退货流程", "a": "在「我的订单」中选择要退货的商品，点击「申请退货」。7天无理由退货，15天换货。"},
        {"q": "退款多久到账", "a": "退货签收后 1-3 个工作日内退款到原支付账户。如超时请联系客服。"},
        {"q": "发货时间", "a": "现货商品下单后 24 小时内发货，预售商品按页面标注时间发货。"},
        {"q": "运费", "a": "满 99 元包邮。不满 99 元，普通快递 ¥6，加急 ¥12。"},
        {"q": "优惠券怎么用", "a": "结算时自动抵扣可用的优惠券。在「我的优惠券」查看所有券。"},
        {"q": "账号问题", "a": "如需找回密码，点击登录页「忘记密码」。其他账号问题可转接人工客服。"},
        {"q": "如何联系人工客服", "a": "输入「转人工」或在工作时间 9:00-21:00 拨打 400-xxx-xxxx。"},
    ]

    @classmethod
    def search(cls, query: str, top_k: int = 3) -> list[dict]:
        """简单关键词匹配"""
        query_lower = query.lower()
        scored = []
        for faq in cls.FAQ_DB:
            q_lower = faq["q"].lower()
            # 简单的 jaccard 相似度
            q_words = set(q_lower)
            query_words = set(query_lower)
            intersection = q_words & query_words
            union = q_words | query_words
            score = len(intersection) / len(union) if union else 0
            # 完全包含加分
            if query_lower in q_lower or q_lower in query_lower:
                score += 0.5
            scored.append((score, faq))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [faq for _, faq in scored[:top_k] if _ > 0.1]

# ─── 对话管理器 ───────────────────────────────────────────
class DialogueManager:
    """核心对话引擎"""

    SYSTEM_TEMPLATE = """你是{company}的智能客服助手「{bot_name}」。

## 身份
- 友好、专业、有耐心
- 不知道的如实说明，不编造信息

## 当前场景
- 用户意图: {intent}
- 已知信息: {slots}

## 知识库参考
{knowledge}

## 规则
- 回复简洁（不超过 200 字）
- 需要收集信息时，一次只问一个问题
- 遇到投诉，先安抚情绪再解决问题
- 如果用户明确要求转人工，引导说明转接流程
- 订单号格式: 字母数字组合 12-16 位"""

    def __init__(self, llm: ChatOpenAI, redis_client: redis.Redis):
        self.llm = llm
        self.redis = redis_client
        self.classifier = IntentClassifier(llm)
        self.retriever = KnowledgeRetriever()
        self.company = os.getenv("COMPANY_NAME", "优品电商")
        self.bot_name = os.getenv("BOT_NAME", "小优")

    async def load_state(self, session_id: str) -> ConversationState:
        """从 Redis 加载会话状态"""
        key = f"cs:session:{session_id}"
        data = await self.redis.get(key)
        if data:
            state_dict = json.loads(data)
            state = ConversationState(session_id=session_id)
            state.user_id = state_dict.get("user_id", "anonymous")
            state.intent = Intent(state_dict.get("intent", "unknown"))
            state.slots = SlotValues(**state_dict.get("slots", {}))
            state.turn_count = state_dict.get("turn_count", 0)
            state.escalated = state_dict.get("escalated", False)
            state.history = state_dict.get("history", [])
            return state
        return ConversationState(session_id=session_id)

    async def save_state(self, state: ConversationState):
        key = f"cs:session:{state.session_id}"
        await self.redis.setex(key, SESSION_TTL, json.dumps({
            "user_id": state.user_id,
            "intent": state.intent.value,
            "slots": state.slots.__dict__,
            "turn_count": state.turn_count,
            "escalated": state.escalated,
            "history": state.history[-MAX_HISTORY:],
        }, ensure_ascii=False, default=str))

    async def chat(self, session_id: str, user_message: str) -> str:
        """主对话入口"""
        state = await self.load_state(session_id)
        state.turn_count += 1

        # 1. 意图识别
        intent, slots = await self.classifier.classify(user_message, state)
        state.intent = intent
        if slots:
            for k, v in slots.items():
                if v and hasattr(state.slots, k):
                    setattr(state.slots, k, v)

        # 2. 意图处理
        if intent == Intent.HUMAN_SERVICE:
            state.escalated = True
            response = "正在为您转接人工客服，请稍候...\n预计等待时间: 2 分钟。如需留言，请直接告诉我。"
        elif intent == Intent.ORDER_STATUS and state.slots.order_id:
            response = f"正在查询订单 {state.slots.order_id}...\n（演示回复）订单状态: 运输中，预计明天送达。"
        else:
            # 3. 知识检索
            faqs = self.retriever.search(user_message)
            knowledge = "\n".join(f"Q: {f['q']}\nA: {f['a']}" for f in faqs[:3]) if faqs else "暂无相关FAQ"

            # 4. LLM 生成回复
            prompt = self.SYSTEM_TEMPLATE.format(
                company=self.company,
                bot_name=self.bot_name,
                intent=intent.value,
                slots=json.dumps(state.slots.__dict__, ensure_ascii=False, default=str),
                knowledge=knowledge,
            )

            messages = [SystemMessage(content=prompt)]
            # 添加历史
            for h in state.history[-6:]:
                if h["role"] == "user":
                    messages.append(HumanMessage(content=h["content"]))
                else:
                    messages.append(AIMessage(content=h["content"]))
            messages.append(HumanMessage(content=user_message))

            response = await self.llm.ainvoke(messages)
            response = response.content

        # 5. 更新历史并保存
        state.history.append({"role": "user", "content": user_message})
        state.history.append({"role": "assistant", "content": response})
        await self.save_state(state)

        return response

    async def summarize(self, session_id: str) -> str:
        """对话摘要（用于转人工时）"""
        state = await self.load_state(session_id)
        history_text = "\n".join(
            f"{h['role']}: {h['content']}" for h in state.history
        )
        prompt = f"请用 100 字以内总结以下客服对话:\n{history_text}\n\n摘要:"
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        return response.content

# ─── FastAPI 服务 ─────────────────────────────────────────

# 全局初始化
redis_client: Optional[redis.Redis] = None
dialogue_manager: Optional[DialogueManager] = None

# 使用 lifespan 替代已弃用的 on_event

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    global redis_client, dialogue_manager
    redis_client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    llm = ChatOpenAI(
        model=MODEL_NAME,
        api_key=OPENAI_API_KEY,
        temperature=0.7,
        max_tokens=512,
    )
    dialogue_manager = DialogueManager(llm, redis_client)
    logger.info("客服系统启动完成")
    yield
    # shutdown
    if redis_client:
        await redis_client.close()

app = FastAPI(title="智能客服 Bot", lifespan=lifespan)

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.active[session_id] = ws

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)

    async def send(self, session_id: str, message: dict):
        ws = self.active.get(session_id)
        if ws:
            await ws.send_json(message)

ws_manager = ConnectionManager()

@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    await ws_manager.connect(session_id, websocket)

    # 发送欢迎消息
    welcome = "您好！我是优品电商智能客服小优 😊\n请问有什么可以帮您？"
    await websocket.send_json({
        "type": "message",
        "role": "assistant",
        "content": welcome,
        "timestamp": datetime.now().isoformat(),
    })

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            user_content = msg.get("content", "")

            if not user_content.strip():
                continue

            # 回显用户消息
            await websocket.send_json({
                "type": "message",
                "role": "user",
                "content": user_content,
                "timestamp": datetime.now().isoformat(),
            })

            # 生成回复
            response = await dialogue_manager.chat(session_id, user_content)

            await websocket.send_json({
                "type": "message",
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat(),
            })

    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开: {session_id}")
    finally:
        ws_manager.disconnect(session_id)

# HTTP API
class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    success: bool
    reply: str
    intent: str = ""
    escalated: bool = False

@app.post("/api/chat", response_model=ChatResponse)
async def http_chat(req: ChatRequest):
    if not dialogue_manager:
        raise HTTPException(503, "服务未就绪")
    reply = await dialogue_manager.chat(req.session_id, req.message)
    state = await dialogue_manager.load_state(req.session_id)
    return ChatResponse(
        success=True,
        reply=reply,
        intent=state.intent.value,
        escalated=state.escalated,
    )

@app.get("/api/summary/{session_id}")
async def get_summary(session_id: str):
    if not dialogue_manager:
        raise HTTPException(503, "服务未就绪")
    summary = await dialogue_manager.summarize(session_id)
    return {"success": True, "summary": summary}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/")
async def index():
    return HTMLResponse("""
<!DOCTYPE html><html><head><meta charset="utf-8"><title>智能客服</title></head>
<body><h1>智能客服 Bot 已运行</h1><p>WebSocket: ws://host/ws/chat/{session_id}</p></body></html>
""")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
