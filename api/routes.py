"""提供给前端使用的 HTTP 接口。"""

from edge_tts import VoicesManager
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from services.asr_service import transcribe
from services.llm_service import full_reply, stream_reply
from services.tts_service import synthesize, DEFAULT_VOICE

router = APIRouter(prefix="/api")

@router.post("/asr")
async def asr_endpoint(audio: UploadFile = File(...)):
    """接收上传的音频并调用 Whisper 进行识别。"""

    audio_bytes = await audio.read()
    text = await transcribe(audio_bytes)
    return JSONResponse({"transcript": text})

@router.get("/full-reply")
async def full_reply_endpoint(text: str):
    """返回大模型生成的完整回复文本。"""

    bot_text = await full_reply(text)
    return JSONResponse({"reply": bot_text})

@router.get("/stream-reply")
async def stream_reply_endpoint(text: str):
    """通过 SSE 流式返回模型回复内容。"""

    async def event_generator():
        # 按 SSE 格式不断推送回复片段
        async for chunk in stream_reply(text):
            yield f"data: {chunk}\n\n"  # SSE 格式要求
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/tts")
async def tts_endpoint(payload: dict):
    """将文本转为语音，返回 WAV 字节数据（十六进制）。"""

    text = payload.get("text")
    voice = payload.get("voice", DEFAULT_VOICE)
    audio_bytes = await synthesize(text, voice)
    return JSONResponse({"audio": audio_bytes.hex()})

def extract_voice_info(voice):
    return {
        "Name":  voice["Name"],
        "ShortName": voice["ShortName"],
        "Gender": voice["Gender"],
        "Locale":  voice["Locale"],
        "SuggestedCodec": voice["SuggestedCodec"],
        "FriendlyName": voice["FriendlyName"],
        "Status": voice["Status"],
        "VoiceTag": voice["VoiceTag"],
        "Language": voice["Language"],
    }

@router.get("/voices")
async def get_voices():
    manager = await VoicesManager.create()
    result = [extract_voice_info(v) for v in manager.voices]
    return result
