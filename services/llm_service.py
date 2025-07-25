"""调用智谱 AI 聊天接口的封装函数。"""

from zhipuai import ZhipuAI
import os

# 从环境变量读取 API Key，便于在不同环境安全部署
api_key = os.getenv("BIGMODEL_API_KEY")
if not api_key:
    raise RuntimeError("BIGMODEL_API_KEY environment variable is not set")

client = ZhipuAI(api_key=api_key)


def format_messages(user_text: str):
    """根据用户输入构造对话上下文。"""

    return [
        {"role": "user", "content": "用中文和我对话"},
        {"role": "user", "content": user_text},
    ]


async def full_reply(user_text: str) -> str:
    """获取模型对用户提问的完整回答。"""
    user_text = user_text.strip()
    if not user_text:
        return ""

    response = client.chat.completions.create(
        model="glm-4-plus",
        messages=format_messages(user_text),
    )
    return response.choices[0].message.content


async def stream_reply(user_text: str):
    """以流式方式逐块返回模型回复。"""
    user_text = user_text.strip()
    if not user_text:
        return

    response = client.chat.completions.create(
        model="glm-4-plus",
        messages=format_messages(user_text),
        stream=True,
    )
    for chunk in response:
        yield chunk.choices[0].delta
