"""音频 WebSocket 端点，用于实现浏览器和服务端的语音交互。"""

import wave
import json

import numpy as np
import webrtcvad
from fastapi import APIRouter, WebSocket

from services.asr_service import transcribe
from services.llm_service import full_reply
from services.tts_service import synthesize


router = APIRouter()


@router.websocket("/ws/audio")
async def audio_ws(websocket: WebSocket):
    """处理浏览器发送的音频流，完成识别、回复和合成。"""

    # 接收来自浏览器的 WebSocket 连接
    await websocket.accept()

    # 初始化语音活动检测器，用于判断语音和静音
    vad = webrtcvad.Vad(3)
    # 用于存储音频帧和整段语音的缓存区
    audio_buffer = b""
    frame_buffer = b""
    silence_counter = 0
    FRAME_DURATION_MS = 30
    SILENCE_THRESHOLD = int(800 / FRAME_DURATION_MS)
    SAMPLE_RATE = 16000
    # 每帧音频的字节数
    FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000) * 2
    speech_started = False

    try:
        while True:
            # 从浏览器接收音频数据，格式为原始 PCM
            chunk = await websocket.receive_bytes()
            if not chunk:
                continue

            # 累积音频帧并在数据足够时进行 VAD 判断
            frame_buffer += chunk
            while len(frame_buffer) >= FRAME_SIZE:
                seg = frame_buffer[:FRAME_SIZE]
                frame_buffer = frame_buffer[FRAME_SIZE:]

                # 判断当前帧是否包含语音
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
                    # 检测到静音，开始识别整段语音
                    transcript = await transcribe(audio_buffer)
                    if not transcript:
                        continue
                    await websocket.send_text(
                        json.dumps({"type": "transcript", "data": transcript})
                    )
                    # 调用大模型生成回复文本
                    reply_text = await full_reply(transcript)
                    await websocket.send_text(
                        json.dumps({"type": "text", "data": reply_text})
                    )
                    # 将回复文本合成为语音并发送给浏览器
                    audio_bytes = await synthesize(reply_text)
                    await websocket.send_text(
                        json.dumps({"type": "audio", "data": audio_bytes.hex()})
                    )
                    # 重置状态，准备处理下一句语音
                    audio_buffer = b""
                    silence_counter = 0
                    speech_started = False

    except Exception as e:
        # 打印异常信息便于调试
        print("WebSocket error:", e)
