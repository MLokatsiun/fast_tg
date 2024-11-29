from database import get_db
from business_logical import create_access_token
import models
from datetime import timedelta
from jose import JWTError, jwt
from schemas import LoginRequest
from business_logical import ACCESS_TOKEN_EXPIRE_MINUTES, create_refresh_token, SECRET_KEY, get_coordinates
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from schemas import CreateCustomerBase, RefreshTokenRequest

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()


@router.post("/register/", status_code=201)
async def register_user(
        user_info: CreateCustomerBase,
        db: AsyncSession = Depends(get_db)
):
    """
    **Реєстрація нового користувача.**

    - **Ендпоінт**: POST `/register/`
    - **Опис**: Дозволяє зареєструвати нового користувача у системі як волонтера чи бенефіціара.
    - **Вхідні параметри**:
      - **user_info**: Дані для реєстрації користувача:
        ```json
        {
            "phone_num": "380123456789",
            "tg_id": "123456789",
            "firstname": "Ім'я",
            "lastname": "Прізвище",
            "patronymic": "По батькові",
            "role_id": 1,
            "client": "Назва клієнта",
            "password": "Пароль",
            "location": {
                "address": "Адреса (для волонтера)",
                "latitude": 50.4501,
                "longitude": 30.5234
            }
        }
        ```
        - **phone_num**: Номер телефону у форматі `380123456789`.
        - **tg_id**: Telegram ID користувача (9-10 цифр).
        - **firstname**: Ім'я користувача.
        - **lastname**: (Опціонально) Прізвище користувача.
        - **patronymic**: (Опціонально) По батькові користувача.
        - **role_id**: ID ролі користувача (1 — бенефіціар, 2 — волонтер).
        - **client**: Назва клієнта, з яким пов'язаний користувач.
        - **password**: Пароль клієнта.
        - **location**: (Опціонально) Інформація про локацію (для волонтера).

    - **Обмеження**:
      - Для волонтерів обов'язково вказувати локацію (або адресу, або координати).
      - Для бенефіціарів локація не потрібна.

    **Відповідь:**
    - **201**: Успішна реєстрація користувача. Повертається інформація про створеного користувача:
        ```json
        {
            "id": 1,
            "phone_num": "380123456789",
            "tg_id": "123456789",
            "firstname": "Ім'я",
            "lastname": "Прізвище",
            "role_id": 1,
            "location_id": null,
            "is_verified": false
        }
        ```
    - **400**: Помилка вхідних даних.
      - Користувач з таким номером телефону або TG ID вже існує:
        ```json
        {
            "detail": "User with this phone number and TG ID already exists and is active."
        }
        ```
      - Невалідний клієнт:
        ```json
        {
            "detail": "Invalid client."
        }
        ```
      - Локація не вказана для волонтера або дані локації некоректні:
        ```json
        {
            "detail": "Location data is required for volunteers."
        }
        ```
    - **500**: Помилка сервера чи бази даних:
        ```json
        {
            "detail": "Database error: ..."
        }
        ```

    **Примітки:**
    - Після створення новий користувач буде не перевіреним (`is_verified: false`).
    - Система дозволяє оновлювати профілі неактивних користувачів, якщо їх перевірка раніше була відхилена.
    """
    try:

        role_check_result = await db.execute(
            select(models.Roles).filter(models.Roles.id == user_info.role_id)
        )
        role_entry = role_check_result.scalars().first()
        if not role_entry:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role_id: {user_info.role_id}. Role does not exist in the Roles table."
            )

        tg_id_check_result = await db.execute(
            select(models.Customer).filter(
                models.Customer.tg_id == user_info.tg_id,
                models.Customer.role_id == user_info.role_id,
                models.Customer.is_active == True
            )
        )
        existing_user_with_tg_id = tg_id_check_result.scalars().first()
        if existing_user_with_tg_id:
            raise HTTPException(
                status_code=400,
                detail=f"User with TG ID {user_info.tg_id} already exists for role ID {user_info.role_id} and is active."
            )

        phone_check_result = await db.execute(
            select(models.Customer).filter(
                models.Customer.phone_num == user_info.phone_num,
                models.Customer.role_id == user_info.role_id,
                models.Customer.is_active == True
            )
        )
        existing_user_with_phone = phone_check_result.scalars().first()
        if existing_user_with_phone:
            raise HTTPException(
                status_code=400,
                detail=f"User with phone number {user_info.phone_num} already exists for role ID {user_info.role_id} and is active."
            )

        client_result = await db.execute(
            select(models.Client).filter(models.Client.name == user_info.client)
        )
        client_entry = client_result.scalars().first()
        if not client_entry:
            raise HTTPException(status_code=400, detail="Invalid client.")

        location_id = None
        if user_info.role_id == 2:
            if not user_info.location:
                raise HTTPException(status_code=400, detail="Location data is required for volunteers.")

            if user_info.location.address:
                coordinates = await get_coordinates(address=user_info.location.address)
                latitude = coordinates["latitude"]
                longitude = coordinates["longitude"]
                address_name = user_info.location.address
            elif user_info.location.latitude is not None and user_info.location.longitude is not None:
                latitude = float(user_info.location.latitude)
                longitude = float(user_info.location.longitude)

                reverse_coordinates = await get_coordinates(lat=latitude, lng=longitude)
                address_name = reverse_coordinates.get("address", "Unknown Address")
            else:
                raise HTTPException(status_code=400, detail="Provide either address or both latitude and longitude.")

            location_query = select(models.Locations).filter(
                models.Locations.latitude == latitude,
                models.Locations.longitude == longitude,
                models.Locations.address_name == address_name
            )
            location_result = await db.execute(location_query)
            existing_location = location_result.scalars().first()

            if existing_location:
                location_id = existing_location.id
            else:
                location_entry = models.Locations(
                    latitude=latitude,
                    longitude=longitude,
                    address_name=address_name
                )
                db.add(location_entry)
                await db.commit()
                await db.refresh(location_entry)
                location_id = location_entry.id
        else:
            if user_info.location:
                raise HTTPException(status_code=400, detail="Location data is not required for beneficiaries.")

        new_user = models.Customer(
            phone_num=user_info.phone_num,
            tg_id=user_info.tg_id,
            firstname=user_info.firstname,
            lastname=user_info.lastname,
            patronymic=user_info.patronymic,
            role_id=user_info.role_id,
            client_id=client_entry.id,
            location_id=location_id,
            is_active=True,
            is_verified=False
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return {
            "id": new_user.id,
            "phone_num": new_user.phone_num,
            "tg_id": new_user.tg_id,
            "firstname": new_user.firstname,
            "lastname": new_user.lastname,
            "role_id": new_user.role_id,
            "location_id": location_id,
            "is_verified": new_user.is_verified
        }

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")



@router.post("/login/", status_code=200)
async def client_login(login_request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    **Вхід користувача в систему.**

    - **Ендпоінт**: POST `/login/`
    - **Опис**: Дозволяє аутентифікувати користувача та отримати токени доступу.

    - **Вхідні параметри**:
      - **login_request**: Дані для входу користувача:
        ```json
        {
            "tg_id": "123456789",
            "role_id": 1,
            "client": "Назва клієнта",
            "password": "Пароль"
        }
        ```
        - **tg_id**: Telegram ID користувача.
        - **role_id**: ID ролі користувача (1 — бенефіціар, 2 — волонтер).
        - **client**: Назва клієнта, з яким пов'язаний користувач.
        - **password**: Пароль клієнта для аутентифікації.

    - **Обмеження**:
      - Користувач має бути активним (`is_active: true`).
      - Клієнт має бути валідним і зареєстрованим у системі.

    **Відповідь:**
    - **200**: Успішний вхід. Повертаються токени доступу:
        ```json
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR...",
            "token_type": "bearer"
        }
        ```
      - **access_token**: Токен доступу для аутентифікації запитів.
      - **refresh_token**: Токен для оновлення токена доступу.
      - **token_type**: Тип токена (bearer).

    - **400**: Помилка вхідних даних.
      - Невалідний клієнт:
        ```json
        {
            "detail": "Invalid client type"
        }
        ```
      - Невірний пароль:
        ```json
        {
            "detail": "Incorrect password for client"
        }
        ```
      - Користувач не знайдений:
        ```json
        {
            "detail": "User not found with provided TG ID and role ID"
        }
        ```

    - **403**: Профіль користувача не активний:
        ```json
        {
            "detail": "User profile is not active. Please contact support."
        }
        ```

    **Примітки:**
    - **access_token** діє протягом часу, визначеного параметром `ACCESS_TOKEN_EXPIRE_MINUTES`.
    - **refresh_token** можна використовувати для оновлення токена доступу.
    - Якщо виникли проблеми з доступом, зверніться до технічної підтримки.
    """

    client_result = await db.execute(select(models.Client).filter(models.Client.name == login_request.client))
    client_entry = client_result.scalars().first()
    if not client_entry:
        raise HTTPException(status_code=400, detail="Invalid client type")

    if not pwd_context.verify(login_request.password, client_entry.password):
        raise HTTPException(status_code=400, detail="Incorrect password for client")



    user_result = await db.execute(select(models.Customer).filter(
        models.Customer.tg_id == login_request.tg_id,
        models.Customer.role_id == login_request.role_id
    ))
    user = user_result.scalars().first()

    if not user:
        raise HTTPException(status_code=400, detail="User not found with provided TG ID and role ID")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User profile is not active. Please contact support.")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="User is not verified. Please contact support.")

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
async def refresh_token(
        token_request: RefreshTokenRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    **Оновлення токена доступу.**

    - **Ендпоінт**: POST `/refresh/`
    - **Опис**: Дозволяє оновити токен доступу за допомогою дійсного refresh-токена.

    - **Вхідні параметри**:
      - **refresh_token**: Токен оновлення, виданий під час аутентифікації:
        ```json
        {
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR...<your-refresh-token>..."
        }
        ```
      - **refresh_token** має бути дійсним і виданим для існуючого користувача.

    **Відповідь**:
    - **200**: Успішне оновлення токена доступу. Повертається новий токен:
        ```json
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR...<new-access-token>...",
            "token_type": "bearer"
        }
        ```
      - **access_token**: Новий токен доступу для аутентифікації запитів.
      - **token_type**: Тип токена (bearer).

    - **401**: Помилка авторизації.
      - Недійсний refresh-токен:
        ```json
        {
            "detail": "Invalid refresh token"
        }
        ```
      - Користувач не знайдений:
        ```json
        {
            "detail": "User not found"
        }
        ```

    **Примітки**:
    - Новий **access_token** діє протягом часу, визначеного параметром `ACCESS_TOKEN_EXPIRE_MINUTES`.
    - Якщо refresh-токен недійсний або закінчився його термін дії, необхідно повторно пройти процес аутентифікації.
    - У разі виникнення проблем із оновленням токена зверніться до технічної підтримки.
    """
    try:
        refresh_token = token_request.refresh_token

        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get("user_id")

        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")


        user_result = await db.execute(select(models.Customer).filter(models.Customer.id == user_id))
        user = user_result.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        if not user.is_verified:
            raise HTTPException(status_code=403, detail="User is not verified. Please contact support.")

        new_access_token = create_access_token(data={"user_id": user.id, "role_id": user.role_id},
                                               expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

