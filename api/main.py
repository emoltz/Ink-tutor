from fastapi import FastAPI
from api.routers import health, worksheet

app = FastAPI(title="InkTutor API")
app.include_router(health.router)
app.include_router(worksheet.router)
