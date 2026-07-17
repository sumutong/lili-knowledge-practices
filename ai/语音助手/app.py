#!/usr/bin/env python3
"""
全栈语音助手后端
依赖: pip install fastapi uvicorn openai-whisper coqui-tts pydub torch
      pip install python-multipart websockets langchain-openai
"""
import asyncio
import io
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import uvicorn
import whisper
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VoiceAssistant")

# ─── 配置 ─────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-xxx")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")   # tiny/base/small/medium/large
TTS_MODEL = os.getenv("TTS_MODEL", "tts_models/zh-CN/baker/tacotron2-DDC")  # Coqui Chinese
USE_GPU = torch.cuda.is_available()
DEVICE = "cuda" if USE_GPU else "cpu"

# ─── 初始化模型 ───────────────────────────────────────────
logger.info(f"Loading Whisper model '{WHISPER_MODEL}' on {DEVICE}...")
whisper_model = whisper.load_model(WHISPER_MODEL, device=DEVICE)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ─── Coqui TTS 模型（懒加载，首次使用加载） ────────────────
tts_model = None

def get_tts():
    global tts_model
    if tts_model is None:
        from TTS.api import TTS
        logger.info(f"Loading TTS model '{TTS_MODEL}' on {DEVICE}...")
        tts_model = TTS(model_name=TTS_MODEL).to(DEVICE)
    return tts_model

# ─── FastAPI ──────────────────────────────────────────────
app = FastAPI(title="Voice Assistant API")

# 多轮对话存储（生产环境应使用 Redis）
conversations: dict[str, list[dict]] = {}

# ─── 系统提示 ─────────────────────────────────────────────
SYSTEM_PROMPT = """你是一个友好的语音助手「小语」。你的回答：
1. 简洁明了，适合语音播报（每句话不超过50字）
2. 语气自然亲切，像朋友聊天
3. 如果用户的问题涉及实时信息，诚实说明无法获取
4. 使用口语化表达，避免书面语
"""

# ─── 语音识别 API ────────────────────────────────────────
class TranscribeResponse(BaseModel):
    text: str
    language: str
    duration: float
    segments: list[dict]

@app.post("/api/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = None,  # 自动检测或指定 'zh'/'en'
):
    """语音识别 - OpenAI Whisper"""
    audio_bytes = await file.read()
    logger.info(f"Received audio: {len(audio_bytes)} bytes, language={language}")

    # 保存临时文件
    tmp_path = f"/tmp/audio_{uuid.uuid4()}.wav"
    with open(tmp_path, "wb") as f:
        f.write(audio_bytes)

    try:
        # 转录
        options = {"task": "transcribe"}
        if language:
            options["language"] = language

        result = whisper_model.transcribe(tmp_path, **options)

        return TranscribeResponse(
            text=result["text"].strip(),
            language=result.get("language", language or "unknown"),
            duration=result.get("duration", 0),
            segments=[
                {"start": s["start"], "end": s["end"], "text": s["text"]}
                for s in result.get("segments", [])
            ],
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

# ─── 对话 API ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: str
    message: str
    stream: bool = False

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    audio_url: Optional[str] = None

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """对话生成 - LLM"""
    session_id = req.session_id or str(uuid.uuid4())

    # 获取/初始化对话历史
    if session_id not in conversations:
        conversations[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    history = conversations[session_id]
    history.append({"role": "user", "content": req.message})

    # 保留最近 20 轮对话（控制 Token 消耗）
    if len(history) > 21:  # system + 20轮
        history = [history[0]] + history[-20:]

    # LLM 生成
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=history,
        temperature=0.7,
        max_tokens=300,
    )

    reply = response.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": reply})
    conversations[session_id] = history

    return ChatResponse(session_id=session_id, reply=reply)

# ─── TTS 语音合成 API ─────────────────────────────────────
@app.post("/api/tts")
async def text_to_speech(text: str, speaker: str = "default"):
    """文本转语音 - Coqui TTS"""
    try:
        tts = get_tts()
        wav = tts.tts(text=text, speaker=speaker)

        # 将 numpy array 转为 bytes (WAV)
        wav_int16 = (np.array(wav) * 32767).astype(np.int16)
        buf = io.BytesIO()
        audio_segment = AudioSegment(
            wav_int16.tobytes(),
            frame_width=2,
            frame_rate=22050,
            channels=1,
        )
        audio_segment.export(buf, format="wav")
        buf.seek(0)

        return StreamingResponse(buf, media_type="audio/wav")
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(500, f"TTS 生成失败: {e}")

# ─── 流式 TTS WebSocket ───────────────────────────────────
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """实时语音对话 WebSocket"""
    await websocket.accept()
    session_id = str(uuid.uuid4())
    conversations[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    try:
        while True:
            # 接收文本消息
            data = await websocket.receive_text()
            message = json.loads(data)
            user_text = message.get("text", "")

            if not user_text:
                continue

            conversations[session_id].append({"role": "user", "content": user_text})

            # 流式 LLM 回复
            stream = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=conversations[session_id],
                temperature=0.7,
                max_tokens=300,
                stream=True,
            )

            full_reply = ""
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_reply += delta
                    # 逐句发送（遇到句号、问号等断句）
                    if any(delta.endswith(p) for p in "。！？.!?\n"):
                        await websocket.send_json({
                            "type": "text_delta",
                            "text": full_reply,
                        })

            # 发送完整回复
            conversations[session_id].append({"role": "assistant", "content": full_reply})
            await websocket.send_json({"type": "text_done", "text": full_reply})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
