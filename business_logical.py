from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
import models
import httpx
from passlib.context import CryptContext
from database import get_db
from models import Customer, Moderators

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = '884e824f5571d0acf70e2cc8600c2deb68dcc302c2402a1838ef2b38e9b22ade'
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")


def create_refresh_token(data: dict, expires_delta: timedelta = timedelta(days=7)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "user_id": data.get("user_id")})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt


async def get_current_user(token: str, db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        role_id = payload.get("role_id")

        if user_id is None or role_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        stmt = select(Customer).filter(Customer.id == user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()

        if user is None:
            stmt = select(Moderators).filter(Moderators.id == user_id)
            result = await db.execute(stmt)
            user = result.scalars().first()

        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        return user, role_id

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_beneficiary(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    user, user_role = await get_current_user(token, db)
    if user_role != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return user


async def get_current_moderator(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    user, user_role = await get_current_user(token, db)
    if user_role != 3:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return user


async def get_current_volonter(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    user, user_role = await get_current_user(token, db)
    if user_role != 2:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return user


async def get_coordinates(address: str):
    base_url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "api/1.0 (misaloka29@gmail.com)"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(base_url, params=params, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error connecting to Nominatim API")

    data = response.json()

    if not data:
        raise HTTPException(status_code=400, detail="Address not found")

    location = data[0]
    return {
        "latitude": location["lat"],
        "longitude": location["lon"]
    }


def get_password_hash(password):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


async def check_user_role(user, role_name):
    return any(role.name == role_name for role in user.roles)
