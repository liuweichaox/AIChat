"""基于 Edge TTS 的文本转语音辅助函数。"""

import os
import uuid
import re
import html
import edge_tts


DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

def remove_markdown_headers(text):
    # 替换所有行首1~6个#后接空格
    return re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)

async def synthesize(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Convert markdown text to speech and return MP3 bytes."""
    communicator = edge_tts.Communicate(
        text=remove_markdown_headers(text),
        voice=voice
    )
    audio_bytes = b""
    for chunk in communicator.stream_sync():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    return audio_bytes


async def synthesize_stream(text: str, voice: str = DEFAULT_VOICE):
    """Generate speech chunks (audio and marks) for streaming playback."""
    communicator = edge_tts.Communicate(
        text=remove_markdown_headers(text),
        voice=voice
    )
    for chunk in communicator.stream_sync():
        yield chunk
