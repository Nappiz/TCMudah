from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings

settings = get_settings()

# psycopg async driver: "postgresql+psycopg"
# NOTE: SQLAlchemy async engine expects "postgresql+psycopg" with async? psycopg v3 supports asyncio via "postgresql+psycopg"
# SQLAlchemy 2.x works with it. If issues, switch to "postgresql+asyncpg" and install asyncpg.
engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
