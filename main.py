from fastapi import FastAPI
from src.core.database import engine
from src.models.base import Base


# FastAPI app initialize karein
app = FastAPI(
    title="Enterprise IAM API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


@app.get("/")
def read_root():
    return {"message": "Welcome to Enterprise IAM System API!"}