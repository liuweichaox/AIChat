import json
import base64
import asyncio
import audioop
import webrtcvad

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.asr_service import transcribe
from services.llm_service import stream_reply
from services.tts_service import synthesize_stream, DEFAULT_VOICE

router = APIRouter(prefix="/ws")

CLIENT_SAMPLE_RATE = 48000   # 前端采样率
ASR_SAMPLE_RATE = 16000      # ASR采样率
VAD_FRAME_MS = 20
FRAME_BYTES = int(ASR_SAMPLE_RATE * VAD_FRAME_MS / 1000) * 2  # 16kHz * 20ms * 2 bytes (16bit)
SILENCE_LIMIT = int(1.5 / (VAD_FRAME_MS / 1000))              # 静音为一句话断点
vad = webrtcvad.Vad(3)


async def stream_tts(websocket: WebSocket, text: str, voice: str):
    """Stream speech synthesis result to the client."""

    async for chunk in synthesize_stream(text, voice):
        if chunk["type"] == "audio":
            b64 = base64.b64encode(chunk["data"]).decode()
            await websocket.send_text(json.dumps({"type": "tts_audio", "data": b64}))
        elif chunk["type"] == "WordBoundary":
            await websocket.send_text(json.dumps({
                "type": "tts_boundary",
                "offset_sec": chunk["offset"] / 10_000_000,
                "text": chunk["text"],
            }))

@router.websocket("/audio")
async def audio_endpoint(websocket: WebSocket):
    """
    WebSocket实时语音交互：
    - 二进制帧：原始PCM（16-bit、mono、采样率CLIENT_SAMPLE_RATE）
    - 文本帧：控制消息，如 {"type": "resume"}
    """
    await websocket.accept()

    vad_buffer = bytearray()
    audio_buffer = bytearray()
    silence = 0
    listening = True
    voice = DEFAULT_VOICE

    
    async def handle_query(text: str):
        await websocket.send_text(json.dumps({"type": "llm_begin"}))
        
        sentence = ""
        tts_task = None
        tts_started = False

        try:
            async for delta in stream_reply(text):
                content = delta.content
                await websocket.send_text(json.dumps({"type": "llm_delta", "data": content}))
                sentence += content
                if sentence and sentence[-1] in "。！？!?.\n":
                    if not tts_started:
                        await websocket.send_text(json.dumps({"type": "tts_begin"}))
                        tts_started = True
                    if tts_task:
                        await tts_task
                    tts_task = asyncio.create_task(stream_tts(websocket, sentence, voice))
                    sentence = ""
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "error", "data": str(e)}))
            return

        await websocket.send_text(json.dumps({"type": "llm_end"}))

        if tts_task:
            await tts_task
        if sentence.strip():
            if not tts_started:
                await websocket.send_text(json.dumps({"type": "tts_begin"}))
                tts_started = True
            await stream_tts(websocket, sentence, voice)

        if tts_started:
            await websocket.send_text(json.dumps({"type": "tts_end"}))


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

                            if transcript.strip():
                                listening = False
                                vad_buffer.clear()

                                await websocket.send_text(json.dumps({"type": "asr_text", "data": transcript}))
                                await handle_query(transcript)

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
                elif payload.get("type") == "llm_search":
                    text = payload.get("data", "")
                    if text.strip():
                        listening = False
                        vad_buffer.clear()
                        audio_buffer.clear()

                        await handle_query(text)
                elif payload.get("type") == "voice":
                    v = payload.get("data")
                    if isinstance(v, str) and v:
                        voice = v

    except WebSocketDisconnect:
        print("WebSocket disconnected")
        await websocket.close()
        return
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()
        return
