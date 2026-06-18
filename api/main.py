from fastapi import FastAPI
from api.routers import health

app = FastAPI(title="InkTutor API")
app.include_router(health.router)
