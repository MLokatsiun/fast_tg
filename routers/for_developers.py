from database import get_db
import models
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from schemas import ForDevelopers

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()

from fastapi import Body


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



