"""调用智谱 AI 聊天接口的封装函数。"""

from zhipuai import ZhipuAI
import asyncio

BIGMODEL_API_KEY =  "fe28433d565d40a5a1806ab43719e504.HHwmOUiDA4XPCDkk"
client = ZhipuAI(api_key=BIGMODEL_API_KEY)

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
    try:
        # 把同步调用放到线程池里，避免阻塞事件循环
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="glm-4-plus",
                messages=format_messages(user_text),
            )
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"


async def stream_reply(user_text: str):
    """以流式方式逐块返回模型回复。"""
    try:
        # 这里是同步流式迭代器，不是真正的 async
        # 但可以 yield 出结果
        response = client.chat.completions.create(
            model="glm-4-plus",
            messages=format_messages(user_text),
            stream=True,
        )
        for chunk in response:
            yield chunk.choices[0].delta
    except Exception as e:
        yield f"Error: {e}"
