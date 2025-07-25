"""提供给前端使用的 HTTP 接口。"""

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from worker.asr_worker import transcribe
from worker.nlp_worker import full_reply, stream_reply
from worker.tts_worker import synthesize

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

    # 从请求 JSON 中取出需要合成的文本
    text = payload.get("text")
    audio_bytes = await synthesize(text)
    return JSONResponse({"audio": audio_bytes.hex()})
