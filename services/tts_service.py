"""基于 Edge TTS 的文本转语音辅助函数。"""

import os
import uuid
import edge_tts

VOICE = "zh-CN-XiaoxiaoNeural"


async def synthesize(text: str) -> bytes:
    """将文本一次性合成为语音并返回 WAV 数据。"""
    tts = edge_tts.Communicate(text=text, voice=VOICE)
    os.makedirs("assets", exist_ok=True)
    output_path = f"assets/{uuid.uuid4()}.wav"
    await tts.save(output_path)
    try:
        with open(output_path, "rb") as f:
            return f.read()
    finally:
        os.remove(output_path)


async def synthesize_stream(text: str):
    """异步生成语音数据块，用于流式播放。"""
    communicator = edge_tts.Communicate(text=text, voice=VOICE)
    async for chunk in communicator.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]
