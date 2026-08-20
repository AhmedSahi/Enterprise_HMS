from fastapi import FastAPI
from src.api.v1 import audit
from src.core.database import engine
from src.models.base import Base

import src.models

from src.api.v1 import (
    users, 
    auth, 
    roles, 
    permissions,
    staff_patients,
    infrastructure,
    pharmacy
)

# FastAPI app initialize karein
app = FastAPI(
    title="Enterprise HMS API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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
