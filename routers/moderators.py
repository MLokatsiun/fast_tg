from fastapi import APIRouter
from fastapi import  Depends, HTTPException
from sqlalchemy.orm import Session
import models
from business_logical import get_current_moderator, get_current_user, create_access_token, create_refresh_token, SECRET_KEY
from schemas import CategoryCreate, CategoryDelete, ApplicationDelete, VerificationResponse, VerificationUser, ModeratorLoginRequest
from database import get_db
from models import Customer
from datetime import timedelta
import bcrypt
from jose import JWTError, jwt


router = APIRouter()
from business_logical import ACCESS_TOKEN_EXPIRE_MINUTES

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password is None:
        return False
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

@router.post("/login/moderator", status_code=200)
async def login_moderator(request: ModeratorLoginRequest, db: Session = Depends(get_db)):
    """
    Логін модератора.

    Цей ендпоїнт дозволяє модератору увійти в систему, надаючи правильні дані для авторизації:
    - номер телефону модератора
    - роль модератора
    - пароль

    Перевіряється:
    - правильність типу клієнта (frontend або telegram)
    - правильність пароля для типу клієнта
    - правильність введених даних модератора (номер телефону, роль, пароль)

    Після успішної авторизації генеруються два токени:
    - **access_token**: для доступу до захищених ресурсів
    - **refresh_token**: для оновлення access_token

    Args:
        request (ModeratorLoginRequest): Запит, що містить дані для авторизації модератора.
        db (Session): Сесія бази даних для виконання запитів до бази.

    Raises:
        HTTPException: Якщо дані не відповідають вимогам (неправильний клієнт, пароль чи модератор).

    Returns:
        dict: Об'єкт з новими токенами.
    """
    if request.client not in ["frontend", "telegram"]:
        raise HTTPException(status_code=400, detail="Invalid client type")

    client_passwords = {
        "frontend": "4321",
        "telegram": "1234"
    }
    if request.client_password != client_passwords.get(request.client):
        raise HTTPException(status_code=400, detail="Incorrect password for client")

    moderator = db.query(models.Moderators).filter(
        models.Moderators.phone_number == request.phone_number,
        models.Moderators.role_id == request.role_id
    ).first()

    if not moderator or not verify_password(request.password, moderator.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    token_data = {
        "user_id": moderator.id,
        "role_id": moderator.role_id,
        "client": request.client
    }

    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_refresh_token(data=token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh-token/moderator", status_code=200)
async def refresh_token_moderator(refresh_token: str, db: Session = Depends(get_db)):
    '''Опис:
Цей ендпоїнт дозволяє оновити access_token для модератора за допомогою його refresh_token. Для цього токен декодується, і якщо він дійсний, створюється новий access_token з обмеженням часу дії.

Шлях:
POST /refresh-token/moderator

Параметри запиту:
refresh_token (тип: string): Refresh токен, за допомогою якого буде оновлено access токен.
Логіка:
Токен декодується за допомогою бібліотеки jwt для отримання user_id і role_id.
Перевіряється, чи існує модератор з вказаним user_id у базі даних.
Якщо модератор знайдений і його роль відповідає role_id, генерується новий access_token.
Повертається новий access_token та його тип.
Можливі помилки:
401 Unauthorized: Якщо токен недійсний або відсутні user_id або role_id в payload.
404 Not Found: Якщо модератор з вказаним ID не знайдений або його роль не відповідає токену.'''
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        role_id = payload.get("role_id")

        if user_id is None or role_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        moderator = db.query(models.Moderators).filter(models.Moderators.id == user_id).first()
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
async def create_category(category: CategoryCreate, db: Session = Depends(get_db), current_moderator=Depends(get_current_user)):
    """
        Створення нової категорії.

        Цей ендпоїнт дозволяє авторизованим модераторам створювати нові категорії в базі даних.

        Шлях:
        POST /categories/

        Параметри запиту:
        - name (тип: string): Назва категорії.
        - parent_id (тип: integer): ID батьківської категорії.
        - active_duration (тип: integer): Тривалість активації категорії в хвилинах.

        Логіка:
        1. Перевіряється, чи є у запиті всі необхідні дані.
        2. Створюється нова категорія в базі даних.
        3. Повертаються дані нової категорії.

        Можливі помилки:
        - 401 Unauthorized: Якщо користувач не є авторизованим модератором.
        - 422 Unprocessable Entity: Якщо дані категорії некоректні.
        """
    new_category = models.Categories(
        name=category.name,
        parent_id=category.parent_id,
        active_duration=category.active_duration
    )
    db.add(new_category)
    db.commit()
    db.refresh(new_category)

    return {
        "id": new_category.id,
        "name": new_category.name,
        "active_duration": new_category.active_duration,
        "parent_id": new_category.parent_id
    }

@router.delete("/categories/", status_code=204)
async def delete_category(category_delete: CategoryDelete, db: Session = Depends(get_db), current_moderator=Depends(get_current_user)):
    """
        Видалення категорії.

        Цей ендпоїнт дозволяє авторизованим модераторам видаляти категорії з бази даних.

        Шлях:
        DELETE /categories/

        Параметри запиту:
        - id (тип: integer): ID категорії, яку необхідно видалити.

        Логіка:
        1. Перевіряється, чи існує категорія з вказаним ID.
        2. Якщо категорія знайдена, вона видаляється з бази даних.
        3. Повертається повідомлення про успішне видалення категорії.

        Можливі помилки:
        - 404 Not Found: Якщо категорія з вказаним ID не знайдена.
        """
    category = db.query(models.Categories).filter(models.Categories.id == category_delete.id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db.delete(category)
    db.commit()
    return {"detail": "Category deleted successfully"}

@router.delete("/applications/", status_code=204)
async def delete_application(application_delete: ApplicationDelete, db: Session = Depends(get_db), current_moderator=Depends(get_current_user)):
    """
        Видалення заявки.

        Цей ендпоїнт дозволяє авторизованим модераторам видаляти заявки з бази даних.

        Шлях:
        DELETE /applications/

        Параметри запиту:
        - application_id (тип: integer): ID заявки, яку необхідно видалити.

        Логіка:
        1. Перевіряється, чи існує заявка з вказаним ID.
        2. Якщо заявка знайдена, вона видаляється з бази даних.
        3. Повертається повідомлення про успішне видалення заявки.

        Можливі помилки:
        - 404 Not Found: Якщо заявка з вказаним ID не знайдена.
        """
    application = db.query(models.Applications).filter(models.Applications.id == application_delete.application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    db.delete(application)
    db.commit()
    return {"detail": "Application deleted successfully"}


@router.post("/verify_user/", response_model=VerificationResponse)
async def verify_user(verification_user: VerificationUser, db: Session = Depends(get_db)):
    """
        Оновлення статусу верифікації користувача.

        Цей ендпоїнт дозволяє авторизованим модераторам оновлювати статус верифікації користувачів (перевіряти чи є користувач верифікованим).

        Шлях:
        POST /verify_user/

        Параметри запиту:
        - user_id (тип: integer): ID користувача, чий статус верифікації необхідно оновити.
        - is_verified (тип: boolean): Статус верифікації користувача (true або false).

        Логіка:
        1. Перевіряється, чи існує користувач з вказаним user_id у базі даних.
        2. Якщо користувач знайдений, оновлюється його статус верифікації.
        3. Повертається відповідь з оновленим статусом верифікації користувача.

        Можливі помилки:
        - 404 Not Found: Якщо користувач з вказаним ID не знайдений.
        """
    customer = db.query(Customer).filter(Customer.id == verification_user.user_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="User not found")

    customer.is_verified = verification_user.is_verified
    db.commit()
    db.refresh(customer)

    return VerificationResponse(
        id=customer.id,
        is_verified=customer.is_verified,
        message="User verification status updated successfully"
    )

