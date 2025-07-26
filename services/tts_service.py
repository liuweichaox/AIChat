"""基于 Edge TTS 的文本转语音辅助函数。"""

import os
import uuid
import edge_tts


VOICE = "zh-CN-XiaoxiaoNeural"
TTS_DIR = "tts_recordings"

async def synthesize(text: str) -> bytes:
    """将文本一次性合成为语音并返回 MP3 数据，并保存文件。"""
    communicator = edge_tts.Communicate(
        text=text,
        voice=VOICE
    )
    audio_bytes = b""
    for chunk in communicator.stream_sync():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    return audio_bytes


async def synthesize_stream(text: str):
    """异步生成语音数据块（MP3），用于流式播放，同时保存文件。"""
    communicator = edge_tts.Communicate(
        text=text,
        voice=VOICE
    )
    for chunk in communicator.stream_sync():
        if chunk["type"] == "audio":
            data = chunk["data"]
            yield data
