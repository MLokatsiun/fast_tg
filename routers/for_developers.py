import math
from datetime import timedelta, datetime
from typing import Optional
from xmlrpc.client import DateTime

from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import func
from starlette import status
from starlette.responses import JSONResponse

from business_logical import verify_password, ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, \
    REFRESH_TOKEN_EXPIRE_DAYS, create_refresh_token
from database import get_db
import models
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import jwt
from decouple import config
from fastapi import Depends, APIRouter, Query

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()

ALGORITHM = "HS256"
SECRET_KEY = config("SECRET_KEY")
from fastapi import Body


def haversine(lat1, lon1, lat2, lon2):
    """
    Обчислює відстань між двома точками на основі їхніх координат (широта, довгота)
    за допомогою формули Haversine.
    :param lat1, lon1: координати першої точки (волонтер)
    :param lat2, lon2: координати другої точки (заявка)
    :return: відстань в кілометрах
    """
    R = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None


class TokenRequest(BaseModel):
    client: str
    password: str


@router.post("/token", response_model=Token)
async def login_for_access_token(
        token_request: TokenRequest,
        db: AsyncSession = Depends(get_db),
):
    """
        **Отримання токенів доступу та оновлення.**

        - **Ендпоінт**: `POST /token`
        - **Опис**: Дозволяє авторизувати клієнта за допомогою імені та пароля, а також отримати `access_token` і `refresh_token`.

        **Вхідні параметри:**
        - **client**: Назва клієнта (наприклад, `frontend` або `telegram`).
        - **password**: Пароль клієнта.

        **Відповідь:**
        - **200 OK**: Повертаються токени авторизації. Приклад відповіді:
          ```json
          {
              "access_token": "токен доступу",
              "refresh_token": "токен оновлення",
              "token_type": "bearer"
          }
          ```
        - **401 Unauthorized**: Якщо клієнт або пароль недійсні:
          ```json
          {
              "detail": "Invalid client type or password"
          }
          ```
        - **500 Internal Server Error**: Якщо виникла помилка на сервері:
          ```json
          {
              "detail": "Error: <error_message>"
          }
          ```

        **Примітки:**
        - `access_token` використовується для доступу до захищених ресурсів.
        - Термін дії `access_token` - 15хв`
        - Термін дії `refresh_token` - 7 днів`
        - `refresh_token` потрібен для оновлення `access_token`.
        - Обидва токени повертаються у відповіді у форматі JSON.
        """
    client_query = select(models.Client).filter(models.Client.name == token_request.client)
    client_result = await db.execute(client_query)
    client_entry = client_result.scalars().first()

    if not client_entry:
        raise HTTPException(status_code=401, detail="Invalid client type or password")

    if not verify_password(token_request.password, client_entry.password):
        raise HTTPException(status_code=401, detail="Invalid client type or password")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = create_access_token(
        data={"sub": token_request.client}, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={"sub": token_request.client}, expires_delta=refresh_token_expires
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class RefreshTokenRequest(BaseModel):
    refresh_token: str

class RefreshToken(BaseModel):
    access_token: str
    token_type: str

@router.post("/refresh", response_model=RefreshToken)
async def refresh_access_token(request: RefreshTokenRequest):
    """
        **Оновлення токену доступу.**

        - **Ендпоінт**: `POST /refresh`
        - **Опис**: Оновлення `access_token` за допомогою дійсного `refresh_token`.

        **Вхідні параметри:**
        - **refresh_token**: Токен оновлення, що передається у форматі JSON:
          ```json
          {
              "refresh_token": "ваш токен оновлення"
          }
          ```

        **Відповідь:**
        - **200 OK**: Повертається новий `access_token`. Приклад відповіді:
          ```json
          {
              "access_token": "новий токен доступу",
              "token_type": "bearer"
          }
          ```
        - **401 Unauthorized**: Якщо `refresh_token` недійсний або прострочений:
          ```json
          {
              "detail": "Invalid refresh token"
          }
          ```
        - **500 Internal Server Error**: Якщо сталася помилка на сервері:
          ```json
          {
              "detail": "Error: <error_message>"
          }
          ```

        **Примітки:**
        - Термін дії `access_token` - 15хв`.
        - Термін дії `refresh_token` - 7 днів`
        - Якщо `refresh_token` недійсний або прострочений, потрібно авторизуватися заново через `/token`.
        """
    try:
        payload = jwt.decode(request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        client_name = payload.get("sub")

        if client_name is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        new_access_token = create_access_token(
            data={"sub": client_name}, expires_delta=access_token_expires
        )

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/roles/", status_code=200)
async def get_roles(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
):
    """
    **Отримання всіх ролей.**

    - **Ендпоінт**: `GET /roles/`
    - **Опис**: Дозволяє отримати список всіх ролей в системі, незалежно від клієнта.

    **Вхідні параметри:**
    - **token**: Авторизаційний токен (Bearer Token), який використовується для перевірки доступу до ендпоінту.

    **Відповідь:**
    - **200 OK**: Повертається список всіх ролей в системі. Кожна роль містить:
      ```json
      [
          {
              "id": 1,
              "name": "Роль 1"
          },
          {
              "id": 2,
              "name": "Роль 2"
          }
      ]
      ```
    - **400 Bad Request**: Якщо токен недійсний або не надано токен:
      ```json
      {
          "detail": "Invalid token"
      }
      ```
    - **500 Internal Server Error**: Якщо сталася помилка на сервері під час виконання запиту:
      ```json
      {
          "detail": "Error: <error_message>"
      }
      ```

    **Примітки:**
    - Токен перевіряється для авторизації запиту. Якщо токен недійсний або відсутній, буде повернута помилка 400.
    - Повертається список всіх ролей, де кожна роль містить:
      - **id**: ID ролі.
      - **name**: Назва ролі.
    """

    verify_token(token)

    try:
        result = await db.execute(select(models.Roles))
        roles = result.scalars().all()

        return [{"id": role.id, "name": role.name} for role in roles]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@router.get("/categories/", status_code=200)
async def get_categories(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
):
    """
    **Отримання всіх категорій.**

    - **Ендпоінт**: `GET /categories/`
    - **Опис**: Дозволяє отримати список всіх категорій в системі, незалежно від клієнта.

    **Вхідні параметри:**
    - **token**: Авторизаційний токен (Bearer Token), який використовується для перевірки доступу до ендпоінту.

    **Відповідь:**
    - **200 OK**: Повертається список всіх категорій в системі. Кожна категорія містить:
      ```json
      [
          {
              "id": 1,
              "name": "Категорія 1",
              "parent_id": null,
              "is_active": true
          },
          {
              "id": 2,
              "name": "Категорія 2",
              "parent_id": 1,
              "is_active": true
          }
      ]
      ```
    - **401 Unauthorized**: Якщо токен недійсний або не надано токен:
      ```json
      {
          "detail": "Invalid token"
      }
      ```
    - **500 Internal Server Error**: Якщо сталася помилка на сервері під час виконання запиту:
      ```json
      {
          "detail": "Error: <error_message>"
      }
      ```

    **Примітки:**
    - Токен перевіряється, щоб авторизувати запит. Якщо токен недійсний або відсутній, буде повернута помилка 401.
    - Повертається список всіх категорій у системі, де кожна категорія містить наступні поля:
      - **id**: ID категорії.
      - **name**: Назва категорії.
      - **parent_id**: ID батьківської категорії (якщо є).
      - **is_active**: Статус категорії (активна чи ні).
    """

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_name: str = payload.get("sub")
        if client_name is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        client_result = await db.execute(
            select(models.Client).filter(models.Client.name == client_name)
        )
        client_entry = client_result.scalars().first()

        if not client_entry:
            raise HTTPException(status_code=401, detail="Invalid token")

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        result = await db.execute(select(models.Categories))
        categories = result.scalars().all()

        return [
            {"id": category.id, "name": category.name, "parent_id": category.parent_id, "is_active": category.is_active}
            for category in categories
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@router.get("/customers/", status_code=200)
async def get_customers(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
):
    """
    **Отримання користувачів для клієнта.**

    - **Ендпоінт**: POST `/customers/`
    - **Опис**: Дозволяє отримати список користувачів для вказаного клієнта.
    - **Вхідні параметри**:
      - **token**: Авторизаційний токен (Bearer Token).
      - **db**: Сесія бази даних для виконання запиту.

    **Відповідь:**
    - **200**: Список користувачів для клієнта, які активні та не верифіковані:
      ```json
      [
        {
          "id": 1,
          "phone_num": "1234567890",
          "firstname": "John",
          "lastname": "Doe",
          "role": 2
        },
        {
          "id": 2,
          "phone_num": "9876543210",
          "firstname": "Jane",
          "lastname": "Smith",
          "role": 3
        }
      ]
      ```
    - **401**: Помилка авторизації. Токен недійсний або не надано токен:
      ```json
      {
          "detail": "Invalid token"
      }
      ```
    - **500**: Помилка сервера або бази даних:
      ```json
      {
          "detail": "Error: ..."
      }
      ```

    **Примітки:**
    - Для доступу до списку користувачів необхідно вказати правильний токен.
    - Повертається лише список активних, не верифікованих користувачів.
    """

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_name: str = payload.get("sub")
        if client_name is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        client_query = select(models.Client).filter(models.Client.name == client_name)
        client_result = await db.execute(client_query)
        client_entry = client_result.scalars().first()

        if not client_entry:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:

        customer_query = select(models.Customer).filter(models.Customer.client_id == client_entry.id)
        customer_result = await db.execute(customer_query)
        customers = customer_result.scalars().all()

        response = []
        for customer in customers:
            if customer.is_verified:
                continue
            if not customer.is_active:
                continue

            response.append({
                "id": customer.id,
                "phone_num": customer.phone_num,
                "firstname": customer.firstname,
                "lastname": customer.lastname,
                "role": customer.role_id
            })

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@router.post('/applications/', status_code=200)
async def get_applications_for_developers(
        token: str = Depends(oauth2_scheme),
        type: str = Query(..., description="Тип заявок: 'available', 'in_progress', 'finished'"),
        category_ids: list[int] = Body(None, description="Список ID категорій для фільтрації"),
        days_valid: int = Body(None, description="Фільтр за кількістю днів дійсності заявки"),
        db: AsyncSession = Depends(get_db)
):
    """
    **Отримання списку заявок за типом для розробників із додатковими фільтрами**

    - **Ендпоінт**: `POST /applications/`
    - **Опис**: Повертає список заявок на основі їх статусу (доступні, у прогресі, завершені)
      з можливістю фільтрації за категоріями та за кількістю днів дійсності.
      Заявки фільтруються за `active_to`, щоб показувати лише ті, що дійсні.

    **Вхідні параметри:**
    - **token**: Авторизаційний токен (Bearer Token), необхідний для перевірки доступу.
    - **type**: Тип заявок, які потрібно повернути. Можливі значення:
      - `'available'`: доступні заявки.
      - `'in_progress'`: заявки, що знаходяться в процесі виконання.
      - `'finished'`: завершені заявки.
    - **category_ids**: Список ID категорій для фільтрації заявок.
    - **days_valid**: Фільтр за кількістю днів дійсності заявки. Якщо параметр задано, заявки будуть фільтруватися за `active_to`, щоб показувати лише ті, що будуть дійсні до вказаної кількості днів.

    **Відповідь:**
    - **200 OK**: Повертається список заявок, що відповідають вказаним критеріям фільтрації:
      ```json
      [
          {
              "id": 1,
              "description": "Description of the application",
              "category_id": 2,
              "location": {
                  "latitude": 50.4501,
                  "longitude": 30.5236,
                  "address_name": "Kyiv"
              },
              "creator": {
                  "id": 1,
                  "first_name": "John",
                  "phone_num": "1234567890"
              },
              "executor": {
                  "id": 2,
                  "first_name": "Alice",
                  "phone_num": "0987654321"
              },
              "is_in_progress": false,
              "is_done": true,
              "date_at": "2024-12-21T12:00:00",
              "active_to": "2024-12-25T12:00:00"
          }
      ]
      ```
    - **404 Not Found**: Якщо тип заявок не є допустимим.
      ```json
      {
          "detail": "Invalid application type"
      }
      ```
    - **500 Internal Server Error**: Якщо сталася помилка на сервері або під час виконання запиту.
      ```json
      {
          "detail": "Error: <error_message>"
      }
      ```

    **Примітки:**
    - Для отримання даних потрібен дійсний токен.
    - Запит повертає список заявок з додатковою інформацією:
      - **id**: ID заявки.
      - **description**: Опис заявки.
      - **category_id**: ID категорії заявки.
      - **location**: Інформація про місце розташування заявки (широта, довгота, адреса).
      - **creator**: Інформація про користувача, який створив заявку.
      - **executor**: Інформація про волонтера, який виконує заявку (якщо є).
      - **is_in_progress**: Статус заявки (в процесі чи ні).
      - **is_done**: Чи завершена заявка.
      - **date_at**: Дата і час створення заявки.
      - **active_to**: Термін дії заявки.

    **Фільтрація:**
    - Фільтрація за типом заявки (`available`, `in_progress`, `finished`).
    - Можливість фільтрації за категоріями, якщо вказані їх ID.
    - Можливість фільтрації за кількістю днів дійсності заявки через параметр `days_valid`.

    """

    client_name = verify_token(token)

    client_query = select(models.Client).filter(models.Client.name == client_name)
    client_result = await db.execute(client_query)
    client_entry = client_result.scalars().first()

    if not client_entry:
        raise HTTPException(status_code=400, detail="Invalid client type")

    try:
        query = select(models.Applications, models.Locations, models.Customer).join(
            models.Locations, models.Applications.location_id == models.Locations.id
        ).join(
            models.Customer, models.Applications.creator_id == models.Customer.id
        )

        if type == 'available':
            query = query.filter(
                models.Applications.is_done.is_(False),
                models.Applications.is_in_progress.is_(False),
                models.Applications.is_active.is_(True)
            )
        elif type == 'in_progress':
            query = query.filter(
                models.Applications.is_in_progress.is_(True),
                models.Applications.is_done.is_(False),
                models.Applications.is_active.is_(True)
            )
        elif type == 'finished':
            query = query.filter(
                models.Applications.is_done.is_(True),
                models.Applications.is_active.is_(True)
            )
        else:
            raise HTTPException(status_code=404, detail="Invalid application type")

        if category_ids:
            if 0 not in category_ids:
                query = query.filter(models.Applications.category_id.in_(category_ids))

        if days_valid is not None and days_valid > 0:
            from sqlalchemy import cast, DateTime
            current_date = datetime.utcnow()
            valid_until = current_date + timedelta(days=days_valid)
            query = query.filter(cast(models.Applications.active_to, DateTime) <= valid_until)

        current_date_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        query = query.filter(models.Applications.date_at > current_date_str)

        result = await db.execute(query)
        applications = result.fetchall()

        response_data = []
        for application in applications:
            executor_data = None
            if application.Applications.executor_id:
                executor_query = select(models.Customer).filter(
                    models.Customer.id == application.Applications.executor_id)
                executor_result = await db.execute(executor_query)
                executor = executor_result.scalar()
                if executor:
                    executor_data = {
                        "id": executor.id,
                        "first_name": executor.firstname,
                        "phone_num": executor.phone_num
                    }

            response_data.append({
                "id": application.Applications.id,
                "description": application.Applications.description,
                "category_id": application.Applications.category_id,
                "location": {
                    "latitude": application.Locations.latitude,
                    "longitude": application.Locations.longitude,
                    "address_name": application.Locations.address_name
                },
                "creator": {
                    "id": application.Customer.id,
                    "first_name": application.Customer.firstname,
                    "phone_num": application.Customer.phone_num
                },
                "executor": executor_data,
                "is_in_progress": application.Applications.is_in_progress,
                "is_done": application.Applications.is_done,
                "date_at": application.Applications.date_at,
                "active_to": application.Applications.active_to
            })

        if not response_data:
            return JSONResponse(content={"detail": "No applications found."}, status_code=200)

        return JSONResponse(content=response_data, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/rating/", status_code=200)
async def get_volunteer_rating(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
):
    """
    **Отримання рейтингу волонтерів для клієнта.**

    - **Ендпоінт**: POST `/rating/`
    - **Опис**: Дозволяє отримати список волонтерів, відсортованих за кількістю закритих заявок.
    - **Вхідні параметри**:
      - **token**: Авторизаційний токен (Bearer Token).
      - **db**: Сесія бази даних для виконання запиту.

    **Відповідь:**
    - **200**: Список волонтерів із кількістю закритих заявок:
      ```json
      [
        {
          "volunteer_name": "Ім'я Прізвище",
          "closed_app_count": 5
        },
        ...
      ]
      ```
    - **401**: Невірний токен:
      ```json
      {
          "detail": "Invalid token"
      }
      ```
    - **500**: Помилка сервера або бази даних:
      ```json
      {
          "detail": "Error: ..."
      }
      ```

    **Примітки:**
    - Перевіряється відповідність токену.
    - Повертається список волонтерів, які закрили заявки зі статусом `is_done = True`.
    """

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_name: str = payload.get("sub")
        if client_name is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        client_query = select(models.Client).filter(models.Client.name == client_name)
        client_result = await db.execute(client_query)
        client_entry = client_result.scalars().first()

        if not client_entry:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        query = (
            select(models.Customer, func.count(models.Applications.id).label('closed_app_count'))
            .join(models.Applications, models.Applications.executor_id == models.Customer.id)
            .filter(models.Applications.is_done == True)
            .group_by(models.Customer.id)
            .order_by(func.count(models.Applications.id).desc())
        )

        results = await db.execute(query)
        volunteer_data = results.all()

        response = [{
            "volunteer_name": f"{volunteer.firstname} {volunteer.lastname}",
            "closed_app_count": closed_app_count
        } for volunteer, closed_app_count in volunteer_data]

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@router.get('/applications/summary', status_code=200)
async def get_applications_summary(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
):
    """
        **Отримання зведення по заявкам та волонтерам**

        - **Ендпоінт**: `GET /applications/summary`
        - **Опис**: Повертає зведену інформацію про заявки та волонтерів:
          - Загальну кількість заявок.
          - Кількість волонтерів з роль `role_id=2`.
          - Кількість завершених (закритих) та неактивних заявок (`is_done=True` і `is_active=False`).

        **Вхідні параметри:**
        - **token**: Авторизаційний токен (Bearer Token), який необхідний для перевірки доступу до даних.

        **Відповідь:**
        - **200 OK**: Повертається зведена інформація по заявках та волонтерам у вигляді JSON-об'єкта:
          ```json
          {
              "total_applications": 100,  // Загальна кількість заявок
              "volunteers_count": 25,     // Кількість волонтерів з role_id=2
              "completed_inactive_applications": 10  // Кількість завершених та неактивних заявок
          }
          ```
        - **401 Unauthorized**: Якщо токен недійсний або не надано токен:
          ```json
          {
              "detail": "Invalid or expired token"
          }
          ```
        - **500 Internal Server Error**: Якщо сталася помилка сервера або бази даних:
          ```json
          {
              "detail": "Error: <error_message>"
          }
          ```

        **Примітки:**
        - Токен перевіряється перед отриманням даних.
        - Запит повертає три основні показники:
          1. **total_applications**: Загальна кількість заявок.
          2. **volunteers_count**: Кількість волонтерів з роллю `role_id=2`.
          3. **completed_inactive_applications**: Кількість завершених заявок, які більше не активні (`is_done=True`, `is_active=False`).

        """
    try:
        user = verify_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:

        total_applications_query = select(func.count()).select_from(models.Applications)
        total_applications_result = await db.execute(total_applications_query)
        total_applications = total_applications_result.scalar()

        volunteers_query = select(func.count()).select_from(models.Customer).filter(models.Customer.role_id == 2)
        volunteers_result = await db.execute(volunteers_query)
        volunteers_count = volunteers_result.scalar()

        completed_inactive_query = select(func.count()).select_from(models.Applications).filter(
            models.Applications.is_done.is_(True),
            models.Applications.is_active.is_(False)
        )
        completed_inactive_result = await db.execute(completed_inactive_query)
        completed_inactive_count = completed_inactive_result.scalar()

        return JSONResponse(
            content={
                "total_applications": total_applications,
                "volunteers_count": volunteers_count,
                "completed_inactive_applications": completed_inactive_count
            },
            status_code=200
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
