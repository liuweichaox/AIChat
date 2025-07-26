"""基于 FunASR 的语音识别工具函数。"""
import numpy as np
from funasr import AutoModel
import wave
import datetime
import os

# 加载 FunASR 模型
_model = AutoModel(model="paraformer-zh", trust_remote_code=True)

async def transcribe(audio_bytes: bytes) -> str:
    """将 16 位 PCM 音频转换为文本，并保存为本地 wav 文件。"""
    # FunASR 推理
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    result = _model.generate(input=audio, sampling_rate=16000)
    return result[0]["text"]
