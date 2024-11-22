from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from decouple import config

DATABASE_URL = config("DATABASE_URL")

engine = create_engine(DATABASE_URL)

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

if __name__ == "__main__":
    print("Таблиці створені успішно!")


