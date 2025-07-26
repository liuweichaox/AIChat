"""基于 Edge TTS 的文本转语音辅助函数。"""

import os
import uuid
import re
import html
import edge_tts


DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
TTS_DIR = "tts_recordings"

def markdown_to_ssml(text: str) -> str:
    """Convert a Markdown string to basic SSML with <mark> tags."""
    # Strip code fences and inline formatting
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"#+\s*(.*)", r"\1", text)
    text = text.replace("\n", " ")

    pieces = re.split(r"([。！？.!?])", text)
    ssml_parts = ["<speak>"]
    idx = 0
    for p in pieces:
        if not p:
            continue
        ssml_parts.append(f"<mark name=\"m{idx}\"/>{html.escape(p)}")
        idx += 1
    ssml_parts.append("</speak>")
    return "".join(ssml_parts)

async def synthesize(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Convert markdown text to speech and return MP3 bytes."""
    ssml = markdown_to_ssml(text)
    communicator = edge_tts.Communicate(
        text=ssml,
        voice=voice
    )
    audio_bytes = b""
    for chunk in communicator.stream_sync():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    return audio_bytes


async def synthesize_stream(text: str, voice: str = DEFAULT_VOICE):
    """Generate speech chunks (audio and marks) for streaming playback."""
    ssml = markdown_to_ssml(text)
    communicator = edge_tts.Communicate(
        text=ssml,
        voice=voice
    )
    for chunk in communicator.stream_sync():
        yield chunk
