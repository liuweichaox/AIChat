"""FastAPI 应用的入口，提供前端演示所需的服务。"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as api_router
from api.websocket import router as ws_router
from api.rtc import router as rtc_router

app = FastAPI()
app.include_router(api_router)
app.include_router(ws_router)
app.include_router(rtc_router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """返回前端页面。"""

    return RedirectResponse(url="/static/index.html")
    
    
if __name__ == "__main__":
    import uvicorn
    # 启动开发服务器
    uvicorn.run(app, host="127.0.0.1", port=8000)
