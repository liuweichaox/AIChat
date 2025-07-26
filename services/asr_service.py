"""基于 FunASR 的语音识别工具函数。"""
import numpy as np
from funasr import AutoModel

# 加载 FunASR 模型（可以选择不同的模型，比如 paraformer）
_model = AutoModel(model="paraformer-zh", trust_remote_code=True)

async def transcribe(audio_bytes: bytes) -> str:
    """将 16 位 PCM 音频转换为文本。"""

    # 将 int16 PCM 数据转换为 float32，并缩放到 [-1.0, 1.0]
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    # FunASR 模型的推理
    # 注意：FunASR 接收 PCM float32 格式
    result = _model.generate(input=audio, sampling_rate=16000)
    return result[0]["text"]
