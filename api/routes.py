from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from worker.asr_worker import transcribe
from worker.nlp_worker import full_reply, stream_reply
from worker.tts_worker import synthesize

router = APIRouter(prefix="/api")

@router.post("/asr")
async def asr_endpoint(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    text = await transcribe(audio_bytes)
    return JSONResponse({"transcript": text})

@router.get("/full-reply")
async def full_reply_endpoint(text: str):
    bot_text = await full_reply(text)
    return JSONResponse({"reply": bot_text})

@router.get("/stream-reply")
async def stream_reply_endpoint(text: str):
    async def event_generator():
        async for chunk in stream_reply(text):
            yield f"data: {chunk}\n\n"  # SSE 格式要求
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/tts")
async def tts_endpoint(payload: dict):
    text = payload.get("text")
    audio_bytes = await synthesize(text)    
    return JSONResponse({"audio": audio_bytes.hex()})
