"""基于 Whisper 的语音识别工具函数。"""

import whisper
import numpy as np
import torch
import torchaudio

TARGET_SR = 16000

_model = whisper.load_model("base")

async def transcribe(audio_bytes: bytes, sample_rate: int = TARGET_SR) -> str:
    """将 16 位 PCM 音频转换为文本。"""
    # 转为 float32 tensor 并缩放到 [-1.0, 1.0]
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    waveform = torch.from_numpy(audio)
    if sample_rate != TARGET_SR:
        waveform = torchaudio.functional.resample(waveform, sample_rate, TARGET_SR)
    result = _model.transcribe(waveform.numpy(), language="zh", fp16=False)
    return result["text"]
