from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import Depends, APIRouter, Query
from starlette.responses import JSONResponse

import models
from models import Client, Moderators, Categories, Applications, Customer
from business_logical import get_current_user, create_access_token, create_refresh_token, SECRET_KEY
from schemas import (CategoryCreate, CategoryDelete, ApplicationDelete, VerificationResponse, VerificationUser,
                     ModeratorLoginRequest, RefreshTokenRequest, ForDevelopers)
from database import get_db
from datetime import timedelta
import bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter()
from business_logical import ACCESS_TOKEN_EXPIRE_MINUTES

async def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password is None:
        return False
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

@router.post("/login/", status_code=200)
async def login_moderator(login_request: ModeratorLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    **Вхід модератора в систему.**

    - **Ендпоінт**: POST `/login/moderator`
    - **Опис**: Дозволяє модератору аутентифікуватися в системі та отримати токени доступу.

    - **Вхідні параметри**:
      - **login_request**: Дані для входу модератора:
        ```json
        {
            "phone_number": "1234567890",
            "password": "Пароль модератора",
            "client": "Назва клієнта",
            "client_password": "Пароль клієнта"
        }
        ```
        - **phone_number**: Номер телефону модератора.
        - **password**: Пароль модератора для аутентифікації.
        - **client**: Назва клієнта, з яким пов'язаний модератор.
        - **client_password**: Пароль клієнта для перевірки доступу.

    - **Обмеження**:
      - Модератор має бути активним і зареєстрованим в системі.
      - Клієнт має бути валідним і зареєстрованим у системі.

    **Відповідь:**
    - **200**: Успішний вхід модератора. Повертаються токени доступу:
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

    - **400**: Помилка авторизації.
      - Невалідний тип клієнта:
        ```json
        {
            "detail": "Invalid client type"
        }
        ```
      - Невірний пароль клієнта:
        ```json
        {
            "detail": "Incorrect password for client"
        }
        ```
      - Невірні дані модератора:
        ```json
        {
            "detail": "Invalid moderator credentials"
        }
        ```

    **Примітки:**
    - **access_token** діє протягом часу, визначеного параметром `ACCESS_TOKEN_EXPIRE_MINUTES`.
    - **refresh_token** можна використовувати для оновлення токена доступу.
    - У разі виникнення проблем з аутентифікацією зверніться до технічної підтримки.
    """

    client_entry = await db.execute(select(Client).filter(Client.name == login_request.client))
    client_entry = client_entry.scalars().first()
    if not client_entry:
        raise HTTPException(status_code=400, detail="Invalid client type")

    if not pwd_context.verify(login_request.client_password, client_entry.password):
        raise HTTPException(status_code=400, detail="Incorrect password for client")

    moderator = await db.execute(select(Moderators).filter(Moderators.phone_number == login_request.phone_number))
    moderator = moderator.scalars().first()

    if not moderator or not pwd_context.verify(login_request.password, moderator.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid moderator credentials")

    token_data = {
        "user_id": moderator.id,
        "role_id": moderator.role_id,
        "client": login_request.client
    }

    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_refresh_token(data=token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh-token/", status_code=200)
async def refresh_token_moderator(refresh_token_request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    **Оновлення токена доступу для модератора.**

    - **Ендпоінт**: POST `/refresh-token/`
    - **Опис**: Оновлює токен доступу для модератора за допомогою дійсного refresh-токена.

    - **Вхідні параметри**:
      - **refresh_token**: Токен оновлення, виданий під час аутентифікації модератора:
        ```json
        {
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR...<your-refresh-token>..."
        }
        ```
      - **refresh_token** має бути дійсним і виданим для існуючого модератора.

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
      - Невалідний refresh-токен або токен без необхідних даних:
        ```json
        {
            "detail": "Invalid token"
        }
        ```

    - **404**: Модератор не знайдений.
      - Якщо модератор не існує або його дані не відповідають токену:
        ```json
        {
            "detail": "Moderator not found"
        }
        ```

    **Примітки**:
    - Новий **access_token** діє протягом 15 хвилин.
    - Якщо refresh-токен недійсний або закінчився термін його дії, необхідно повторно пройти процес аутентифікації.
    - У разі виникнення проблем із оновленням токена зверніться до технічної підтримки.
    """

    try:
        payload = jwt.decode(refresh_token_request.refresh_token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        role_id = payload.get("role_id")

        if user_id is None or role_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        moderator = await db.execute(select(Moderators).filter(Moderators.id == user_id))
        moderator = moderator.scalars().first()

        if not moderator or moderator.role_id != role_id:
            raise HTTPException(status_code=404, detail="Moderator not found")

        expires_delta = timedelta(minutes=15)
        new_access_token = create_access_token(data={"user_id": moderator.id, "role_id": moderator.role_id},
                                               expires_delta=expires_delta)

        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/categories/", status_code=201)
async def create_category(category: CategoryCreate, db: AsyncSession = Depends(get_db), current_moderator=Depends(get_current_user)):
    """
    **Створення нової категорії або активація неактивної.**

    - **Ендпоінт**: POST `/categories/`
    - **Опис**: Дозволяє створити нову категорію або активувати вже існуючу неактивну категорію.
    - **Вхідні параметри**:
      - **category**: Дані для створення або активації категорії:
        ```json
        {
            "name": "Назва категорії",
            "parent_id": 1
        }
        ```
        - **name**: Назва категорії (обов'язково).
        - **parent_id**: Ідентифікатор батьківської категорії (необов'язково).

    - **Обмеження**:
      - Якщо категорія з таким ім'ям вже існує і активна, вона не буде створена повторно.
      - Якщо категорія з таким ім'ям існує, але неактивна, вона буде активована.

    **Відповідь:**
    - **201**: Успішне створення нової категорії або реактивація неактивної категорії. Повертається інформація про категорію:
        ```json
        {
            "id": 1,
            "name": "Назва категорії",
            "parent_id": 1
        }
        ```
    - **400**: Помилка вхідних даних. Наприклад, категорія з таким ім'ям уже існує і є активною:
        ```json
        {
            "detail": "Category 'Назва категорії' already exists and is active."
        }
        ```
    - **500**: Помилка сервера або бази даних:
        ```json
        {
            "detail": "Error: ..."
        }
        ```

    **Примітки:**
    - Якщо категорія вже існує, але неактивна, вона буде активована та оновлений її `parent_id`.
    - Після створення нової категорії вона матиме статус активної.
    """
    try:
        existing_category_result = await db.execute(
            select(Categories).filter(Categories.name == category.name)
        )
        existing_category = existing_category_result.scalars().first()

        if existing_category:
            if existing_category.is_active:
                return {
                    "detail": f"Category '{category.name}' already exists and is active.",
                    "id": existing_category.id,
                    "name": existing_category.name,
                    "parent_id": existing_category.parent_id
                }
            else:
                existing_category.is_active = True
                existing_category.parent_id = category.parent_id
                await db.commit()
                await db.refresh(existing_category)
                return {
                    "id": existing_category.id,
                    "name": existing_category.name,
                    "parent_id": existing_category.parent_id,
                    "status": "Category reactivated"
                }

        new_category = Categories(
            name=category.name,
            parent_id=category.parent_id
        )
        db.add(new_category)
        await db.commit()
        await db.refresh(new_category)

        return {
            "id": new_category.id,
            "name": new_category.name,
            "parent_id": new_category.parent_id
        }

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.delete("/categories/", status_code=204)
async def deactivate_category(category_delete: CategoryDelete, db: AsyncSession = Depends(get_db), current_moderator=Depends(get_current_user)):
    """
    **Деактивація категорії.**

    - **Ендпоінт**: DELETE `/categories/`
    - **Опис**: Деактивує категорію за її ідентифікатором, встановлюючи поле `is_active` в `False`.

    - **Вхідні параметри**:
      - **category_delete**: Дані категорії, яку потрібно деактивувати:
        ```json
        {
            "id": 123
        }
        ```
        - **id**: Унікальний ідентифікатор категорії, яку потрібно деактивувати.

    - **Обмеження**:
      - Доступний лише для модераторів із дійсним токеном авторизації.
      - Категорія повинна існувати в базі даних.

    **Відповідь:**
    - **204**: Категорія успішно деактивована. Відповідь без вмісту, з повідомленням:
        ```json
        {
            "detail": "Category deactivated successfully"
        }
        ```

    - **404**: Категорія не знайдена.
        ```json
        {
            "detail": "Category not found"
        }
        ```

    **Примітки:**
    - Деактивація категорії означає, що вона більше не буде доступна для використання, але залишиться в базі даних.
    - У разі помилок доступу або авторизації, зверніться до адміністратора системи.
    """

    category = await db.execute(select(Categories).filter(Categories.id == category_delete.id))
    category = category.scalars().first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    category.is_active = False
    await db.commit()

    return {"detail": "Category deactivated successfully"}

@router.delete("/applications/", status_code=204)
async def delete_application(application_delete: ApplicationDelete, db: AsyncSession = Depends(get_db), current_moderator=Depends(get_current_user)):
    """
    **Деактивація заявки.**

    - **Ендпоінт**: DELETE `/applications/`
    - **Опис**: Деактивує заявку за її ідентифікатором, встановлюючи поле `is_active` в `False`.

    - **Вхідні параметри**:
      - **application_delete**: Дані заявки, яку потрібно деактивувати:
        ```json
        {
            "application_id": 123
        }
        ```
        - **application_id**: Унікальний ідентифікатор заявки, яку потрібно деактивувати.

    - **Обмеження**:
      - Доступний лише для модераторів із дійсним токеном авторизації.
      - Заявка повинна існувати в базі даних.

    **Відповідь:**
    - **204**: Заявка успішно деактивована. Відповідь без вмісту, з повідомленням:
        ```json
        {
            "detail": "Application deleted successfully"
        }
        ```

    - **404**: Заявка не знайдена.
        ```json
        {
            "detail": "Application not found"
        }
        ```

    **Примітки:**
    - Деактивація заявки означає, що вона більше не буде доступна для використання, але залишиться в базі даних.
    - У разі помилок доступу або авторизації, зверніться до адміністратора системи.
    """

    application = await db.execute(select(Applications).filter(Applications.id == application_delete.application_id))
    application = application.scalars().first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application.is_active = False
    await db.commit()
    return {"detail": "Application deleted successfully"}

@router.post("/verify_user/", response_model=VerificationResponse)
async def verify_user(verification_user: VerificationUser, db: AsyncSession = Depends(get_db), current_moderator=Depends(get_current_user)):
    """
    **Перевірка користувача.**

    - **Ендпоінт**: POST `/verify_user/`
    - **Опис**: Оновлює статус верифікації користувача в системі.

    - **Вхідні параметри**:
      - **verification_user**: Дані для оновлення статусу верифікації:
        ```json
        {
            "user_id": 123,
            "is_verified": true
        }
        ```
        - **user_id**: Унікальний ідентифікатор користувача, статус якого потрібно оновити.
        - **is_verified**: Новий статус верифікації (`true` або `false`).

    - **Обмеження**:
      - Доступний лише для модераторів із дійсним токеном авторизації.
      - Користувач повинен існувати в базі даних.

    **Відповідь:**
    - **200**: Статус верифікації успішно оновлений. Повертається об'єкт:
        ```json
        {
            "id": 123,
            "is_verified": true,
            "message": "User verification status updated successfully"
        }
        ```

    - **404**: Користувач не знайдений.
        ```json
        {
            "detail": "User not found"
        }
        ```

    **Примітки:**
    - Статус верифікації відображає, чи підтверджений користувач модератором.
    - У разі помилок доступу або авторизації, зверніться до адміністратора системи.
    """

    customer = await db.execute(select(Customer).filter(Customer.id == verification_user.user_id))
    customer = customer.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="User not found")

    customer.is_verified = verification_user.is_verified
    await db.commit()
    await db.refresh(customer)

    return VerificationResponse(
        id=customer.id,
        is_verified=customer.is_verified,
        message="User verification status updated successfully"
    )

@router.post("/app/categories/", status_code=200)
async def get_categories(
        for_developers: ForDevelopers = Body(...),
        db: AsyncSession = Depends(get_db)
):
    """
        **Отримання категорій для клієнта.**

        - **Ендпоінт**: POST `/app/categories/`
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

@router.post("/app/customers/", status_code=200)
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

@router.post('/app/applications/', status_code=200)
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

