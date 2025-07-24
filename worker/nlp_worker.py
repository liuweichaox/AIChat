from zhipuai import ZhipuAI

BIGMODEL_API_KEY = "fe28433d565d40a5a1806ab43719e504.HHwmOUiDA4XPCDkk"
client = ZhipuAI(api_key=BIGMODEL_API_KEY)

async def full_reply(user_text: str) -> str:
    response = client.chat.completions.create(
    model="glm-4-plus",  # 请填写您要调用的模型名称
    messages=[
        {"role": "user", "content": user_text}
    ],
    )
    return response


async def stream_reply(user_text: str):
    response = client.chat.completions.create(
    model="glm-4-plus",  # 请填写您要调用的模型名称
    messages=[
        {"role": "user", "content": user_text},
    ],
    stream=True,
    )
    for chunk in response:
        yield chunk.choices[0].delta