"""WebSocket-based real-time voice interaction (no webrtcvad)."""

import asyncio
import json
import audioop

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.asr_service import transcribe
from services.llm_service import full_reply
from services.tts_service import synthesize_stream, SAMPLE_RATE as TTS_SAMPLE_RATE

router = APIRouter(prefix="/ws")

CLIENT_SAMPLE_RATE = 48000   # 如果前端直接发 48k PCM，这里保持 48k
ASR_SAMPLE_RATE = 16000      # 你的 ASR（FunASR/Whisper）通常用 16k


async def stream_tts(websocket: WebSocket, text: str):
    """把 TTS 的 PCM 以固定帧长（20ms / 960 samples@48k）推给前端播放。"""
    buffer = bytearray()
    FRAME_SAMPLES = int(TTS_SAMPLE_RATE * 0.02)  # 20ms
    FRAME_BYTES = FRAME_SAMPLES * 2              # int16 mono

    async for chunk in synthesize_stream(text):  # 这里假设返回的就是 int16 PCM @ TTS_SAMPLE_RATE
        buffer.extend(chunk)
        while len(buffer) >= FRAME_BYTES:
            frame = bytes(buffer[:FRAME_BYTES])
            buffer = buffer[FRAME_BYTES:]
            await websocket.send_bytes(frame)

    if buffer:
        pad = FRAME_BYTES - len(buffer)
        await websocket.send_bytes(bytes(buffer) + b"\x00" * pad)

    # 发送一个空包，告知客户端音频播放结束（可选）
    await websocket.send_bytes(b"")


@router.websocket("/audio")
async def audio_endpoint(websocket: WebSocket):
    """
    纯 WebSocket 方案：
    - 二进制帧：原始 PCM（16-bit、mono、采样率见 CLIENT_SAMPLE_RATE）
    - 文本帧：控制消息（例如 {"type": "flush"} 表示一句结束，立刻推 ASR + LLM + TTS）
    """
    await websocket.accept()

    audio_buffer = bytearray()

    try:
        while True:
            msg = await websocket.receive()  # 会返回 {"type":"websocket.receive","text" or "bytes":...}

            if "bytes" in msg:
                data: bytes = msg["bytes"]

                # 若客户端发 48k，需要重采样到 16k 给 ASR
                if CLIENT_SAMPLE_RATE != ASR_SAMPLE_RATE:
                    data, _ = audioop.ratecv(
                        data, 2, 1,
                        CLIENT_SAMPLE_RATE, ASR_SAMPLE_RATE,
                        None
                    )
                audio_buffer.extend(data)

            elif "text" in msg:
                try:
                    payload = json.loads(msg["text"])
                except Exception:
                    # 非 JSON 的简单控制消息也可按需处理
                    payload = {"type": msg["text"]}

                # 统一用 type 字段控制
                if payload.get("type") == "flush":
                    # 一句结束，立即跑 ASR + LLM + TTS
                    if audio_buffer:
                        transcript = await transcribe(bytes(audio_buffer))
                        audio_buffer.clear()

                        if transcript.strip():
                            await websocket.send_text(json.dumps({"type": "transcript", "data": transcript}))

                            reply_text = await full_reply(transcript)
                            await websocket.send_text(json.dumps({"type": "text", "data": reply_text}))

                            # 异步推流 TTS，让 WS 主循环不被阻塞
                            asyncio.create_task(stream_tts(websocket, reply_text))

                elif payload.get("type") in {"close", "stop"}:
                    # 客户端主动通知关闭
                    break

                # 你也可以扩展更多指令类型，如 "reset" 等

    except WebSocketDisconnect:
        pass
