"""基于 Edge TTS 的文本转语音辅助函数。"""

import os
import uuid
import edge_tts

VOICE = "zh-CN-XiaoxiaoNeural"
TTS_DIR = "tts_recordings"


async def synthesize(text: str) -> bytes:
    """将文本一次性合成为语音并返回 WAV 数据，并保存文件。"""
    tts = edge_tts.Communicate(text=text, voice=VOICE)
    os.makedirs(TTS_DIR, exist_ok=True)
    output_path = f"{TTS_DIR}/{uuid.uuid4()}.wav"
    await tts.save(output_path)
    with open(output_path, "rb") as f:
        return f.read()


async def synthesize_stream(text: str):
    """异步生成语音数据块，用于流式播放，同时保存文件。"""
    communicator = edge_tts.Communicate(text=text, voice=VOICE)
    os.makedirs(TTS_DIR, exist_ok=True)
    output_path = f"{TTS_DIR}/{uuid.uuid4()}.wav"
    with open(output_path, "wb") as f:
        async for chunk in communicator.stream():
            if chunk["type"] == "audio":
                data = chunk["data"]
                f.write(data)
                yield data
