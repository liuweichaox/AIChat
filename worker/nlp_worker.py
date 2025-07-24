import os
import httpx
import asyncio

BIGMODEL_API_KEY =  "fe28433d565d40a5a1806ab43719e504.HHwmOUiDA4XPCDkk"
BASE_URL = "https://bigmodel.cn/dev/api/normal-model/glm-4"

async def full_reply(user_text: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BIGMODEL_API_KEY}"
    }
    payload = {
        "inputs": user_text,
        "parameters": {
            "temperature": 0.7,
            "max_tokens": 512
        }
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(BASE_URL + "/generate", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        # Assuming response format {"data": {"text": "..."}}
        return data.get("data", {}).get("text", "")

async def stream_reply(user_text: str):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BIGMODEL_API_KEY}"
    }
    payload = {
        "inputs": user_text,
        "parameters": {"temperature": 0.7},
        "stream": True
    }
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", BASE_URL + "/generate_stream", json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    # Each line is a JSON chunk
                    chunk = httpx.Response(200, content=line).json()
                    yield chunk.get("data", {}).get("text", "")