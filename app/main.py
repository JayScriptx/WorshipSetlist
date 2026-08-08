import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config import settings
from app.database import Base, engine
from app.routers import songs, sections, setlists, setlist_songs

logger = logging.getLogger("worship_app")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Worship Setlist & Song Management API",
    version="1.0.0",
    description="Backend API for managing worship songs, chord charts, and Sunday setlists.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Error handling - never leak raw stack traces / DB errors to the client.
# ---------------------------------------------------------------------------

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.warning("Integrity error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=409,
        content={"detail": "This action conflicts with existing data (e.g. a related record still exists)."},
    )


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Database error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "A database error occurred. Please try again."})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our end. Please try again."})


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(songs.router)
app.include_router(sections.router)
app.include_router(setlists.router)
app.include_router(setlist_songs.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}


@app.on_event("startup")
def on_startup():
    if settings.AUTO_CREATE_TABLES:
        # Dev convenience only - production should use `alembic upgrade head`.
        logger.warning("AUTO_CREATE_TABLES is true - creating tables directly from models (dev only).")
        Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
# The frontend is a plain HTML/CSS/JS single-page app served by this same
# FastAPI process, so there's only one service to deploy on Render and no
# CORS/auth complexity between frontend and backend.

app.mount("/static", StaticFiles(directory="static"), name="static-assets")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    # Let the SPA's JS router handle client-side paths; always serve index.html
    # for any non-API path that isn't a real static file.
    return FileResponse("static/index.html")
