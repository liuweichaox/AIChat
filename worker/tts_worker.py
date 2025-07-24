import io
import uuid
import edge_tts
import torch
import torchaudio 

# 可选：设置默认声音（中文女声“小小”）
VOICE = "zh-CN-XiaoxiaoNeural"

async def synthesize(text: str) -> bytes:
    tts = edge_tts.Communicate(text=text, voice=VOICE)
    output_path = f'assets/{uuid.uuid4()}.wav'
    await tts.save(output_path)
    with open(output_path, "rb") as f:
        audio_bytes = f.read()

    return audio_bytes

   