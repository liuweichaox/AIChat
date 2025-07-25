"""提供实时语音交互的 WebRTC 接口。"""

import asyncio
import json
import uuid

import av
import numpy as np
import webrtcvad
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamTrack
from fastapi import APIRouter, Request

from services.asr_service import transcribe
from services.llm_service import full_reply
from services.tts_service import synthesize_stream

router = APIRouter(prefix="/rtc")

pcs = {}


class TTSTrack(MediaStreamTrack):
    """向客户端回传合成语音的自定义音频轨道。"""

    kind = "audio"

    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()
        self.stop_event = asyncio.Event()

    async def stream_text(self, text: str):
        """将文本转为语音并持续推送到对端。"""

        self.stop_event.clear()
        async for chunk in synthesize_stream(text):
            if self.stop_event.is_set():
                break
            array = np.frombuffer(chunk, dtype=np.int16)
            array = array.reshape(-1, 1)
            frame = av.AudioFrame.from_ndarray(array, layout="mono")
            await self.queue.put(frame)
        await self.queue.put(None)

    def interrupt(self):
        """提前停止语音流。"""

        self.stop_event.set()

    async def recv(self):
        """获取下一帧音频并发送给客户端。"""

        frame = await self.queue.get()
        if frame is None:
            raise asyncio.CancelledError
        return frame


@router.post("/offer")
async def offer(request: Request):
    """处理客户端的 offer，返回 answer 完成连接。"""

    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pc_id = str(uuid.uuid4())
    tts_track = TTSTrack()
    # 添加 TTS 音轨，并在字典中保存 peer connection 相关信息
    pc.addTrack(tts_track)
    pcs[pc_id] = {"pc": pc, "tts": tts_track}

    data_channel = None

    @pc.on("datachannel")
    def on_datachannel(channel):
        nonlocal data_channel
        if channel.label == "tts":
            data_channel = channel
            pcs[pc_id]["channel"] = channel

    # 设置麦克风流语音检测的参数
    vad = webrtcvad.Vad(3)
    audio_buffer = b""
    frame_buffer = b""
    silence_counter = 0
    speech_counter = 0
    FRAME_DURATION_MS = 30
    SILENCE_THRESHOLD = int(800 / FRAME_DURATION_MS)
    SPEECH_START_FRAMES = int(200 / FRAME_DURATION_MS)
    SAMPLE_RATE = 16000
    FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000) * 2
    speech_started = False

    @pc.on("track")
    async def on_track(track):
        nonlocal audio_buffer, frame_buffer, silence_counter, speech_started, speech_counter
        # 只处理音频轨道
        if track.kind != "audio":
            return
        while True:
            frame = await track.recv()
            # 将音频帧转换为原始 PCM 数据
            pcm = frame.to_ndarray().tobytes()
            frame_buffer += pcm
            while len(frame_buffer) >= FRAME_SIZE:
                seg = frame_buffer[:FRAME_SIZE]
                frame_buffer = frame_buffer[FRAME_SIZE:]
                # 通过 VAD 判断当前帧是否为语音
                is_speech = vad.is_speech(seg, SAMPLE_RATE)
                if is_speech:
                    silence_counter = 0
                    speech_counter += 1
                    if not speech_started and speech_counter >= SPEECH_START_FRAMES:
                        speech_started = True
                    if speech_started:
                        audio_buffer += seg
                        tts_track.interrupt()
                else:
                    if speech_started:
                        silence_counter += 1
                        audio_buffer += seg
                    speech_counter = 0
                if speech_started and silence_counter >= SILENCE_THRESHOLD and audio_buffer:
                    # 静音判定结束后，生成回复并启动语音合成
                    transcript = await transcribe(audio_buffer)
                    if not transcript.strip():
                        audio_buffer = b""
                        silence_counter = 0
                        speech_started = False
                        continue
                    if data_channel and data_channel.readyState == "open":
                        data_channel.send(json.dumps({"type": "transcript", "data": transcript}))
                    reply_text = await full_reply(transcript)
                    if data_channel and data_channel.readyState == "open":
                        data_channel.send(json.dumps({"type": "text", "data": reply_text}))
                    asyncio.create_task(tts_track.stream_text(reply_text))
                    audio_buffer = b""
                    silence_counter = 0
                    speech_started = False

    # 完成 WebRTC 信令交换
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # 将 answer 信息和 id 返回给客户端
    return {"id": pc_id, "sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
