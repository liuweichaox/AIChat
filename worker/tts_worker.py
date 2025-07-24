import uuid
import ChatTTS
import torch
import torchaudio
import io
import soundfile as sf 

chat = ChatTTS.Chat()
chat.load(compile=False)

async def synthesize(text: str) -> bytes:
    texts = [text]
    wavs = chat.infer(texts)
    buffer = io.BytesIO()
    sf.write(buffer, wavs[0], 24000, format='WAV')  # 直接写入 BytesIO
    buffer.seek(0)
    return buffer.getvalue()
