import asyncio
import json
import audioop
import time
import webrtcvad

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.asr_service import transcribe
from services.llm_service import full_reply
from services.tts_service import synthesize_stream
from services.buffers import audio_buffer, video_frames

router = APIRouter(prefix="/ws")

CLIENT_SAMPLE_RATE = 48000   # 前端采样率
ASR_SAMPLE_RATE = 16000      # ASR采样率
VAD_FRAME_MS = 20
FRAME_BYTES = int(ASR_SAMPLE_RATE * VAD_FRAME_MS / 1000) * 2  # 16kHz * 20ms * 2 bytes (16bit)
SILENCE_LIMIT = int(0.8 / (VAD_FRAME_MS / 1000))              # 0.8秒静音为一句话断点
vad = webrtcvad.Vad(3)

async def stream_tts(websocket: WebSocket, text: str):
    """TTS文本流转音频发送，包含轮次边界"""
    await websocket.send_text(json.dumps({"type": "tts_begin"}))
    async for chunk in synthesize_stream(text):
        await websocket.send_bytes(chunk)
    await websocket.send_text(json.dumps({"type": "tts_end"}))


@router.websocket("/audio")
async def audio_endpoint(websocket: WebSocket):
    """
    WebSocket实时语音交互：
    - 二进制帧：原始PCM（16-bit、mono、采样率CLIENT_SAMPLE_RATE）
    - 文本帧：控制消息，如 {"type": "resume"}
    """
    await websocket.accept()

    vad_buffer = bytearray()
    silence = 0
    listening = True

    try:
        while True:
            msg = await websocket.receive()
            # 处理音频流
            if "bytes" in msg:
                data: bytes = msg["bytes"]

                if not listening:
                    # 不监听时丢弃所有流并清缓冲
                    vad_buffer.clear()
                    audio_buffer.clear()
                    continue

                # 必要时重采样
                if CLIENT_SAMPLE_RATE != ASR_SAMPLE_RATE:
                    data, _ = audioop.ratecv(
                        data, 2, 1,
                        CLIENT_SAMPLE_RATE, ASR_SAMPLE_RATE,
                        None
                    )
                audio_buffer.extend(data)
                vad_buffer.extend(data)

                # 语音活动检测循环
                while len(vad_buffer) >= FRAME_BYTES:
                    frame = bytes(vad_buffer[:FRAME_BYTES])
                    vad_buffer = vad_buffer[FRAME_BYTES:]

                    if vad.is_speech(frame, ASR_SAMPLE_RATE):
                        silence = 0
                    else:
                        silence += 1

                    if silence > SILENCE_LIMIT:
                        if audio_buffer:
                            # 一句话结束，ASR推理
                            transcript = await transcribe(bytes(audio_buffer))
                            audio_buffer.clear()
                            video_frames.clear()

                            if transcript.strip():
                                # 进入“回复+TTS”阶段，先关闭监听
                                listening = False
                                vad_buffer.clear()

                                await websocket.send_text(json.dumps({"type": "asr_text", "data": transcript}))
                                llm_reply = await full_reply(transcript)
                                await websocket.send_text(json.dumps({"type": "llm_reply", "data": llm_reply}))
                                await stream_tts(websocket, llm_reply)

                        silence = 0
            # 处理控制消息
            elif "text" in msg:
                try:
                    payload = json.loads(msg["text"])
                except Exception:
                    payload = {"type": msg["text"]}

                if payload.get("type") == "resume":
                    # TTS播放完毕，恢复监听，重置相关状态
                    listening = True
                    silence = 0
                    audio_buffer.clear()
                    vad_buffer.clear()
                    video_frames.clear()
                elif payload.get("type") == "text":
                    text = payload.get("data", "")
                    if text.strip():
                        listening = False
                        vad_buffer.clear()
                        audio_buffer.clear()
                        video_frames.clear()

                        llm_reply = await full_reply(text)
                        await websocket.send_text(json.dumps({"type": "llm_reply", "data": llm_reply}))
                        await stream_tts(websocket, llm_reply)

    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
