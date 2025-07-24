from fastapi import APIRouter, WebSocket
import json
import webrtcvad

from worker.asr_worker import transcribe
from worker.nlp_worker import full_reply
from worker.tts_worker import synthesize


router = APIRouter()


@router.websocket("/ws/audio")
async def audio_ws(websocket: WebSocket):
    await websocket.accept()

    vad = webrtcvad.Vad(2)
    audio_buffer = b""
    frame_buffer = b""
    silence_counter = 0
    FRAME_DURATION_MS = 30
    SILENCE_THRESHOLD = int(800 / FRAME_DURATION_MS)
    SAMPLE_RATE = 16000
    FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000) * 2
    speech_started = False

    try:
        while True:
            chunk = await websocket.receive_bytes()
            if not chunk:
                continue

            frame_buffer += chunk
            while len(frame_buffer) >= FRAME_SIZE:
                seg = frame_buffer[:FRAME_SIZE]
                frame_buffer = frame_buffer[FRAME_SIZE:]

                is_speech = vad.is_speech(seg, SAMPLE_RATE)

                if is_speech:
                    silence_counter = 0
                    audio_buffer += seg
                    speech_started = True
                else:
                    if speech_started:
                        silence_counter += 1
                        audio_buffer += seg

                if speech_started and silence_counter >= SILENCE_THRESHOLD and audio_buffer:
                    transcript = await transcribe(audio_buffer)
                    await websocket.send_text(
                        json.dumps({"type": "transcript", "data": transcript})
                    )
                    reply_text = await full_reply(transcript)
                    await websocket.send_text(
                        json.dumps({"type": "text", "data": reply_text})
                    )
                    audio_bytes = await synthesize(reply_text)
                    await websocket.send_text(
                        json.dumps({"type": "audio", "data": audio_bytes.hex()})
                    )
                    audio_buffer = b""
                    silence_counter = 0
                    speech_started = False

    except Exception as e:
        print("WebSocket error:", e)
