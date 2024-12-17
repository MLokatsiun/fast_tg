import math

from sqlalchemy import func
from starlette.responses import JSONResponse

from database import get_db
import models
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from schemas import ForDevelopers, ApplicationsList
from typing import List, Optional
from fastapi import Depends, APIRouter, Query
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()

from fastapi import Body

def haversine(lat1, lon1, lat2, lon2):
    """
    Обчислює відстань між двома точками на основі їхніх координат (широта, довгота)
    за допомогою формули Haversine.
    :param lat1, lon1: координати першої точки (волонтер)
    :param lat2, lon2: координати другої точки (заявка)
    :return: відстань в кілометрах
    """
    R = 6371  # Радіус Землі в кілометрах
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

@router.post("/roles/", status_code=200)
async def get_roles(
        for_developers: ForDevelopers = Body(...),
        db: AsyncSession = Depends(get_db)
):
    """
        **Отримання ролей для клієнта.**

        - **Ендпоінт**: POST `/roles/`
        - **Опис**: Дозволяє отримати список ролей для вказаного клієнта.
        - **Вхідні параметри**:
          - **for_developers**: Дані для авторизації:
            ```json
            {
                "client": "Назва клієнта",
                "password": "Пароль клієнта"
            }
            ```
            - **client**: Назва клієнта, для якого запитуються ролі.
            - **password**: Пароль клієнта для перевірки доступу.

        **Відповідь:**
        - **200**: Список ролей для клієнта. Повертається масив ролей:
            ```json
            [
                {
                    "id": 1,
                    "name": "Role Name"
                },
                {
                    "id": 2,
                    "name": "Another Role"
                }
            ]
            ```
        - **400**: Помилка вхідних даних. Наприклад, невірний клієнт або неправильний пароль:
            ```json
            {
                "detail": "Invalid client type"
            }
            ```
        - **500**: Помилка сервера або бази даних:
            ```json
            {
                "detail": "Error: ..."
            }
            ```

        **Примітки:**
        - Для доступу до ролей необхідно вказати правильний клієнт та пароль.
        """
    client_result = await db.execute(
        select(models.Client).filter(models.Client.name == for_developers.client)
    )
    client_entry = client_result.scalars().first()
    if not client_entry:
        raise HTTPException(status_code=400, detail="Invalid client type")

    if not pwd_context.verify(for_developers.password, client_entry.password):
        raise HTTPException(status_code=400, detail="Incorrect password for client")

    result = await db.execute(select(models.Roles))
    roles = result.scalars().all()
    return [{"id": role.id, "name": role.name} for role in roles]


@router.post("/categories/", status_code=200)
async def get_categories(
        for_developers: ForDevelopers = Body(...),
        db: AsyncSession = Depends(get_db)
):
    """
        **Отримання категорій для клієнта.**

        - **Ендпоінт**: POST `/categories/`
        - **Опис**: Дозволяє отримати список категорій для вказаного клієнта.
        - **Вхідні параметри**:
          - **for_developers**: Дані для авторизації:
            ```json
            {
                "client": "Назва клієнта",
                "password": "Пароль клієнта"
            }
            ```
            - **client**: Назва клієнта, для якого запитуються категорії.
            - **password**: Пароль клієнта для перевірки доступу.

        **Відповідь:**
        - **200**: Список категорій для клієнта. Повертається масив категорій:
            ```json
            [
                {
                    "id": 1,
                    "name": "Category Name",
                    "parent_id": 0,
                    "is_active": true
                },
                {
                    "id": 2,
                    "name": "Another Category",
                    "parent_id": 1,
                    "is_active": false
                }
            ]
            ```
        - **400**: Помилка вхідних даних. Наприклад, невірний клієнт або неправильний пароль:
            ```json
            {
                "detail": "Invalid client type"
            }
            ```
        - **500**: Помилка сервера або бази даних:
            ```json
            {
                "detail": "Error: ..."
            }
            ```

        **Примітки:**
        - Для доступу до категорій необхідно вказати правильний клієнт та пароль.
        """
    client_result = await db.execute(
        select(models.Client).filter(models.Client.name == for_developers.client)
    )
    client_entry = client_result.scalars().first()
    if not client_entry:
        raise HTTPException(status_code=400, detail="Invalid client type")

    if not pwd_context.verify(for_developers.password, client_entry.password):
        raise HTTPException(status_code=400, detail="Incorrect password for client")

    result = await db.execute(select(models.Categories))
    categories = result.scalars().all()
    return [
        {
            "id": category.id,
            "name": category.name,
            "parent_id": category.parent_id,
            "is_active": category.is_active,
        }
        for category in categories
    ]


