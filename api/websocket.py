"""WebSocket-based real-time voice interaction."""

import asyncio
import json
import audioop

import webrtcvad
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.asr_service import transcribe
from services.llm_service import full_reply
from services.tts_service import synthesize_stream, SAMPLE_RATE as TTS_SAMPLE_RATE

router = APIRouter(prefix="/ws")

CLIENT_SAMPLE_RATE = 48000
ASR_SAMPLE_RATE = 16000


async def stream_tts(websocket: WebSocket, text: str):
    """Stream synthesized speech via WebSocket."""
    buffer = bytearray()
    FRAME_SAMPLES = 960
    FRAME_BYTES = FRAME_SAMPLES * 2
    async for chunk in synthesize_stream(text):
        buffer.extend(chunk)
        while len(buffer) >= FRAME_BYTES:
            frame = bytes(buffer[:FRAME_BYTES])
            buffer = buffer[FRAME_BYTES:]
            await websocket.send_bytes(frame)
    if buffer:
        pad = FRAME_BYTES - len(buffer)
        await websocket.send_bytes(bytes(buffer) + b"\x00" * pad)
    # indicate end of audio
    await websocket.send_bytes(b"")


@router.websocket("/audio")
async def audio_endpoint(websocket: WebSocket):
    """Receive audio via WebSocket and return transcript and TTS."""
    await websocket.accept()

    vad = webrtcvad.Vad(3)
    audio_buffer = b""
    frame_buffer = b""
    silence_counter = 0
    speech_counter = 0
    FRAME_DURATION_MS = 30
    SPEECH_START_FRAMES = int(400 / FRAME_DURATION_MS)
    SILENCE_THRESHOLD = int(1200 / FRAME_DURATION_MS)
    FRAME_SIZE = int(ASR_SAMPLE_RATE * FRAME_DURATION_MS / 1000) * 2
    speech_started = False

    try:
        while True:
            data = await websocket.receive_bytes()
            if CLIENT_SAMPLE_RATE != ASR_SAMPLE_RATE:
                data, _ = audioop.ratecv(data, 2, 1, CLIENT_SAMPLE_RATE, ASR_SAMPLE_RATE, None)
            frame_buffer += data
            while len(frame_buffer) >= FRAME_SIZE:
                seg = frame_buffer[:FRAME_SIZE]
                frame_buffer = frame_buffer[FRAME_SIZE:]
                is_speech = vad.is_speech(seg, ASR_SAMPLE_RATE)
                if is_speech:
                    silence_counter = 0
                    speech_counter += 1
                    if not speech_started and speech_counter >= SPEECH_START_FRAMES:
                        speech_started = True
                    if speech_started:
                        audio_buffer += seg
                else:
                    if speech_started:
                        silence_counter += 1
                        audio_buffer += seg
                    speech_counter = 0
                if speech_started and silence_counter >= SILENCE_THRESHOLD and audio_buffer:
                    transcript = await transcribe(audio_buffer)
                    if transcript.strip():
                        await websocket.send_text(json.dumps({"type": "transcript", "data": transcript}))
                        reply_text = await full_reply(transcript)
                        await websocket.send_text(json.dumps({"type": "text", "data": reply_text}))
                        asyncio.create_task(stream_tts(websocket, reply_text))
                    audio_buffer = b""
                    silence_counter = 0
                    speech_started = False
    except WebSocketDisconnect:
        return
