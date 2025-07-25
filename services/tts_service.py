"""基于 Edge TTS 的文本转语音辅助函数。"""

import os
import uuid
import wave
import edge_tts


VOICE = "zh-CN-XiaoxiaoNeural"
EDGE_FORMAT = "raw-16khz-16bit-mono-pcm"
SAMPLE_RATE = 16000


async def synthesize(text: str) -> bytes:
    """将文本一次性合成为语音并返回 WAV 数据，并保存文件。"""
    communicator = edge_tts.Communicate(
        text=text, voice=VOICE, output_format=EDGE_FORMAT
    )
    os.makedirs(TTS_DIR, exist_ok=True)
    output_path = f"{TTS_DIR}/{uuid.uuid4()}.wav"
    audio_bytes = b""
    async for chunk in communicator.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_bytes)
    return audio_bytes


async def synthesize_stream(text: str):
    """异步生成语音数据块，用于流式播放，同时保存文件。"""
    communicator = edge_tts.Communicate(
        text=text, voice=VOICE, output_format=EDGE_FORMAT
    )
    os.makedirs(TTS_DIR, exist_ok=True)
    output_path = f"{TTS_DIR}/{uuid.uuid4()}.wav"
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        async for chunk in communicator.stream():
            if chunk["type"] == "audio":
                data = chunk["data"]
                wf.writeframes(data)
                yield data
