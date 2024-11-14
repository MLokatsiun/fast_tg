from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base


URL_DATABASE = 'postgresql+asyncpg://postgres:2117@185.161.209.220:9039/fasttg_db'

engine = create_async_engine(URL_DATABASE, echo=True)

SessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    """
    Establishes an asynchronous database session for requests.

    Returns:
        AsyncSession: An asynchronous database session.
    """
    async with SessionLocal() as db:
        yield db
