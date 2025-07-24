import whisper
import numpy as np

_model = whisper.load_model("base")

async def transcribe(audio_bytes: bytes) -> str:
    audio = np.frombuffer(audio_bytes, dtype=np.float32)
    result = _model.transcribe(audio, fp16=False)
    return result['text']