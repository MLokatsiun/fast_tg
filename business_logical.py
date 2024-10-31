from fastapi import Depends, HTTPException, status, requests
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
import models
import requests
from passlib.context import CryptContext
from database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = '884e824f5571d0acf70e2cc8600c2deb68dcc302c2402a1838ef2b38e9b22ade'
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(data: dict, expires_delta: timedelta):
    """
        Generates a new access token with an expiration time.

        Args:
            data (dict): Data to be encoded in the token.
            expires_delta (timedelta): Token expiration time.

        Returns:
            str: A JWT access token string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")


def create_refresh_token(data: dict):
    """
        Generates a refresh token with a predefined expiration date.

        Args:
            data (dict): Data to be encoded in the token.

        Returns:
            str: A JWT refresh token string.
    """
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")


def get_current_user(token: str, db: Session):
    """
        Retrieves the current user from the token.

        Args:
            token (str): The JWT token for user authentication.
            db (Session): The database session dependency.

        Raises:
            HTTPException: If the token is invalid or the user is not found.

        Returns:
            tuple: A tuple containing the user object and user role.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        user_role = payload.get("role")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        user = db.query(models.Customer).filter(models.Customer.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user, user_role
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_beneficiary(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
        Retrieves the current beneficiary user from the token.

        Args:
            token (str): The JWT token for user authentication.
            db (Session): The database session dependency.

        Raises:
            HTTPException: If the user does not have the 'beneficiary' role.

        Returns:
            User: The beneficiary user object.
    """
    user, user_role = get_current_user(token, db)
    if user_role != "beneficiary":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return user


def get_current_moderator(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
        Retrieves the current moderator user from the token.

        Args:
            token (str): The JWT token for user authentication.
            db (Session): The database session dependency.

        Raises:
            HTTPException: If the user does not have the 'moderator' role.

        Returns:
            User: The moderator user object.
    """
    user, user_role = get_current_user(token, db)
    if user_role != "moderator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return user


def get_current_volonter(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
        Retrieves the current volunteer user from the token.

        Args:
            token (str): The JWT token for user authentication.
            db (Session): The database session dependency.

        Raises:
            HTTPException: If the user does not have the 'volunteer' role.

        Returns:
            User: The volunteer user object.
    """
    user, user_role = get_current_user(token, db)
    if user_role != "volunteer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return user


def get_coordinates(address: str):
    """
    Uses the Nominatim API to obtain latitude and longitude from an address.

    Args:
        address (str): The address to be geocoded.

    Returns:
        dict: A dictionary containing "latitude" and "longitude".

    Raises:
        HTTPException: If the Nominatim API request fails or the address is not found.
    """
    base_url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }

    response = requests.get(base_url, params=params)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Помилка під час з'єднання з Nominatim API")

    data = response.json()

    if not data:
        raise HTTPException(status_code=400, detail="Адресу не знайдено")

    location = data[0]
    return {
        "latitude": location["lat"],
        "longitude": location["lon"]
    }


def get_password_hash(password):
    """
        Hashes the user's password.

        Args:
            password (str): The plain password.

        Returns:
            str: The hashed password.
    """
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    """
        Verifies that the plain password matches the hashed password.

        Args:
            plain_password (str): The plain password.
            hashed_password (str): The hashed password.

        Returns:
            bool: True if passwords match, otherwise False.
    """
    return pwd_context.verify(plain_password, hashed_password)


def check_user_role(user, role_name):
    """
        Checks if the user has a specific role.

        Args:
            user: The user to check.
            role_name (str): The role name to check against.

        Returns:
            bool: True if the user's role matches, otherwise False.
        """
    return any(role.name == role_name for role in user.roles)
