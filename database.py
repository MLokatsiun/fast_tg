from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

URL_DATABASE = 'postgresql://postgres:2117@fast-tg-db/fasttg_db'

engine = create_engine(URL_DATABASE)

session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Establishes a database session for requests.

    Returns:
        Session: A database session.
    """
    db = session_local()
    try:
        yield db
    finally:
        db.close()