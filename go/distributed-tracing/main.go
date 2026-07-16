// Package main — 分布式链路追踪 (OpenTelemetry + Jaeger)
// 演示 Span 创建、上下文传播、HTTP 中间件集成
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.17.0"
	"go.opentelemetry.io/otel/trace"
)

// ─── Tracer 初始化 ────────────────────────────────────────

var tracer trace.Tracer

func initTracer(ctx context.Context) (*sdktrace.TracerProvider, error) {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = "localhost:4318"
	}

	exporter, err := otlptracehttp.New(ctx,
		otlptracehttp.WithEndpoint(endpoint),
		otlptracehttp.WithInsecure(),
	)
	if err != nil {
		return nil, fmt.Errorf("创建 OTLP exporter 失败: %w", err)
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceName("distributed-tracing-demo"),
			semconv.ServiceVersion("1.0.0"),
		)),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)

	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	tracer = tp.Tracer("distributed-tracing-demo")
	return tp, nil
}

// ─── 模拟微服务 ───────────────────────────────────────────

// 模拟数据库查询
func queryDatabase(ctx context.Context, query string) (string, error) {
	ctx, span := tracer.Start(ctx, "db.query",
		trace.WithAttributes(
			attribute.String("db.system", "postgresql"),
			attribute.String("db.operation", "SELECT"),
			attribute.String("db.statement", query),
		))
	defer span.End()

	// 模拟查询延迟
	time.Sleep(30 * time.Millisecond)

	span.SetAttributes(attribute.Int("db.rows_affected", 1))
	return `{"id": 1, "name": "Alice", "email": "alice@example.com"}`, nil
}

// 模拟缓存查询
func queryCache(ctx context.Context, key string) (string, bool) {
	ctx, span := tracer.Start(ctx, "cache.get",
		trace.WithAttributes(
			attribute.String("cache.system", "redis"),
			attribute.String("cache.key", key),
		))
	defer span.End()

	time.Sleep(5 * time.Millisecond)

	// 模拟缓存未命中
	span.SetAttributes(attribute.Bool("cache.hit", false))
	return "", false
}

// 模拟外部 API 调用
func callExternalAPI(ctx context.Context, url string) (string, error) {
	ctx, span := tracer.Start(ctx, "http.client",
		trace.WithAttributes(
			attribute.String("http.method", "GET"),
			attribute.String("http.url", url),
		))
	defer span.End()

	time.Sleep(50 * time.Millisecond)

	// 模拟错误
	if url == "" {
		span.SetStatus(codes.Error, "invalid URL")
		return "", fmt.Errorf("invalid URL")
	}

	span.SetAttributes(attribute.Int("http.status_code", 200))
	return `{"status": "ok"}`, nil
}

// ─── HTTP 中间件 ──────────────────────────────────────────

func tracingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx := otel.GetTextMapPropagator().Extract(r.Context(), propagation.HeaderCarrier(r.Header))

		ctx, span := tracer.Start(ctx, r.Method+" "+r.URL.Path,
			trace.WithSpanKind(trace.SpanKindServer),
			trace.WithAttributes(
				attribute.String("http.method", r.Method),
				attribute.String("http.url", r.URL.String()),
				attribute.String("http.user_agent", r.UserAgent()),
			))
		defer span.End()

		// 注入 trace ID 到响应头
		spanCtx := span.SpanContext()
		if spanCtx.HasTraceID() {
			w.Header().Set("X-Trace-ID", spanCtx.TraceID().String())
		}

		next.ServeHTTP(w, r.WithContext(ctx))

		span.SetAttributes(attribute.Int("http.status_code", http.StatusOK))
	})
}

// ─── 业务处理 ─────────────────────────────────────────────

func handleGetUser(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := r.URL.Query().Get("id")
	if userID == "" {
		userID = "1"
	}

	// Span 1: 缓存查询
	if cached, hit := queryCache(ctx, "user:"+userID); hit {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(cached))
		return
	}

	// Span 2: 数据库查询
	result, err := queryDatabase(ctx, "SELECT * FROM users WHERE id = "+userID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	// Span 3: 外部 API 调用（如通知服务）
	callExternalAPI(ctx, "http://notification-service/api/notify")

	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(result))
}

func handleCreateOrder(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// 模拟复杂的业务链路
	ctx, span := tracer.Start(ctx, "order.create")
	defer span.End()

	// 子 Span 1: 库存检查
	func() {
		_, childSpan := tracer.Start(ctx, "inventory.check")
		defer childSpan.End()
		time.Sleep(20 * time.Millisecond)
		childSpan.SetAttributes(attribute.Bool("inventory.available", true))
	}()

	// 子 Span 2: 支付处理
	func() {
		_, childSpan := tracer.Start(ctx, "payment.process")
		defer childSpan.End()
		time.Sleep(40 * time.Millisecond)
	}()

	// 子 Span 3: 发送消息
	func() {
		_, childSpan := tracer.Start(ctx, "message.send")
		defer childSpan.End()
		time.Sleep(10 * time.Millisecond)
	}()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"order_id": "ORD-2024-001",
		"status":   "created",
	})
}

// ─── 健康检查 ─────────────────────────────────────────────

func handleHealth(w http.ResponseWriter, r *http.Request) {
	_, span := tracer.Start(r.Context(), "health.check")
	defer span.End()

	writeJSON(w, http.StatusOK, map[string]string{
		"status": "healthy",
		"tracer": "opentelemetry",
	})
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

// ─── 主入口 ───────────────────────────────────────────────

func main() {
	ctx := context.Background()

	tp, err := initTracer(ctx)
	if err != nil {
		log.Printf("⚠️  Tracer 初始化失败（将以无追踪模式运行）: %v", err)
	} else {
		defer func() {
			if err := tp.Shutdown(ctx); err != nil {
				log.Printf("Tracer 关闭错误: %v", err)
			}
		}()
		log.Println("✅ OpenTelemetry Tracer 已初始化")
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/api/user", handleGetUser)
	mux.HandleFunc("/api/order", handleCreateOrder)
	mux.HandleFunc("/health", handleHealth)

	var handler http.Handler = mux
	handler = tracingMiddleware(handler)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	fmt.Println(`
╔══════════════════════════════════════════╗
║   🔍 分布式链路追踪 Demo                 ║
║   OpenTelemetry + OTLP + Jaeger         ║
╚══════════════════════════════════════════╝`)

	log.Printf("🚀 服务启动: http://localhost:%s", port)
	log.Printf("📋 端点: GET /api/user, POST /api/order")

	if err := http.ListenAndServe(":"+port, handler); err != nil {
		log.Fatalf("启动失败: %v", err)
	}
}
