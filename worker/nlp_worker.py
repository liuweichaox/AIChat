from zhipuai import ZhipuAI

BIGMODEL_API_KEY = "fe28433d565d40a5a1806ab43719e504.HHwmOUiDA4XPCDkk"
client = ZhipuAI(api_key=BIGMODEL_API_KEY)


def format_messages(user_text: str):
    return [
        {"role": "user", "content": "用中文和我对话"},
        {"role": "user", "content": user_text},
    ]


async def full_reply(user_text: str) -> str:
    response = client.chat.completions.create(
        model="glm-4-plus",
        messages=format_messages(user_text),
    )
    return response.choices[0].message.content


async def stream_reply(user_text: str):
    response = client.chat.completions.create(
        model="glm-4-plus",
        messages=format_messages(user_text),
        stream=True,
    )
    for chunk in response:
        yield chunk.choices[0].delta
