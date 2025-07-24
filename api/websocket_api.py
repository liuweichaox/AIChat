from fastapi import APIRouter, WebSocket
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
import asyncio
import json
import webrtcvad

from worker.asr_worker import transcribe
from worker.nlp_worker import full_reply
from worker.tts_worker import synthesize

router = APIRouter()

@router.websocket("/ws/signal")
async def signal_ws(websocket: WebSocket):
    await websocket.accept()

    pc = RTCPeerConnection()

    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            asyncio.create_task(process_audio(track, websocket))

    @pc.on("icecandidate")
    async def on_icecandidate(candidate):
        if candidate:
            await websocket.send_text(json.dumps({
                "type": "candidate",
                "candidate": {
                    "candidate": candidate.candidate,
                    "sdpMid": candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                },
            }))

    try:
        while True:
            data = json.loads(await websocket.receive_text())
            msg_type = data.get("type")

            if msg_type == "offer":
                await pc.setRemoteDescription(
                    RTCSessionDescription(sdp=data["sdp"], type="offer")
                )
                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)
                await websocket.send_text(json.dumps({
                    "type": "answer",
                    "sdp": pc.localDescription.sdp,
                }))

            elif msg_type == "candidate":
                cand = data["candidate"]
                ice = RTCIceCandidate(
                    sdpMid=cand["sdpMid"],
                    sdpMLineIndex=cand["sdpMLineIndex"],
                    candidate=cand["candidate"],
                )
                await pc.addIceCandidate(ice)

    except Exception as e:
        print("WebSocket closed or error:", str(e))
    finally:
        await pc.close()


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
                reply_text = await full_reply(transcript)
                await websocket.send_text(json.dumps({"type": "text", "data": reply_text}))
                audio_bytes = await synthesize(reply_text)
                await websocket.send_text(json.dumps({"type": "audio", "data": audio_bytes.hex()}))
                audio_buffer = b""
                silence_counter = 0

    except Exception as e:
        print("Audio processing error:", str(e))
