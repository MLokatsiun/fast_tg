from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Client, Moderators, Categories, Applications, Customer
from business_logical import get_current_user, create_access_token, create_refresh_token, SECRET_KEY
from schemas import CategoryCreate, CategoryDelete, ApplicationDelete, VerificationResponse, VerificationUser, ModeratorLoginRequest
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
async def refresh_token_moderator(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """
    **Оновлення токена доступу для модератора.**

    - **Ендпоінт**: POST `/refresh-token/`
    - **Опис**: Оновлює токен доступу для модератора за допомогою дійсного refresh-токена.

    - **Вхідні параметри**:
      - **refresh_token**: Токен оновлення, виданий під час аутентифікації модератора:
        ```json
        {
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR..."
        }
        ```

    - **Обмеження**:
      - Токен оновлення має бути дійсним і виданим для існуючого модератора.

    **Відповідь:**
    - **200**: Успішне оновлення токена доступу. Повертається новий токен:
        ```json
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
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

    **Примітки:**
    - Новий **access_token** діє протягом 15 хвилин.
    - Якщо refresh-токен недійсний або закінчився термін його дії, необхідно повторно пройти процес аутентифікації.
    - У разі виникнення проблем із оновленням токена зверніться до технічної підтримки.
    """

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        role_id = payload.get("role_id")

        if user_id is None or role_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        moderator = await db.execute(select(Moderators).filter(Moderators.id == user_id))
        moderator = moderator.scalars().first()
        if not moderator or moderator.role_id != role_id:
            raise HTTPException(status_code=404, detail="Moderator not found")

        expires_delta = timedelta(minutes=15)

        new_access_token = create_access_token(data={"user_id": moderator.id, "role_id": moderator.role_id}, expires_delta=expires_delta)

        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/categories/", status_code=201)
async def create_category(category: CategoryCreate, db: AsyncSession = Depends(get_db), current_moderator=Depends(get_current_user)):
    new_category = Categories(
        name=category.name,
        parent_id=category.parent_id,
        active_duration=category.active_duration
    )
    db.add(new_category)
    await db.commit()
    await db.refresh(new_category)

    return {
        "id": new_category.id,
        "name": new_category.name,
        "active_duration": new_category.active_duration,
        "parent_id": new_category.parent_id
    }

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
async def verify_user(verification_user: VerificationUser, db: AsyncSession = Depends(get_db)):
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