@router.post("/customers/", status_code=200)
async def get_customers(
        for_developers: ForDevelopers = Body(...),
        db: AsyncSession = Depends(get_db)
):
    """
    **Отримання користувачів для клієнта.**

    - **Ендпоінт**: POST `/customers/`
    - **Опис**: Дозволяє отримати список користувачів для вказаного клієнта.
    - **Вхідні параметри**:
      - **for_developers**: Дані для авторизації:
        ```json
        {
            "client": "Назва клієнта",
            "password": "Пароль клієнта"
        }
        ```
        - **client**: Назва клієнта для якого запитуються користувачі.
        - **password**: Пароль клієнта для перевірки доступу.
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
    - **400**: Помилка вхідних даних. Наприклад, невірний клієнт або неправильний пароль:
      ```json
      {
          "detail": "Invalid client type"
      }
      ```
    - **500**: Помилка сервера або бази даних:
      ```json
      {
          "detail": "Error: ..."
      }
      ```

    **Примітки:**
    - Для доступу до списку користувачів необхідно вказати правильний клієнт та пароль.
    - Повертається лише список активних, не верифікованих користувачів.
    """
    client_query = select(models.Client).filter(models.Client.name == for_developers.client)
    client_result = await db.execute(client_query)
    client_entry = client_result.scalars().first()

    if not client_entry:
        raise HTTPException(status_code=400, detail="Invalid client type")

    if not pwd_context.verify(for_developers.password, client_entry.password):
        raise HTTPException(status_code=400, detail="Incorrect password for client")

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

@router.post('/applications/', status_code=200)
async def get_applications_for_developers(
        client: str = Body(...),
        password: str = Body(...),
        type: str = Query(..., description="Тип заявок: 'available', 'in_progress', 'finished'"),
        category_ids: list[int] = Body(None, description="Список ID категорій для фільтрації"),
        days_valid: int = Body(None, description="Фільтр за кількістю днів дійсності заявки"),
        db: AsyncSession = Depends(get_db)
):
    """
    **Отримати список заявок за типом для розробників із додатковими фільтрами.**

    - **Ендпоінт**: POST `/applications/`
    - **Опис**: Повертає список заявок на основі їх статусу (доступні, у прогресі, завершені)
      з можливістю фільтрації за категоріями або тривалістю дійсності заявки.

    **Вхідні параметри**:
    - **client** (*str*): Ім'я клієнта для авторизації.
    - **password** (*str*): Пароль для клієнта.
    - **type** (*str*): Тип заявок для отримання:
      - `'available'`: Заявки, які доступні для виконання.
      - `'in_progress'`: Заявки, які виконуються.
      - `'finished'`: Заявки, які завершені.
    - **category_ids** (*list[int]*, необов'язковий): Список ID категорій для фільтрації заявок.
    - **days_valid** (*int*, необов'язковий): Фільтр заявок, які залишаються дійсними на певну кількість днів.
    - **db** (*AsyncSession*): Підключення до бази даних.

    **Логіка обробки**:
    1. Перевірка клієнта:
       - Клієнт повинен існувати у базі даних.
       - Пароль клієнта перевіряється через хешування.
    2. Фільтрація заявок:
       - Залежно від типу заявки (`available`, `in_progress`, `finished`).
       - За необхідності враховується список категорій (`category_ids`).
       - За необхідності враховується термін дійсності (`days_valid`).
    3. Повернення інформації про заявки, включаючи:
       - Локацію заявки.
       - Інформацію про автора заявки.
       - Інформацію про виконавця, якщо такий є.

    **Відповіді**:
    - **200 OK**: Успішний запит із списком заявок:
      ```json
      [
        {
          "id": 1,
          "description": "Допомогти з доставкою продуктів",
          "category_id": 3,
          "location": {
            "latitude": 50.4501,
            "longitude": 30.5234,
            "address_name": "Київ, вул. Хрещатик, 1"
          },
          "creator": {
            "id": 12,
            "first_name": "Іван",
            "phone_num": "1234567890"
          },
          "executor": {
            "id": 8,
            "first_name": "Петро",
            "phone_num": "0987654321"
          },
          "is_in_progress": true,
          "is_done": false,
          "date_at": "2024-12-01T12:00:00Z",
          "active_to": "2024-12-17T12:00:00Z"
        }
      ]
      ```
    - **200 OK**: Якщо заявки не знайдено:
      ```json
      {
          "detail": "No applications found."
      }
      ```
    - **400 Bad Request**: Невірний клієнт або неправильний пароль:
      ```json
      {
          "detail": "Invalid client type"
      }
      ```
    - **404 Not Found**: Якщо вказано неправильний тип заявки:
      ```json
      {
          "detail": "Invalid application type"
      }
      ```
    - **500 Internal Server Error**: Помилка сервера:
      ```json
      {
          "detail": "Error: <error_message>"
      }
      ```

    **Примітки**:
    - Параметри `client` та `password` обов'язкові для авторизації.
    - Параметри `category_ids` та `days_valid` є необов'язковими, але дозволяють детальніше фільтрувати заявки.
    - Тип заявки (`type`) визначає набір заявок, які будуть включені у відповідь.
    """
    client_query = select(models.Client).filter(models.Client.name == client)
    client_result = await db.execute(client_query)
    client_entry = client_result.scalars().first()

    if not client_entry:
        raise HTTPException(status_code=400, detail="Invalid client type")

    if not pwd_context.verify(password, client_entry.password):
        raise HTTPException(status_code=400, detail="Incorrect password for client")

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
            from datetime import datetime, timedelta
            current_date = datetime.utcnow()
            valid_until = current_date + timedelta(days=days_valid)
            query = query.filter(cast(models.Applications.active_to, DateTime) <= valid_until)

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

