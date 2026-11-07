
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.database.database import Base, engine
from app.database import models  # noqa: F401

from app.routes.groups import router as groups_router
from app.routes.expenses import router as expenses_router
from app.routes.settlements import router as settlements_router
from app.routes.ai import router as ai_router


templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan
)


app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)


# Register all API routers
app.include_router(groups_router)
app.include_router(expenses_router)
app.include_router(settlements_router)
app.include_router(ai_router)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": settings.app_name
    }
