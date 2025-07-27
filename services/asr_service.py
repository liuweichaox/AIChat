"""基于 faster-whisper 的语音识别工具函数。"""
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
import torch

_model = WhisperModel("tiny", device="cuda" if torch.cuda.is_available() else "cpu", compute_type="float16")

async def transcribe(audio_bytes: bytes) -> str:
    """将 16 位 PCM 音频转换为文本"""
    # 将 PCM bytes 转换为 float32 numpy array
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    # 直接使用 faster-whisper 进行转录
    segments, info = _model.transcribe(audio, language="zh")
    
    # 合并转录文本
    text = "".join([seg.text for seg in segments])
    return text.strip()
