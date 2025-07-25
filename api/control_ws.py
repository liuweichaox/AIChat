import json
from fastapi import APIRouter, WebSocket

from .webrtc import pcs

router = APIRouter()


@router.websocket("/ws/control")
async def control_ws(websocket: WebSocket):
    await websocket.accept()
    pc_id = None
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "register":
                pc_id = msg.get("id")
            elif msg.get("type") == "interrupt" and pc_id:
                client = pcs.get(pc_id)
                if client:
                    client["tts"].interrupt()
    except Exception as exc:
        print("control ws error", exc)
