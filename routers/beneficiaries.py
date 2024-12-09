from typing import List, Optional
from fastapi import Depends, APIRouter, Query
from starlette.responses import JSONResponse
from database import get_db
from business_logical import (get_current_beneficiary, get_coordinates)
import models
from schemas import ApplicationCreate, ApplicationDelete, ApplicationConfirm, ApplicationsList
from fastapi import HTTPException
from dateparser import parse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

router = APIRouter()


@router.delete("/profile/", status_code=200)
async def deactivate_beneficiary(
        current_user=Depends(get_current_beneficiary),
        db: AsyncSession = Depends(get_db)
):
    """
    **Деактивація профілю бенефіціара.**

    - **current_user**: Бенефіціар, який наразі аутентифікований в системі.
    - **db**: Асинхронна сесія бази даних.

    **Відповідь:**
    - **200**: Профіль успішно деактивовано.
        - Повертається повідомлення:
          ```json
          {
              "detail": "Beneficiary deactivated successfully"
          }
          ```
    - **403**: Користувач не підтверджений.
        - Повертається повідомлення:
          ```json
          {
              "detail": "Access denied. User not verified by moderator"
          }
          ```
    - **404**: Бенефіціара не знайдено.
        - Повертається повідомлення:
          ```json
          {
              "detail": "Beneficiary not found"
          }
          ```
    """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    result = await db.execute(
        select(models.Customer).filter(models.Customer.id == current_user.id)
    )
    beneficiary = result.scalar_one_or_none()

    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    beneficiary.is_active = False
    await db.commit()

    return {"detail": "Beneficiary deactivated successfully"}


