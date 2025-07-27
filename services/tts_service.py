"""基于 Edge TTS 的文本转语音辅助函数。"""

import os
import uuid
import re
import html
import edge_tts


DEFAULT_VOICE = "zh-CN-YunxiNeural"

def remove_markdown_headers(text: str) -> str:
    # 移除标题 (# 开头)
    text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)
    # 移除强调符号 * 或 _
    text = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', text)
    # 移除行内代码 `
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # 移除链接 [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # 移除图片 ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
    # 移除块引用 >
    text = re.sub(r'^\s*>\s?', '', text, flags=re.MULTILINE)
    # 移除无序列表符号 - + *
    text = re.sub(r'^\s*[-+*]\s+', '', text, flags=re.MULTILINE)
    # 移除有序列表符号 1. 2. ...
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # 移除多余的空格
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


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
