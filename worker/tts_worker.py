import uuid
import ChatTTS
import torch
import torchaudio
import io

chat = ChatTTS.Chat()
chat.load(compile=False)

async def synthesize(text: str) -> bytes:
    texts = [text]
    wavs = chat.infer(texts)
    buffer = io.BytesIO()
    torchaudio.save(buffer, torch.from_numpy(wavs[0]), 24000, format="wav")
    buffer.seek(0)
    output_path = f"assets/{uuid.uuid4()}.wav"
    torchaudio.save(output_path, torch.from_numpy(wavs[0]), 24000)
    return buffer.getvalue()
