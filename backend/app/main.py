from dotenv import load_dotenv; load_dotenv()

from fastapi import FastAPI
from .routers import news, exploits

app = FastAPI(title="Thandev API", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(news.router)
app.include_router(exploits.router)