@router.post("/rating/", status_code=200)
async def get_volunteer_rating(
        for_developers: ForDevelopers = Body(...),
        db: AsyncSession = Depends(get_db)
):
    """
    **Отримання рейтингу волонтерів для клієнта.**

    - **Ендпоінт**: POST `/rating/frontend/`
    - **Опис**: Дозволяє отримати список волонтерів, відсортованих за кількістю закритих заявок.
    - **Вхідні параметри**:
      - **for_developers**: Дані для авторизації:
        ```json
        {
            "client": "frontend",
            "password": "пароль_клієнта"
        }
        ```
        - **client**: Назва клієнта (наприклад, `frontend`).
        - **password**: Пароль для клієнта.
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
    - **400**: Невірний клієнт або неправильний пароль:
      ```json
      {
          "detail": "Invalid client type or password"
      }
      ```
    - **500**: Помилка сервера або бази даних:
      ```json
      {
          "detail": "Error: ..."
      }
      ```

    **Примітки:**
    - Перевіряється відповідність клієнта та пароля.
    - Повертається список волонтерів, які закрили заявки зі статусом `is_done = True`.
    """
    client_query = select(models.Client).filter(models.Client.name == for_developers.client)
    client_result = await db.execute(client_query)
    client_entry = client_result.scalars().first()

    if not client_entry:
        raise HTTPException(status_code=400, detail="Invalid client type or password")

    if not pwd_context.verify(for_developers.password, client_entry.password):
        raise HTTPException(status_code=400, detail="Invalid client type or password")

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


@router.post('/applications/count', status_code=200)
async def get_applications_count_by_type(
        payload: ForDevelopers,
        type: str = Query(..., description="Тип заявок: 'available', 'in_progress', 'finished'"),
        db: AsyncSession = Depends(get_db)
):
    """
    **Отримати кількість заявок за типом**

    - **Ендпоінт**: `POST /applications/count`
    - **Опис**: Цей ендпоінт повертає кількість заявок у базі даних для вказаного типу. Типи заявок можуть бути:
      - `available`: Доступні заявки (не завершені та не в процесі).
      - `in_progress`: Заявки в процесі (не завершені, але в процесі виконання).
      - `finished`: Завершені заявки (повністю виконані).

    **Вхідні параметри**:

    - **payload** (*JSON*): Авторизаційні дані клієнта:
        - **client** (*str*): Ім'я клієнта для авторизації (наприклад, `frontend` або `telegram`).
        - **password** (*str*): Пароль для клієнта.

    - **type** (*Query*): Тип заявок, для яких потрібно отримати кількість:
        - `'available'`: Доступні заявки.
        - `'in_progress'`: Заявки в процесі виконання.
        - `'finished'`: Завершені заявки.

    **Відповіді**:

    - **200 OK**: Успішний запит, повертається кількість заявок для вказаного типу. Формат відповіді:
    ```json
    {
        "type": "available",
        "count": 10
    }
    ```
    - **400 Bad Request**: Невірний клієнт або пароль. Виникає, якщо надано невірні авторизаційні дані.
    - **404 Not Found**: Неправильний тип заявки. Якщо тип, наданий у запиті, не є одним з наступних: `available`, `in_progress`, `finished`.
    - **500 Internal Server Error**: Виникла внутрішня помилка сервера.

    **Приклад запиту**:

    Запит на отримання кількості доступних заявок:
    ```json
    POST /applications/count
    Content-Type: application/json

    {
        "client": "frontend",
        "password": "yourpassword"
    }

    type=available
    ```

    **Приклад відповіді**:
    ```json
    {
        "type": "available",
        "count": 10
    }
    ```

    **Примітка**: Якщо клієнт або пароль невірні, буде повернено помилку 400. Якщо тип заявки невірний, буде повернено помилку 404.
    """
    client_query = select(models.Client).filter(models.Client.name == payload.client)
    client_result = await db.execute(client_query)
    client_entry = client_result.scalars().first()

    if not client_entry:
        raise HTTPException(status_code=400, detail="Invalid client type")

    if not pwd_context.verify(payload.password, client_entry.password):
        raise HTTPException(status_code=400, detail="Incorrect password for client")

    try:
        query = select(func.count()).select_from(models.Applications)

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

        result = await db.execute(query)
        total_count = result.scalar()

        return JSONResponse(content={"type": type, "count": total_count}, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
