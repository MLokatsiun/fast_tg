from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from business_logical import get_password_hash, verify_password, create_access_token
import models
from datetime import timedelta
from jose import JWTError, jwt
from schemas import RegisterRequest, LoginRequest
from business_logical import ACCESS_TOKEN_EXPIRE_MINUTES, create_refresh_token, SECRET_KEY
router = APIRouter()


@router.post("/register/")
async def register_user(register_request: RegisterRequest, db: Session = Depends(get_db)):
    """
        Register a new user in the system.

        Args:
            register_request (RegisterRequest): The request containing the user's phone number, role, and password.
            db (Session): The database session dependency.

        Raises:
            HTTPException: If the user is already registered.

        Returns:
            dict: A message confirming successful registration and the new user's ID.
    """
    existing_user = db.query(models.User).filter(models.User.phone_num == register_request.phone_num).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already registered.")


    hashed_password = get_password_hash(register_request.password)


    new_user = models.User(
        phone_num=register_request.phone_num,
        role=register_request.role,
        password=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully", "user_id": new_user.id}

@router.post("/login/")
async def login(login_request: LoginRequest, db: Session = Depends(get_db)):
    """
        Authenticate a user and return access and refresh tokens.

        Args:
            login_request (LoginRequest): The request containing the user's phone number and password.
            db (Session): The database session dependency.

        Raises:
            HTTPException: If the phone number or password is incorrect.

        Returns:
            dict: Access token, refresh token, and user's role.
    """
    user = db.query(models.User).filter(models.User.phone_num == login_request.phone_num).first()
    if not user or not verify_password(login_request.password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect phone number or password")

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": user.role
    }

@router.post("/refresh/")
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    """
        Refresh the access token using the provided refresh token.

        Args:
            refresh_token (str): The refresh token for the user.
            db (Session): The database session dependency.

        Raises:
            HTTPException: If the refresh token is invalid or the user is not found.

        Returns:
            dict: A new access token and the token type.
    """
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=['HS256'])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        new_access_token = create_access_token(data={"sub": str(user.id)}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")