from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from passlib.context import CryptContext
from models import Client, Roles, Moderators

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

from decouple import config

PASSWORD_380968101250 = config('PASSWORD_380968101250')
PASSWORD_380123456789 = config("PASSWORD_380123456789")
PASSWORD_380501546037 = config("PASSWORD_380501546037")
PASSWORD_TELEGRAM = config("PASSWORD_TELEGRAM")
PASSWORD_FRONTEND = config("PASSWORD_FRONTEND")

async def get_password_hash(password: str) -> str:
    """
    Хешує пароль.
    """
    return pwd_context.hash(password)


async def initialize_data(db: AsyncSession):
    """
    Ініціалізує базові дані в базі даних.
    """
    try:
        roles = ["beneficiary", "volunteer", "moderator"]
        for role_name in roles:
            result = await db.execute(select(Roles).filter(Roles.name == role_name))
            if not result.scalars().first():
                db.add(Roles(name=role_name))

        clients = [
            {"name": "telegram", "password": PASSWORD_TELEGRAM},
            {"name": "frontend", "password": PASSWORD_FRONTEND}
        ]
        for client_data in clients:
            result = await db.execute(select(Client).filter(Client.name == client_data["name"]))
            if not result.scalars().first():
                db.add(Client(
                    name=client_data["name"],
                    password=await get_password_hash(client_data["password"])
                ))

        moderators = [
            {
                "phone_number": "380968101250",
                "role_id": 3,
                "client_id": 2,
                "password": PASSWORD_380968101250
            },
            {
                "phone_number": "380123456789",
                "role_id": 3,
                "client_id": 1,
                "password": PASSWORD_380123456789
            },
            {
                "phone_number": "380501546037",
                "role_id": 3,
                "client_id": 1,
                "password": PASSWORD_380123456789
            }
        ]
        for moderator_data in moderators:
            result = await db.execute(select(Moderators).filter(Moderators.phone_number == moderator_data["phone_number"]))
            existing_moderator = result.scalars().first()
            if not existing_moderator:
                db.add(Moderators(
                    phone_number=moderator_data["phone_number"],
                    role_id=moderator_data["role_id"],
                    client_id=moderator_data["client_id"],
                    hashed_password=await get_password_hash(moderator_data["password"])
                ))
            else:
                print(f"Модератор з номером телефону {existing_moderator.phone_number} вже існує!")

        await db.commit()
        print("Базові дані успішно ініціалізовані.")
    except Exception as e:
        await db.rollback()
        print(f"Error initializing data: {e}")
