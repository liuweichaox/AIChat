import os
import uuid
import edge_tts

VOICE = "zh-CN-XiaoxiaoNeural"


async def synthesize(text: str) -> bytes:
    """Synthesize text to audio and return WAV bytes."""
    tts = edge_tts.Communicate(text=text, voice=VOICE)
    os.makedirs("assets", exist_ok=True)
    output_path = f"assets/{uuid.uuid4()}.wav"
    await tts.save(output_path)
    with open(output_path, "rb") as f:
        return f.read()


async def synthesize_stream(text: str):
    """Asynchronously yield WAV byte chunks for streaming playback."""
    communicator = edge_tts.Communicate(text=text, voice=VOICE)
    async for chunk in communicator.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]
