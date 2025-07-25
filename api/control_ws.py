"""用于控制 TTS 播放的 WebSocket 接口。"""

import json
from fastapi import APIRouter, WebSocket

from .webrtc import pcs

router = APIRouter()


@router.websocket("/ws/control")
async def control_ws(websocket: WebSocket):
    """接收控制指令，可在合成语音播放时打断。"""

    await websocket.accept()
    pc_id = None
    try:
        while True:
            # 等待客户端发送控制消息
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "register":
                # 保存对端连接的标识，便于后续找到对应的 TTS Track
                pc_id = msg.get("id")
            elif msg.get("type") == "interrupt" and pc_id:
                # 将中断请求转发给对应的 TTS Track
                client = pcs.get(pc_id)
                if client:
                    client["tts"].interrupt()
    except Exception as exc:
        # 记录控制通道中的异常，便于排查
        print("control ws error", exc)
