"""WebSocket-based real-time voice interaction with built-in VAD."""

import asyncio
import json
import audioop
import time
import webrtcvad

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.asr_service import transcribe
from services.llm_service import full_reply
from services.tts_service import synthesize_stream, SAMPLE_RATE as TTS_SAMPLE_RATE
from services.buffers import audio_buffer, video_frames

router = APIRouter(prefix="/ws")

CLIENT_SAMPLE_RATE = 48000   # 如果前端直接发 48k PCM，这里保持 48k
ASR_SAMPLE_RATE = 16000      # 你的 ASR（FunASR/Whisper）通常用 16k
VAD_FRAME_MS = 20
FRAME_BYTES = int(ASR_SAMPLE_RATE * VAD_FRAME_MS / 1000) * 2
SILENCE_LIMIT = int(0.8 / (VAD_FRAME_MS / 1000))
vad = webrtcvad.Vad(3)

async def stream_tts(websocket: WebSocket, text: str):
    """把 TTS PCM 重采样成 48k 裸 PCM 再实时推给前端"""
    resample_state = None
    async for chunk in synthesize_stream(text):  # int16 mono @ TTS_SAMPLE_RATE
        if TTS_SAMPLE_RATE != CLIENT_SAMPLE_RATE:
            chunk, resample_state = audioop.ratecv(
                chunk,               # 16-bit
                2,                   # width=2 bytes
                1,                   # mono
                TTS_SAMPLE_RATE,
                CLIENT_SAMPLE_RATE,  # -> 48000
                resample_state
            )
        await websocket.send_bytes(chunk)

    # 结束标记
    await websocket.send_bytes(b"")



@router.websocket("/audio")
async def audio_endpoint(websocket: WebSocket):
    """
    纯 WebSocket 方案：
    - 二进制帧：原始 PCM（16-bit、mono、采样率见 CLIENT_SAMPLE_RATE）
    - 文本帧：控制消息（例如 {"type": "flush"} 表示一句结束，立刻推 ASR + LLM + TTS）
    """
    await websocket.accept()

    vad_buffer = bytearray()
    silence = 0
    listening = True
    last_speech = time.monotonic()

    try:
        while True:
            msg = await websocket.receive()  # {"type":"websocket.receive","text" or "bytes":...}

            if "bytes" in msg:
                data: bytes = msg["bytes"]

                if not listening:
                    continue

                # 若客户端发 48k，需要重采样到 16k 给 ASR
                if CLIENT_SAMPLE_RATE != ASR_SAMPLE_RATE:
                    data, _ = audioop.ratecv(
                        data, 2, 1,
                        CLIENT_SAMPLE_RATE, ASR_SAMPLE_RATE,
                        None
                    )
                audio_buffer.extend(data)
                vad_buffer.extend(data)

                while len(vad_buffer) >= FRAME_BYTES:
                    frame = bytes(vad_buffer[:FRAME_BYTES])
                    vad_buffer = vad_buffer[FRAME_BYTES:]
                    if vad.is_speech(frame, ASR_SAMPLE_RATE):
                        silence = 0
                        last_speech = time.monotonic()
                    else:
                        silence += 1

                    if silence > SILENCE_LIMIT:
                        if audio_buffer:
                            transcript = await transcribe(bytes(audio_buffer))
                            audio_buffer.clear()
                            video_frames.clear()

                            if transcript.strip():
                                await websocket.send_text(json.dumps({"type": "transcript", "data": transcript}))

                                reply_text = await full_reply(transcript)
                                await websocket.send_text(json.dumps({"type": "text", "data": reply_text}))

                                listening = False
                                await stream_tts(websocket, reply_text)
                                listening = True

                        silence = 0

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

                            listening = False
                            await stream_tts(websocket, reply_text)
                            listening = True

                elif payload.get("type") in {"close", "stop"}:
                    # 客户端主动通知关闭
                    break

                # 你也可以扩展更多指令类型，如 "reset" 等

    except WebSocketDisconnect:
        pass
