#!/usr/bin/env python3
"""
订单微服务 — FastAPI + SQLAlchemy + Redis
依赖: pip install fastapi uvicorn sqlalchemy asyncpg redis pydantic
启动: uvicorn main:app --reload
"""
import json
import os
import time
from datetime import datetime
from enum import Enum
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import (Column, DateTime, Float, Integer, String, Text,
                        select, func)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# ─── 配置 ─────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/orders")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class Base(DeclarativeBase):
    pass

class OrderModel(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    product = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(20), default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OrderOutbox(Base):
    __tablename__ = "order_outbox"
    id = Column(Integer, primary_key=True)
    aggregate_id = Column(Integer, nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    published = Column(Integer, default=0)

class OrderStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"

class OrderCreate(BaseModel):
    user_id: int = Field(gt=0)
    product: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0, le=9999)
    unit_price: float = Field(gt=0)

class OrderUpdate(BaseModel):
    product: Optional[str] = None
    quantity: Optional[int] = Field(None, gt=0)
    status: Optional[OrderStatus] = None

class OrderResponse(BaseModel):
    id: int
    user_id: int
    product: str
    quantity: int
    unit_price: float
    total_amount: float
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    page_size: int

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=20)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

redis = aioredis.from_url(REDIS_URL, decode_responses=True)

async def get_cache(key: str) -> Optional[dict]:
    data = await redis.get(key)
    return json.loads(data) if data else None

async def set_cache(key: str, value: dict, ttl: int = 60):
    await redis.setex(key, ttl, json.dumps(value, default=str))

async def invalidate_cache(pattern: str):
    keys = []
    async for key in redis.scan_iter(match=pattern):
        keys.append(key)
    if keys:
        await redis.delete(*keys)

app = FastAPI(
    title="订单微服务",
    description="高性能订单 CRUD 微服务",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{(time.perf_counter() - start)*1000:.1f}ms"
    return response

async def get_order_or_404(order_id: int, db: AsyncSession = Depends(get_db)) -> OrderModel:
    result = await db.execute(select(OrderModel).where(OrderModel.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return order

@app.post("/api/orders", response_model=OrderResponse, status_code=201)
async def create_order(req: OrderCreate, db: AsyncSession = Depends(get_db)):
    total = req.quantity * req.unit_price
    order = OrderModel(
        user_id=req.user_id, product=req.product,
        quantity=req.quantity, unit_price=req.unit_price, total_amount=total,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)
    outbox = OrderOutbox(
        aggregate_id=order.id, event_type="order.created",
        payload=json.dumps({"order_id": order.id, "user_id": order.user_id, "total_amount": order.total_amount}),
    )
    db.add(outbox)
    await invalidate_cache("orders:list:*")
    return order

@app.get("/api/orders/{order_id}", response_model=OrderResponse)
async def get_order(order: OrderModel = Depends(get_order_or_404)):
    cache_key = f"order:{order.id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached
    await set_cache(cache_key, OrderResponse.model_validate(order).model_dump(), ttl=30)
    return order

@app.get("/api/orders", response_model=OrderListResponse)
async def list_orders(
    page: int = 1, page_size: int = 20, status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"orders:list:{page}:{page_size}:{status}"
    cached = await get_cache(cache_key)
    if cached:
        return cached
    query = select(OrderModel)
    count_query = select(func.count(OrderModel.id))
    if status:
        query = query.where(OrderModel.status == status)
        count_query = count_query.where(OrderModel.status == status)
    total = (await db.execute(count_query)).scalar()
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(OrderModel.id.desc()).limit(page_size).offset(offset)
    )
    orders = result.scalars().all()
    resp = OrderListResponse(
        items=[OrderResponse.model_validate(o) for o in orders],
        total=total, page=page, page_size=page_size,
    )
    await set_cache(cache_key, resp.model_dump(), ttl=30)
    return resp

@app.patch("/api/orders/{order_id}", response_model=OrderResponse)
async def update_order(
    req: OrderUpdate,
    order: OrderModel = Depends(get_order_or_404),
    db: AsyncSession = Depends(get_db),
):
    if req.product is not None:
        order.product = req.product
    if req.quantity is not None:
        order.quantity = req.quantity
        order.total_amount = order.quantity * order.unit_price
    if req.status is not None:
        order.status = req.status.value
    await db.flush()
    await db.refresh(order)
    await invalidate_cache(f"order:{order.id}")
    await invalidate_cache("orders:list:*")
    return order

@app.delete("/api/orders/{order_id}", status_code=204)
async def delete_order(
    order: OrderModel = Depends(get_order_or_404),
    db: AsyncSession = Depends(get_db),
):
    await db.delete(order)
    await invalidate_cache(f"order:{order.id}")
    await invalidate_cache("orders:list:*")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.on_event("startup")
async def startup():
    await init_db()
    print("🚀 Order Service started")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
