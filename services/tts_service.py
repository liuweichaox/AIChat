"""基于 Edge TTS 的文本转语音辅助函数。"""

import os
import uuid
import edge_tts


VOICE = "zh-CN-XiaoxiaoNeural"
TTS_DIR = "tts_recordings"

# Edge TTS 默认返回 MP3 数据，不便于直接重采样。我们改为输出原始
# 16-bit PCM，采样率为 24kHz，随后在 WebSocket 中再升采样到客户端
# 需要的 48kHz。
SAMPLE_RATE = 24000
OUTPUT_FORMAT = "raw-24khz-16bit-mono-pcm"


async def synthesize(text: str) -> bytes:
    """将文本一次性合成为语音并返回 WAV 数据，并保存文件。"""
    communicator = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        output_format=OUTPUT_FORMAT,
    )
    os.makedirs(TTS_DIR, exist_ok=True)
    output_path = f"{TTS_DIR}/{uuid.uuid4()}.wav"
    audio_bytes = b""
    async for chunk in communicator.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    with open(output_path, "wb") as wf:
        wf.write(audio_bytes)
    return audio_bytes


async def synthesize_stream(text: str):
    """异步生成语音数据块，用于流式播放，同时保存文件。"""
    communicator = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        output_format=OUTPUT_FORMAT,
    )
    os.makedirs(TTS_DIR, exist_ok=True)
    output_path = f"{TTS_DIR}/{uuid.uuid4()}.wav"
    with open(output_path, "wb") as wf:
        async for chunk in communicator.stream():
            if chunk["type"] == "audio":
                data = chunk["data"]
                wf.write(data)
                yield data
