"""基于 Whisper 的语音识别工具函数。"""

import os
import uuid
import wave
import whisper
import numpy as np

_model = whisper.load_model("base")

async def transcribe(audio_bytes: bytes) -> str:
    """将 16 位 PCM 音频转换为文本。"""

    # 先保存原始音频，便于调试或后续使用
    os.makedirs("recordings", exist_ok=True)
    path = f"recordings/{uuid.uuid4().hex}.wav"
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(audio_bytes)

    # 将 int16 PCM 数据转换为 float32，并缩放到 [-1.0, 1.0]
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    result = _model.transcribe(audio, fp16=False)
    return result["text"]
