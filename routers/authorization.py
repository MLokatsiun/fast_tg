from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from business_logical import get_password_hash, verify_password, create_access_token
import models
from datetime import timedelta
from jose import JWTError, jwt
from schemas import LoginRequest, CreateCustomerBase
from business_logical import ACCESS_TOKEN_EXPIRE_MINUTES, create_refresh_token, SECRET_KEY, REFRESH_TOKEN_EXPIRE_DAYS, \
    get_coordinates

router = APIRouter()

FRONTEND_PASSWORD = "4321"
TELEGRAM_PASSWORD = "1234"


@router.post("/register/", status_code=201)
async def register_user(
        user_info: CreateCustomerBase,
        db: Session = Depends(get_db)
):
    # Перевірка наявності користувача
    existing_user = db.query(models.Customer).filter(
        models.Customer.phone_num == user_info.phone_num,
        models.Customer.tg_id == user_info.tg_id
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this phone number and TG ID already exists.")

    clients = {
        "telegram": TELEGRAM_PASSWORD,
        "frontend": FRONTEND_PASSWORD
    }

    if user_info.client not in clients:
        raise HTTPException(status_code=400, detail="Invalid client.")

    if user_info.password != clients[user_info.client]:
        raise HTTPException(status_code=400, detail="Invalid client or password.")

    if user_info.role_id == 3:
        if not user_info.location:
            raise HTTPException(status_code=400, detail="Location data is required for volunteers.")

        if user_info.location.address:
            coordinates = get_coordinates(user_info.location.address)
            latitude, longitude = coordinates["latitude"], coordinates["longitude"]

        elif user_info.location.latitude is not None and user_info.location.longitude is not None:
            latitude, longitude = user_info.location.latitude, user_info.location.longitude
        else:
            raise HTTPException(status_code=400, detail="Provide either address or both latitude and longitude.")


        existing_location = db.query(models.Locations).filter(
            models.Locations.latitude == latitude,
            models.Locations.longitude == longitude
        ).first()

        if existing_location:

            location_id = existing_location.id
        else:

            location_entry = models.Locations(
                latitude=latitude,
                longitude=longitude,
                address_name=user_info.location.address if user_info.location.address else None
            )
            db.add(location_entry)
            db.commit()
            db.refresh(location_entry)
            location_id = location_entry.id
    else:
        if user_info.location:
            raise HTTPException(status_code=400, detail="Location data is not required for beneficiaries.")
        location_id = None


    client_entry = db.query(models.Client).filter(models.Client.name == user_info.client).first()
    if not client_entry:
        raise HTTPException(status_code=400, detail="Invalid client.")


    new_user = models.Customer(
        phone_num=user_info.phone_num,
        tg_id=user_info.tg_id,
        firstname=user_info.firstname,
        lastname=user_info.lastname,
        patronymic=user_info.patronymic,
        role_id=user_info.role_id,
        client_id=client_entry.id,
        location_id=location_id
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)


    return {
        "id": new_user.id,
        "phone_num": new_user.phone_num,
        "tg_id": new_user.tg_id,
        "firstname": new_user.firstname,
        "lastname": new_user.lastname,
        "role_id": new_user.role_id,
        "location_id": location_id
    }



@router.post("/login/", status_code=200)
async def client_login(login_request: LoginRequest, db: Session = Depends(get_db)):
    if login_request.client not in ["frontend", "telegram"]:
        raise HTTPException(status_code=400, detail="Invalid client type")

    client_passwords = {
        "frontend": FRONTEND_PASSWORD,
        "telegram": TELEGRAM_PASSWORD
    }
    if login_request.password != client_passwords[login_request.client]:
        raise HTTPException(status_code=400, detail="Incorrect password for client")

    user = db.query(models.Customer).filter(
        models.Customer.id == login_request.user_id,
        models.Customer.role_id == login_request.role_id
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="User not found with provided user_id and role_id")

    token_data = {
        "user_id": user.id,
        "role_id": user.role_id,
        "client": login_request.client
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_refresh_token(data=token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh/")
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get("user_id")

        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        user = db.query(models.Customer).filter(models.Customer.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        new_access_token = create_access_token(data={"user_id": user.id, "role_id": user.role_id},
                                               expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