@router.post("/applications/", status_code=201)
async def create_application(
        application: ApplicationCreate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_beneficiary)
):
    """
    **Створити нову заявку.**

    - **application**: Об'єкт типу `ApplicationCreate`, що містить дані про заявку.
        - **description**: Опис заявки (тип: `str`).
        - **category_id**: (необов'язково) ID категорії заявки (тип: `int`).
        - **address**: (необов'язково) Адреса для локації заявки (тип: `str`).
        - **latitude**: (необов'язково) Широта локації (тип: `float`).
        - **longitude**: (необов'язково) Довгота локації (тип: `float`).
        - **active_to**: Дата, до якої дія буде активною (тип: `str` в форматі ISO 8601).

    - **db**: Сесія бази даних.
    - **current_user**: Бенефіціар, який наразі аутентифікований в системі.

    **Відповідь:**
    - **201**: Заявка успішно створена.
        - Повертається об'єкт JSON з даними нової заявки:
          ```json
          {
              "id": 1,
              "creator_id": 123,
              "location_id": 456,
              "description": "Опис заявки",
              "active_to": "2024-12-31T23:59:59"
          }
          ```
    - **400**: Невірно задана дата або відсутні координати.
        - Повертається помилка з деталями:
          ```json
          {
              "detail": "Invalid date: active_to must be in the future."
          }
          ```
    """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    try:
        active_to_date = parse(application.active_to)
        if not active_to_date:
            raise ValueError("Дата не розпізнана")

        if active_to_date < datetime.utcnow():
            raise HTTPException(status_code=400, detail="active_to date must be in the future.")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date: {str(e)}")

    try:
        if application.address:
            coordinates = await get_coordinates(application.address)
            latitude, longitude = coordinates["latitude"], coordinates["longitude"]
            address = application.address
        elif application.latitude and application.longitude:
            latitude, longitude = application.latitude, application.longitude
            reverse_geocode = await get_coordinates(lat=latitude, lng=longitude)
            address = reverse_geocode.get("address")
            if not address:
                raise HTTPException(status_code=400, detail="Could not resolve address for the given coordinates.")
        else:
            raise HTTPException(status_code=400, detail="Provide either address or both latitude and longitude.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error in geocoding: {str(e)}")

    try:
        query = select(models.Categories).filter(models.Categories.id == application.category_id)
        category_result = await db.execute(query)
        category = category_result.scalar_one_or_none()

        if not category:
            raise HTTPException(status_code=400, detail=f"Invalid category_id: {application.category_id}")

        # Обробка локації
        result = await db.execute(
            select(models.Locations).filter(
                models.Locations.latitude == float(latitude),
                models.Locations.longitude == float(longitude),
                models.Locations.address_name == address
            )
        )
        existing_location = result.scalar_one_or_none()

        if existing_location:
            location_id = existing_location.id
        else:
            new_location = models.Locations(latitude=latitude, longitude=longitude, address_name=address)
            db.add(new_location)
            await db.commit()
            await db.refresh(new_location)
            location_id = new_location.id
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{str(e)}")

    try:
        new_application = models.Applications(
            creator_id=current_user.id,
            category_id=application.category_id,
            location_id=location_id,
            description=application.description,
            is_in_progress=False,
            is_done=False,
            is_finished=False,
            active_to=active_to_date.isoformat(),
            date_at=datetime.utcnow().isoformat()
        )

        db.add(new_application)
        await db.commit()
        await db.refresh(new_application)

        return {
            "id": new_application.id,
            "creator_id": current_user.id,
            "location_id": new_application.location_id,
            "description": new_application.description,
            "active_to": active_to_date
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error while creating application: {str(e)}")


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


@router.put("/applications/", status_code=200)
async def confirm_application(
        application_confirm: ApplicationConfirm,
        db: AsyncSession = Depends(get_db),
        current_user: models.Customer = Depends(get_current_beneficiary)
):
    """
    **Підтвердити виконання заявки.**

    - **application_confirm**: Об'єкт типу `ApplicationConfirm`, що містить ID заявки.
        - `application_id`: **int** — унікальний ідентифікатор заявки, яку потрібно підтвердити.
    - **db**: Сесія бази даних для взаємодії з таблицею заявок.
    - **current_user**: Бенефіціар, який наразі аутентифікований в системі.

    **Відповідь:**
    - **200**: Заявка успішно підтверджена.
        - Повертається повідомлення:
          ```json
          {
              "detail": "Application confirmed successfully"
          }
          ```
    - **404**: Заявку не знайдено.
        - Повертається повідомлення:
          ```json
          {
              "detail": "Application not found"
          }
          ```
    - **400**: Виконавець не призначений або завдання не позначене як виконане.
        - Повертається повідомлення:
          ```json
          {
              "detail": "No executor assigned to the application"
          }
          ```
        або:
          ```json
          {
              "detail": "The task has not been marked as done by the executor"
          }
          ```

    **Примітка:**
    - Підтвердити заявку може тільки бенефіціар, який аутентифікований і підтверджений модератором.
    - Заявка буде підтверджена тільки в тому випадку, якщо:
      1. Заявці призначено виконавця (`executor_id`).
      2. Заявка позначена як виконана (`is_done`).
    """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")


    result = await db.execute(
        select(models.Applications).filter(models.Applications.id == application_confirm.application_id))
    application = result.scalars().first()

    if not application:
        raise HTTPException(status_code=404, detail='Application not found')

    if application.executor_id is None:
        raise HTTPException(status_code=400, detail='No executor assigned to the application')

    if not application.is_done:
        raise HTTPException(status_code=400, detail='The task has not been marked as done by the executor')

    application.is_finished = True

    await db.commit()

    return {"detail": "Application confirmed successfully"}


# Видалення заявки
@router.delete("/applications/", status_code=204)
async def delete_application(
        application_delete: ApplicationDelete,
        db: AsyncSession = Depends(get_db),
        current_user: models.Customer = Depends(get_current_beneficiary)
):
    '''
    **Видалити заявку.**

    - **application_delete**: Об'єкт типу `ApplicationDelete`, що містить ID заявки.
        - `application_id`: **int** — унікальний ідентифікатор заявки, яку потрібно видалити.
    - **db**: Сесія бази даних для взаємодії з таблицею заявок.
    - **current_user**: Бенефіціар, який наразі аутентифікований в системі.

    **Відповідь:**
    - **200**: Заявка успішно видалена.
        - Повертається повідомлення:
          ```json
          {
              "message": "The application has been successfully deleted"
          }
          ```
    - **404**: Заявку не знайдено.
        - Повертається повідомлення:
          ```json
          {
              "detail": "Application not found"
          }
          ```

    **Примітка:**
    - Видалення заявки фактично робить її неактивною, оновлюючи поле `is_active` в базі даних.
    - Підтвердити видалення може тільки бенефіціар, який аутентифікований і підтверджений модератором.
    '''
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    result = await db.execute(
        select(models.Applications).filter(
            models.Applications.id == application_delete.application_id
        )
    )
    application = result.scalars().first()

    if not application:
        raise HTTPException(status_code=404, detail='Application not found')

    application.is_active = False
    await db.commit()

    return JSONResponse(
        status_code=200,
        content={"message": "The application has been successfully deleted"}
    )


@router.get('/applications/', response_model=List[ApplicationsList])
async def get_applications(
        type: Optional[str] = Query(..., description="Тип заявок: 'accessible', 'is_progressing', 'complete'"),
        db: AsyncSession = Depends(get_db),
        current_user: models.Customer = Depends(get_current_beneficiary)
):
    """
    **Отримати список заявок за типом.**

    - **type**: Тип заявок (обов'язково): 'accessible', 'is_progressing', 'complete'.
        - `available`: Заявки, які доступні для виконання.
        - `in_progress`: Заявки, що знаходяться в процесі виконання.
        - `finished`: Завершені заявки.
    - **db**: Сесія бази даних для виконання запиту.
    - **current_user**: Бенефіціар, який наразі аутентифікований в системі.

    **Відповідь:**
    - **200**: Список заявок, що відповідають вказаному типу. Повертається список об'єктів заявок.
    - **403**: Доступ заборонено для не верифікованих користувачів.
    - **404**: Некоректний тип заявок.
        - Повертається повідомлення:
          ```json
          {
              "detail": "Invalid applications type"
          }
          ```

    **Формат відповіді:**
    - **200**: Список заявок для запитуваного типу. Кожен елемент списку містить такі поля:
      ```json
      [
        {
            "id": 1,
            "description": "Заявка на виконання завдання",
            "category_id": 2,
            "location": 3,
            "executor_id": 4,
            "is_in_progress": false,
            "is_done": false,
            "date_at": "2024-11-16T10:00:00",
            "active_to": "2024-11-20T10:00:00"
        },
        ...
      ]
      ```

    **Примітка:**
    - У разі помилки запиту або некоректного значення типу заявки, повертається відповідь з помилкою.
    - Для отримання списку заявок необхідно вказати правильний тип: 'available', 'in_progress' або 'finished'.
    """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    try:
        if type == 'accessible':
            query = select(
                models.Applications,
                models.Locations,
                models.Customer
            ).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).outerjoin(
                models.Customer, models.Applications.executor_id == models.Customer.id
            ).filter(
                models.Applications.creator_id == current_user.id,
                models.Applications.is_done.is_(False),
                models.Applications.is_in_progress.is_(False),
                models.Applications.is_active.is_(True)
            )

        elif type == 'is_progressing':
            query = select(
                models.Applications,
                models.Locations,
                models.Customer
            ).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).outerjoin(
                models.Customer, models.Applications.executor_id == models.Customer.id
            ).filter(
                models.Applications.creator_id == current_user.id,
                models.Applications.is_in_progress.is_(True),
                models.Applications.is_done.is_(False),
                models.Applications.is_active.is_(True)
            )

        elif type == 'complete':
            query = select(
                models.Applications,
                models.Locations,
                models.Customer
            ).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).outerjoin(
                models.Customer, models.Applications.executor_id == models.Customer.id
            ).filter(
                models.Applications.creator_id == current_user.id,
                models.Applications.is_done.is_(True),
                models.Applications.is_active.is_(True)
            )

        else:
            raise HTTPException(status_code=404, detail='Invalid applications type')

        result = await db.execute(query)
        applications = result.fetchall()

        response_data = [
            {
                'id': application.Applications.id,
                'description': application.Applications.description,
                'category_id': application.Applications.category_id,
                'location': {
                    'latitude': application.Locations.latitude,
                    'longitude': application.Locations.longitude,
                    'address_name': application.Locations.address_name
                },
                'executor': {
                    'id': application.Customer.id if application.Customer else None,
                    'first_name': application.Customer.firstname if application.Customer else None,
                    'phone_num': application.Customer.phone_num if application.Customer else None
                } if application.Customer else None,
                'is_in_progress': application.Applications.is_in_progress,
                'is_done': application.Applications.is_done,
                'date_at': application.Applications.date_at,
                'active_to': application.Applications.active_to
            }
            for application in applications
        ]

        return JSONResponse(content=response_data, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error: {str(e)}')
