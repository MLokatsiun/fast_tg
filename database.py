from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

from decouple import config

URL_DATABASE = config("DATABASE_URL_ASYNCH")

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
