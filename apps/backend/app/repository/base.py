"""
Clase base Repository
"""
from typing import Generic, TypeVar, Type, Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

ModelType = TypeVar("ModelType", bound=Any)


class BaseRepository(Generic[ModelType]):
    """Clase base Repository"""

    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        self.session = session
        self.model = model

    async def create(self, **kwargs) -> ModelType:
        """Crea un nuevo registro"""
        db_obj = self.model(**kwargs)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def get(self, id: int) -> Optional[ModelType]:
        """Obtiene el registro por ID"""
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_field(self, field_name: str, value: Any) -> Optional[ModelType]:
        """Obtiene el registro por valor de campo"""
        stmt = select(self.model).where(getattr(self.model, field_name) == value)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters
    ) -> List[ModelType]:
        """Consulta la lista de registros"""
        stmt = select(self.model)

        for key, value in filters.items():
            if hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        id: int,
        **kwargs
    ) -> Optional[ModelType]:
        """Actualiza el registro"""
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj:
            for key, value in kwargs.items():
                if hasattr(db_obj, key):
                    setattr(db_obj, key, value)

            await self.session.flush()
            await self.session.refresh(db_obj)

        return db_obj

    async def delete(self, id: int) -> bool:
        """Elimina el registro"""
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj:
            await self.session.delete(db_obj)
            await self.session.flush()
            return True

        return False

    async def count(self, **filters) -> int:
        """Cuenta el número de registros"""
        from sqlalchemy import func

        stmt = select(func.count(self.model.id))

        for key, value in filters.items():
            if hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)

        result = await self.session.execute(stmt)
        return result.scalar() or 0
