from fastapi import APIRouter, WebSocket
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaBlackhole
import json
import asyncio
import webrtcvad
import numpy as np

from worker.asr_worker import transcribe
from worker.nlp_worker import stream_reply

router = APIRouter()

@router.websocket("/ws/signal")
async def signal_ws(websocket: WebSocket):
    await websocket.accept()

    pc = RTCPeerConnection()
    media_sink = MediaBlackhole()

    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            asyncio.create_task(process_audio(track, websocket))

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data["type"] == "offer":
                await pc.setRemoteDescription(RTCSessionDescription(sdp=data["sdp"], type="offer"))
                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)
                await websocket.send_text(json.dumps({
                    "type": "answer",
                    "sdp": pc.localDescription.sdp
                }))

            elif data["type"] == "candidate":
                candidate = data["candidate"]
                ice = RTCIceCandidate(
                    sdpMid=candidate["sdpMid"],
                    sdpMLineIndex=candidate["sdpMLineIndex"],
                    candidate=candidate["candidate"]
                )
                await pc.addIceCandidate(ice)

    except Exception as e:
        print("WebSocket closed or error:", str(e))


async def process_audio(track, websocket):
    print("[track] start streaming audio")
    vad = webrtcvad.Vad(2)
    audio_buffer = b""
    silence_counter = 0
    FRAME_DURATION_MS = 30
    SILENCE_THRESHOLD = int(800 / FRAME_DURATION_MS)
    SAMPLE_RATE = 16000
    FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000) * 2  # 16bit = 2 bytes

    try:
        while True:
            frame = await track.recv()
            pcm = frame.to_ndarray().tobytes()
            if len(pcm) < FRAME_SIZE:
                continue

            chunk = pcm[:FRAME_SIZE]
            is_speech = vad.is_speech(chunk, SAMPLE_RATE)

            if is_speech:
                silence_counter = 0
                audio_buffer += chunk
            else:
                silence_counter += 1
                if audio_buffer:
                    audio_buffer += chunk  # still save trailing silence

            if silence_counter >= SILENCE_THRESHOLD and audio_buffer:
                transcript = await transcribe(audio_buffer)
                async for chunk in stream_reply(transcript):
                    await websocket.send_text(json.dumps({"type": "text", "data": chunk}))
                audio_buffer = b""
                silence_counter = 0

    except Exception as e:
        print("Audio processing error:", str(e))
