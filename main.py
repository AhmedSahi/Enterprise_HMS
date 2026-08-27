from fastapi import FastAPI
from src.api.v1 import audit
from src.core.database import engine
from src.models.base import Base
from fastapi.middleware.cors import CORSMiddleware

import src.models

from src.api.v1 import (
    users, 
    auth, 
    roles, 
    permissions,
    staff_patients,
    infrastructure,
    pharmacy,
    clinical,
    billing,
    blood_bank
)

# FastAPI app initialize karein
app = FastAPI(
    title="Enterprise HMS API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All routers connection !
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(roles.router, prefix="/api/v1")
app.include_router(permissions.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(staff_patients.router, prefix="/api/v1")
app.include_router(infrastructure.router, prefix="/api/v1")
app.include_router(pharmacy.router, prefix="/api/v1")
app.include_router(clinical.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(blood_bank.router, prefix="/api/v1")