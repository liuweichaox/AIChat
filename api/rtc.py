from fastapi import APIRouter, Request
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay
import asyncio

router = APIRouter(prefix="/rtc")
relay = MediaRelay()
pcs = set()

@router.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)
    video_frames = []

    @pc.on("connectionstatechange")
    async def on_state_change():
        if pc.connectionState in {"failed", "closed"}:
            await pc.close()
            pcs.discard(pc)

    @pc.on("track")
    def on_track(track):
        """Only receive tracks from the client without sending them back."""
        if track.kind == "video":
            local = relay.subscribe(track)

            async def consume():
                async for frame in local.recv():
                    video_frames.append(frame)

            asyncio.create_task(consume())

    await pc.setRemoteDescription(offer)
    await pc.setLocalDescription(await pc.createAnswer())

    # Wait for ICE gathering to complete
    while pc.iceGatheringState != "complete":
        await asyncio.sleep(0.1)

    answer = pc.localDescription
    return {"sdp": answer.sdp, "type": answer.type}
