"""基于 faster-whisper 的语音识别工具函数。"""
import numpy as np
from faster_whisper import WhisperModel

# 强制 CPU + int8（适合 Apple M1/M2）
_model = WhisperModel("tiny", device="cpu", compute_type="int8")

async def transcribe(audio_bytes: bytes) -> str:
    """将 PCM16 音频流转换为文本"""
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    segments, info = _model.transcribe(audio, language="zh")

    # 拼接所有识别到的文本
    text = "".join([segment.text for segment in segments])
    return text.strip()
