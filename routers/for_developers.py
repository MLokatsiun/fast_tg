import math

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
        db: AsyncSession = Depends(get_db)
):
    """
    **Отримати список заявок за типом для розробників.**

    - **Ендпоінт**: POST `/applications/`
    - **Опис**: Дозволяє отримати список заявок за вказаним типом для розробників.
    - **Вхідні параметри**:
      - **client**: Назва клієнта для авторизації.
      - **password**: Пароль клієнта для авторизації.
      - **type**: Тип заявок (обов'язково):
        - **'available'**: доступні заявки.
        - **'in_progress'**: заявки в процесі виконання.
        - **'finished'**: завершені заявки.
      - **db**: Сесія бази даних для виконання запиту.

    **Відповідь:**
    - **200**: Список заявок для вказаного клієнта за вказаним типом. Повертається масив заявок:
      ```json
      [
        {
          "id": 1,
          "description": "Description of the application",
          "category_id": 2,
          "location": {
            "latitude": 50.4501,
            "longitude": 30.6402,
            "address_name": "Kyiv, Ukraine"
          },
          "creator": {
            "id": 1,
            "first_name": "John",
            "phone_num": "1234567890"
          },
          "executor": {
            "id": 2,
            "first_name": "Jane",
            "phone_num": "0987654321"
          },
          "is_in_progress": true,
          "is_done": false,
          "date_at": "2024-12-01T12:00:00",
          "active_to": "2024-12-31T23:59:59"
        }
      ]
      ```
    - **400**: Помилка вхідних даних. Наприклад, невірний клієнт або неправильний пароль:
      ```json
      {
        "detail": "Invalid client type"
      }
      ```
    - **404**: Помилка типу заявок. Якщо тип заявки не співпадає з можливими значеннями:
      ```json
      {
        "detail": "Invalid application type"
      }
      ```
    - **500**: Помилка сервера або бази даних:
      ```json
      {
        "detail": "Error: ..."
      }
      ```

    **Примітки:**
    - Для доступу до заявок необхідно вказати правильний клієнт та пароль.
    - Тип заявки має бути одним з таких: 'available', 'in_progress', 'finished'.
    """
    client_query = select(models.Client).filter(models.Client.name == client)
    client_result = await db.execute(client_query)
    client_entry = client_result.scalars().first()

    if not client_entry:
        raise HTTPException(status_code=400, detail="Invalid client type")

    if not pwd_context.verify(password, client_entry.password):
        raise HTTPException(status_code=400, detail="Incorrect password for client")

    try:
        if type == 'available':
            query = select(models.Applications, models.Locations, models.Customer).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).join(
                models.Customer, models.Applications.creator_id == models.Customer.id
            ).filter(
                models.Applications.is_done.is_(False),
                models.Applications.is_in_progress.is_(False),
                models.Applications.is_active.is_(True)
            )

        elif type == 'in_progress':
            query = select(models.Applications, models.Locations, models.Customer).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).join(
                models.Customer, models.Applications.creator_id == models.Customer.id
            ).filter(
                models.Applications.is_in_progress.is_(True),
                models.Applications.is_done.is_(False),
                models.Applications.is_active.is_(True)
            )

        elif type == 'finished':
            query = select(models.Applications, models.Locations, models.Customer).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).join(
                models.Customer, models.Applications.creator_id == models.Customer.id
            ).filter(
                models.Applications.is_done.is_(True),
                models.Applications.is_active.is_(True)
            )

        else:
            raise HTTPException(status_code=404, detail="Invalid application type")

        result = await db.execute(query)
        applications = result.fetchall()

        response_data = []
        for application in applications:
            executor_data = None
            if application.Applications.executor_id:
                executor_query = select(models.Customer).filter(models.Customer.id == application.Applications.executor_id)
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

