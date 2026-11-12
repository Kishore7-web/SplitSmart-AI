import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.database.database import Base, engine, run_migrations
from app.database import models  # noqa: F401

from app.routes.groups import router as groups_router
from app.routes.expenses import router as expenses_router
from app.routes.settlements import router as settlements_router
from app.routes.ai import router as ai_router
from app.routes.evidence import router as evidence_router
from app.routes.analytics import router as analytics_router
from app.routes.payments import router as payments_router
from app.routes.auth import router as auth_router
from app.routes.activities import router as activities_router
from app.routes.customization import router as customization_router


templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure uploads directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)
    # Safely apply incremental SQLite migrations without data loss
    run_migrations()
    # Create any missing new tables
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="The Financial Memory of a Group - Group Activity & Financial Intelligence Platform",
    debug=settings.debug,
    lifespan=lifespan
)


app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)

# Ensure uploads directory exists before mounting
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount(
    "/uploads",
    StaticFiles(directory=settings.upload_dir),
    name="uploads"
)


# Register all API routers
app.include_router(auth_router)
app.include_router(groups_router)
app.include_router(activities_router)
app.include_router(customization_router)
app.include_router(expenses_router)
app.include_router(settlements_router)
app.include_router(ai_router)
app.include_router(evidence_router)
app.include_router(analytics_router)
app.include_router(payments_router)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.app_name,
            "app_version": settings.app_version,
        }
    )


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": "sandbox" if settings.debug else "production"
    }
