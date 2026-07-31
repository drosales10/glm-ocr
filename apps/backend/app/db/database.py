"""
Conexión a la base de datos y gestión de sesiones
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.models.base import Base
from app.utils.config import settings
from app.utils.logger import logger

# Crear el motor asíncrono
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)

# Crear la fábrica de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def init_db():
    """Inicializa la base de datos"""
    logger.info("Initializing database...")

    # Crear todas las tablas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized successfully")


async def close_db():
    """Cierra la conexión a la base de datos"""
    logger.info("Closing database connection...")
    await engine.dispose()
    logger.info("Database connection closed")


async def get_db() -> AsyncSession:
    """
    Obtiene una sesión de base de datos (inyección de dependencias)

    Yields:
        AsyncSession: Sesión de base de datos
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
