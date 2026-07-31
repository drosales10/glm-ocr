"""
Punto de entrada de la aplicación FastAPI
"""
import sys
from pathlib import Path


from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.tasks import router as tasks_router
from app.api.system import router as system_router
from app.core.task_manager import init_task_system, shutdown_task_system
from app.db.database import init_db, close_db
from app.utils.logger import logger
from app.utils.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación"""
    # Al iniciar
    logger.info("Application starting up...")

    # 1. Inicializar la base de datos
    await init_db()

    # 2. Inicializar el sistema de tareas
    await init_task_system()

    logger.info("Application startup complete")

    yield

    # Al cerrar
    logger.info("Application shutting down...")

    # 1. Cerrar el sistema de tareas
    await shutdown_task_system()

    # 2. Cerrar la conexión a la base de datos
    await close_db()

    logger.info("Application shutdown complete")


# Crear la aplicación FastAPI
app = FastAPI(
    title=f"{settings.APP_NAME}",
    description="Async task execution system",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Configuración CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar rutas
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Ruta raíz"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Comprobación de salud"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
