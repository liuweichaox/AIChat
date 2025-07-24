import whisper
import numpy as np

_model = whisper.load_model("base")

async def transcribe(audio_bytes: bytes) -> str:
    """Transcribe raw 16-bit PCM audio bytes using Whisper."""
    # Convert int16 PCM data to float32 range [-1.0, 1.0]
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    result = _model.transcribe(audio, fp16=False)
    return result["text"]
