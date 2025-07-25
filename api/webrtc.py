import asyncio
import json
import uuid

import av
import webrtcvad
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamTrack
from fastapi import APIRouter, Request

from worker.asr_worker import transcribe
from worker.nlp_worker import full_reply
from worker.tts_worker import synthesize_stream

router = APIRouter(prefix="/rtc")

pcs = {}


class TTSTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()
        self.stop_event = asyncio.Event()

    async def stream_text(self, text: str):
        self.stop_event.clear()
        async for chunk in synthesize_stream(text):
            if self.stop_event.is_set():
                break
            frame = av.AudioFrame.from_ndarray(chunk, layout="mono")
            await self.queue.put(frame)
        await self.queue.put(None)

    def interrupt(self):
        self.stop_event.set()

    async def recv(self):
        frame = await self.queue.get()
        if frame is None:
            raise asyncio.CancelledError
        return frame


@router.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pc_id = str(uuid.uuid4())
    tts_track = TTSTrack()
    pc.addTrack(tts_track)
    pcs[pc_id] = {"pc": pc, "tts": tts_track}

    vad = webrtcvad.Vad(3)
    audio_buffer = b""
    frame_buffer = b""
    silence_counter = 0
    FRAME_DURATION_MS = 30
    SILENCE_THRESHOLD = int(800 / FRAME_DURATION_MS)
    SAMPLE_RATE = 16000
    FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000) * 2
    speech_started = False

    @pc.on("track")
    async def on_track(track):
        nonlocal audio_buffer, frame_buffer, silence_counter, speech_started
        if track.kind != "audio":
            return
        async for frame in track:
            pcm = frame.to_ndarray().tobytes()
            frame_buffer += pcm
            while len(frame_buffer) >= FRAME_SIZE:
                seg = frame_buffer[:FRAME_SIZE]
                frame_buffer = frame_buffer[FRAME_SIZE:]
                is_speech = vad.is_speech(seg, SAMPLE_RATE)
                if is_speech:
                    silence_counter = 0
                    audio_buffer += seg
                    speech_started = True
                    tts_track.interrupt()
                else:
                    if speech_started:
                        silence_counter += 1
                        audio_buffer += seg
                if speech_started and silence_counter >= SILENCE_THRESHOLD and audio_buffer:
                    transcript = await transcribe(audio_buffer)
                    reply_text = await full_reply(transcript)
                    asyncio.create_task(tts_track.stream_text(reply_text))
                    audio_buffer = b""
                    silence_counter = 0
                    speech_started = False

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"id": pc_id, "sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
