from datetime import datetime

from sqlalchemy.orm import selectinload

from business_logical import (get_current_volonter, get_coordinates)
import models
from schemas import EditCustomerBase, AcceptApplicationBase, ApplicationsList
from typing import Optional
import aiofiles
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form, Query
from typing import List
from database import get_db
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.responses import JSONResponse
import os
from models import Media, Ink_ApplicationsMedia

router = APIRouter()


@router.put('/profile/')
async def edit_customer(
        customer_info: EditCustomerBase,
        db: AsyncSession = Depends(get_db),
        volunteer: models.Customer = Depends(get_current_volonter)
):
    """
        **Редагувати профіль існуючого волонтера.**

        - **customer_info**: Об'єкт типу `EditCustomerBase`, що містить оновлену інформацію про профіль волонтера.
            - **location**: (необов'язково) Об'єкт типу `LocationUpdate`, що містить оновлену локацію волонтера.
                - **latitude**: (необов'язково) Новий рівень широти локації (тип: `float`).
                - **longitude**: (необов'язково) Новий рівень довготи локації (тип: `float`).
                - **address**: (необов'язково) Нова адреса локації (тип: `str`).
            - **categories**: (необов'язково) Список нових категорій волонтера (тип: `List[int]`).
                - Кожен елемент списку — це ID категорії, яку потрібно додати до профілю волонтера.

        - **db**: Сесія бази даних для виконання запиту.
        - **volunteer**: Волонтер, який наразі аутентифікований в системі.

        **Відповідь:**
        - **200**: Інформація про профіль волонтера успішно оновлена.
            - Повертається об'єкт JSON з оновленими даними:
              ```json
              {
                  "id": 1,
                  "phone_num": "1234567890",
                  "tg_id": "tg_user_id",
                  "firstname": "John",
                  "lastname": "Doe",
                  "categories": [1, 2, 3],
                  "location": 123
              }
              ```

        - **400**: Невірно вказана локація або відсутня адреса або координати.
            - Повертається повідомлення:
              ```json
              {
                  "detail": "Provide either coordinates or an address."
              }
              ```

        - **403**: Користувач не підтверджений.
            - Повертається повідомлення:
              ```json
              {
                  "detail": "Access denied. User not verified by moderator"
              }
              ```

        - **500**: Помилка бази даних.
            - Повертається повідомлення:
              ```json
              {
                  "detail": "Database error: <error_message>"
              }
              ```

        **Примітка:**
        - Для оновлення локації можна вказати нові координати (широту та довготу) або нову адресу.
        - Категорії волонтера можна додавати або видаляти через відповідні ID.
        - Волонтер може редагувати тільки свій профіль.
        """
    if not volunteer.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    try:
        customer = volunteer

        if customer_info.location is not None:
            if customer_info.location.latitude is not None and customer_info.location.longitude is not None:
                latitude = float(customer_info.location.latitude)
                longitude = float(customer_info.location.longitude)

                if not customer_info.location.address:
                    reverse_geocode = await get_coordinates(lat=latitude, lng=longitude)
                    address = reverse_geocode.get("address")
                    if not address:
                        raise HTTPException(status_code=400,
                                            detail="Could not resolve address for the given coordinates.")
                else:
                    address = customer_info.location.address
            elif customer_info.location.address:
                coordinates = await get_coordinates(address=customer_info.location.address)
                latitude = float(coordinates["latitude"])
                longitude = float(coordinates["longitude"])
                address = customer_info.location.address
            else:
                raise HTTPException(status_code=400, detail="Provide either coordinates or an address.")

            query = select(models.Locations).filter(
                models.Locations.latitude == latitude,
                models.Locations.longitude == longitude,
                models.Locations.address_name == address
            )
            location_result = await db.execute(query)
            location = location_result.scalars().first()

            if not location:
                location = models.Locations(
                    latitude=latitude,
                    longitude=longitude,
                    address_name=address
                )
                db.add(location)
                await db.commit()
                await db.refresh(location)

            customer.location_id = location.id

        if customer_info.categories is not None:
            query = select(models.Categories).filter(
                models.Categories.id.in_(customer_info.categories)
            )
            existing_categories_result = await db.execute(query)
            existing_categories = {cat.id for cat in existing_categories_result.scalars().all()}

            invalid_categories = set(customer_info.categories) - existing_categories
            if invalid_categories:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category IDs: {', '.join(map(str, invalid_categories))}"
                )

            query = select(models.Ink_CustomerCategories).filter(
                models.Ink_CustomerCategories.customer_id == customer.id
            )
            current_categories_result = await db.execute(query)
            current_categories = current_categories_result.scalars().all()

            current_category_ids = {cat.category_id for cat in current_categories}
            new_category_ids = set(customer_info.categories)

            categories_to_add = new_category_ids - current_category_ids
            categories_to_remove = current_category_ids - new_category_ids

            for category_id in categories_to_add:
                new_category = models.Ink_CustomerCategories(
                    customer_id=customer.id,
                    category_id=category_id
                )
                db.add(new_category)

            for category_id in categories_to_remove:
                delete_query = delete(models.Ink_CustomerCategories).where(
                    models.Ink_CustomerCategories.customer_id == customer.id,
                    models.Ink_CustomerCategories.category_id == category_id
                )
                await db.execute(delete_query)

            await db.commit()

        await db.refresh(customer)

        return JSONResponse(status_code=200, content={
            'id': customer.id,
            'phone_num': customer.phone_num,
            'tg_id': customer.tg_id,
            'firstname': customer.firstname,
            'lastname': customer.lastname,
            'categories': customer_info.categories,
            'location': customer.location_id
        })

    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f'Database error: {str(e)}')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error: {str(e)}')


@router.delete('/profile/', status_code=204)
async def delete_profile(
        db: AsyncSession = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
    """
        **Деактивувати профіль поточного волонтера.**

        Цей ендпоінт дозволяє деактивувати профіль волонтера, якщо:
        - Роль ID = 2
        - Профіль активний (is_active = True)

        **Аргументи:**
        - **db**: Сесія бази даних для виконання запиту.
        - **current_volunteer**: Поточний авторизований волонтер.

        **Винятки:**
        - **403**: Якщо користувач не підтверджений або не має ролі ID = 2.
          - Повертається повідомлення:
            ```json
            {
                "detail": "Access denied. User is not authorized to perform this action"
            }
            ```
        - **404**: Якщо профіль волонтера не знайдений або вже неактивний.
          - Повертається повідомлення:
            ```json
            {
                "detail": "Customer with Telegram ID <tg_id> not found or is already inactive"
            }
            ```
        - **500**: Помилка сервера.
          - Повертається повідомлення:
            ```json
            {
                "detail": "Error: <error_message>"
            }
            ```

        **Повертає:**
        - **204**: Якщо профіль успішно деактивовано, відповідь не містить тіла.
    """
    if not current_volunteer.is_verified or current_volunteer.role_id != 2:
        raise HTTPException(
            status_code=403,
            detail="Access denied. User is not authorized to perform this action"
        )

    try:
        result = await db.execute(
            select(models.Customer).filter(
                models.Customer.tg_id == current_volunteer.tg_id,
                models.Customer.is_active == True,
                models.Customer.role_id == 2
            )
        )
        profile = result.scalar_one_or_none()

        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"Customer with Telegram ID {current_volunteer.tg_id} not found or is already inactive"
            )

        profile.is_active = False
        await db.commit()

        return None

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@router.post('/applications/accept/', status_code=200)
async def accept_application(
        app_id: AcceptApplicationBase,
        db: AsyncSession = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
    """
        Прийняття заявки волонтером.

        Цей ендпоінт дозволяє волонтеру прийняти заявку для виконання. Якщо волонтер не підтверджений або вже має 3 активні заявки, запит буде відхилено.

        **Параметри запиту**:
        - `application_id`: ID заявки, яку волонтер хоче прийняти.

        **Параметри тіла запиту**:
        - `application_id` (int): Унікальний ідентифікатор заявки, яку потрібно прийняти.

        **Відповідь**:
        - Успішна відповідь містить оновлену інформацію про заявку з локацією:
            - `id`: ID заявки
            - `category_id`: ID категорії заявки
            - `location`: Деталі локації (широта, довгота, адреса)
            - `executor_id`: ID виконавця (волонтера)
            - `description`: Опис заявки
            - `is_in_progress`: Статус виконання
            - `is_done`: Статус завершення
            - `date_at`: Дата подачі заявки
            - `active_to`: Дата завершення активності заявки

        **Помилки**:
        - **403 Access denied**: Якщо користувач не є підтвердженим волонтером.
        - **400 Volunteer already has 3 applications in progress**: Якщо волонтер вже має 3 активні заявки.
        - **404 Application not found**: Якщо заявка з вказаним ID не знайдена.
        - **500 Internal Server Error**: Якщо сталася внутрішня помилка на сервері.

        **Приклад запиту**:
        ```
        POST /applications/accept/
        {
            "application_id": 123
        }
        ```

        **Приклад відповіді**:
        ```json
        {
            "id": 123,
            "category_id": 1,
            "location": {
                "latitude": 48.8588443,
                "longitude": 2.2943506,
                "address_name": "Paris, France"
            },
            "executor_id": 456,
            "description": "Заявка на прибирання",
            "is_in_progress": true,
            "is_done": false,
            "date_at": "2024-12-09T18:45:45",
            "active_to": "2025-12-09T00:00:00"
        }
        ```

        **Технічні деталі**:
        - Використовується асинхронний запит до бази даних через SQLAlchemy для отримання заявки і локації.
        - Перевірка, чи волонтер має право прийняти заявку на основі статусу підтвердження і кількості активних заявок.
        - Інформація про локацію включає широту, довготу та адресу.
        """
    if not current_volunteer.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    try:
        in_progress_query = await db.execute(
            select(models.Applications).where(
                models.Applications.executor_id == current_volunteer.id,
                models.Applications.is_in_progress.is_(True)
            )
        )
        in_progress_count = len(in_progress_query.scalars().all())

        if in_progress_count >= 3:
            raise HTTPException(status_code=400, detail="Volunteer already has 3 applications in progress.")

        application_query = await db.execute(
            select(models.Applications).where(models.Applications.id == app_id.application_id)
            .options(selectinload(models.Applications.location))
        )
        application = application_query.scalars().first()

        if not application:
            raise HTTPException(status_code=404, detail=f"Application with ID {app_id.application_id} not found")

        application.is_in_progress = True
        application.executor_id = current_volunteer.id

        await db.commit()

        location = application.location
        location_info = {
            "latitude": location.latitude if location else "Не вказано",
            "longitude": location.longitude if location else "Не вказано",
            "address_name": location.address_name if location else "Не вказано"
        }

        return JSONResponse(content={
            'id': application.id,
            'category_id': application.category_id,
            'location': location_info,
            'executor_id': application.executor_id,
            'description': application.description,
            'is_in_progress': application.is_in_progress,
            'is_done': application.is_done,
            'date_at': application.date_at,
            'active_to': application.active_to
        })

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@router.post('/applications/close/', status_code=200)
async def close_application(
        application_id: int = Form(...),
        files: List[UploadFile] = File(...),
        db: AsyncSession = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
    """
        **Закрити заявку, завантаживши файли та оновивши статус заявки.**

        Цей ендпоінт дозволяє волонтеру закрити заявку, прикріпивши файли (наприклад, звіти) і оновивши статус заявки на завершений.

        **Аргументи:**
        - **application_id**: Ідентифікатор заявки, яку потрібно закрити.
        - **files**: Список файлів, які волонтер додає до заявки.
        - **db**: Сесія бази даних для виконання запиту.
        - **current_volunteer**: Поточний авторизований волонтер.

        **Винятки:**
        - **403**: Якщо користувач не підтверджений.
          - Повертається повідомлення:
            ```json
            {
                "detail": "Access denied. User not verified by moderator"
            }
            ```
        - **404**: Якщо заявка не знайдена.
          - Повертається повідомлення:
            ```json
            {
                "detail": "Application with ID <application_id> not found"
            }
            ```
        - **400**: Якщо виникла помилка при збереженні файлів.
          - Повертається повідомлення:
            ```json
            {
                "detail": "Error saving file <filename>: <error_message>"
            }
            ```
        - **500**: Помилка сервера.
          - Повертається повідомлення:
            ```json
            {
                "detail": "An error occurred: <error_message>"
            }
            ```

        **Повертає:**
        - **200**: Якщо заявка успішно закрита, з доданими файлами.
          - Повертається список ID збережених файлів та ідентифікатор заявки:
            ```json
            {
                "files": [<file_id_1>, <file_id_2>, ...],
                "application_id": <application_id>
            }
            ```

        **Примітка:**
        - Файли зберігаються в окремій директорії на сервері, яка створюється на основі ідентифікатора заявки.
        - Після закриття заявки, її статус оновлюється на `is_done: True` і `is_in_progress: False`.
        """
    if not current_volunteer.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    try:

        result = await db.execute(select(models.Applications).filter(models.Applications.id == application_id))
        application = result.scalars().first()

        if not application:
            raise HTTPException(status_code=404, detail=f'Application with ID {application_id} not found')

        save_directory = f'saved_images/{application_id}'
        os.makedirs(save_directory, exist_ok=True)

        saved_files = []

        for file in files:
            try:

                file_path = os.path.join(save_directory, file.filename)
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(await file.read())

                media_entry = Media(
                    filepath=file_path,
                    creator_id=current_volunteer.id
                )
                db.add(media_entry)
                await db.flush()

                ink_media = Ink_ApplicationsMedia(
                    application_id=application.id,
                    media_id=media_entry.id
                )
                db.add(ink_media)

                saved_files.append(media_entry.id)

            except Exception as e:
                raise HTTPException(status_code=400, detail=f'Error saving file {file.filename}: {str(e)}')

        application.is_done = True
        application.is_in_progress = False
        await db.commit()

        return JSONResponse(content={
            'files': saved_files,
            'application_id': application.id
        })

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f'An error occurred: {str(e)}')


@router.post('/applications/cancel/', status_code=200)
async def cancel_application(
        app_id: AcceptApplicationBase,
        db: AsyncSession = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
    """
    **Скасувати заявку, яку прийняв поточний волонтер.**

    Цей ендпоінт дозволяє волонтеру скасувати заявку, яку він прийняв раніше. Заявка буде повернута в стан "не в процесі".

    **Аргументи:**
    - **app_id**: Ідентифікатор заявки, яку потрібно скасувати.
    - **db**: Сесія бази даних для виконання запиту.
    - **current_volunteer**: Поточний авторизований волонтер.

    **Винятки:**
    - **403**: Якщо волонтер не є авторизованим або якщо інший волонтер прийняв заявку.
      - Повертається повідомлення:
        ```json
        {
            "detail": "Access denied. User not verified by moderator"
        }
        ```
      або
        ```json
        {
            "detail": "Application accepted by user with ID <executor_id>, not by <current_volunteer_id>"
        }
        ```
    - **404**: Якщо заявка з вказаним ідентифікатором не знайдена.
      - Повертається повідомлення:
        ```json
        {
            "detail": "Application with ID <application_id> not found"
        }
        ```
    - **400**: Якщо сталася помилка при скасуванні заявки.
      - Повертається повідомлення:
        ```json
        {
            "detail": "Error: <error_message>"
        }
        ```

    **Повертає:**
    - **200**: Якщо заявка успішно скасована.
      - Повертається повідомлення:
        ```json
        {
            "status": "Application cancelled successfully"
        }
        ```

    **Примітка:**
    - Заявка буде повернута в стан "не в процесі" та скасовано призначення виконавця.
    """
    if not current_volunteer.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    try:
        result = await db.execute(select(models.Applications).filter(models.Applications.id == app_id.application_id))
        application = result.scalars().first()

        if not application:
            raise HTTPException(status_code=404, detail=f'Application with ID {app_id.application_id} not found')

        if current_volunteer.id == application.executor_id:

            application.is_in_progress = False
            application.is_done = False
            application.is_finished = False
            application.executor_id = None

            await db.commit()
            await db.refresh(application)

            return JSONResponse(status_code=200, content={"status": "Application cancelled successfully"})
        else:
            raise HTTPException(
                status_code=403,
                detail=f'Application accepted by user with ID {application.executor_id}, not by {current_volunteer.id}'
            )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error: {e}')


import math


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


@router.get('/applications/', response_model=List[ApplicationsList])
async def get_applications(
        type: Optional[str] = Query(..., description="Тип заявок: 'available', 'in_progress', 'finished'"),
        radius_km: float = Query(50000.0, description="Радіус пошуку заявок у кілометрах"),
        db: AsyncSession = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
    """
        **Отримати список заявок за типом.**

        - **type**: Тип заявок (обов'язково): 'available', 'in_progress', 'finished'.
            - `available`: Заявки, які доступні для виконання.
            - `in_progress`: Заявки, що знаходяться в процесі виконання (тільки для поточного волонтера).
            - `finished`: Завершені заявки.
        - **db**: Сесія бази даних для виконання запиту.
        - **current_volunteer**: Волонтер, який наразі аутентифікований в системі.

        **Відповідь:**
        - **200**: Список заявок, що відповідають вказаному типу. Повертається список об'єктів заявок.
        - **403**: Доступ заборонено для не верифікованих користувачів.
        - **404**: Некоректний тип заявок.
            - Повертається повідомлення:
              ```json
              {
                  "detail": "Invalid application type"
              }
              ```

        **Формат відповіді:**
        - **200**: Список заявок для запитуваного типу. Кожен елемент списку містить такі поля:
          ```json
          [
            {
                "id": 1,
                "description": "Опис заявки",
                "category_id": 2,
                "location": {
                    "latitude": 48.858844,
                    "longitude": 2.294351,
                    "address_name": "Ейфелева вежа, Париж"
                },
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
        - У разі помилки запиту або некоректного значення типу заявки повертається відповідь з помилкою.
        - Для отримання списку заявок необхідно вказати правильний тип: 'available', 'in_progress' або 'finished'.
        """
    if not current_volunteer.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    try:
        category_query = await db.execute(
            select(models.Ink_CustomerCategories.category_id).where(
                models.Ink_CustomerCategories.customer_id == current_volunteer.id
            )
        )
        categories = category_query.scalars().all()

        if not categories:
            categories = []

        volunteer_location_query = await db.execute(
            select(models.Locations.latitude, models.Locations.longitude).where(
                models.Locations.id == current_volunteer.location_id
            )
        )
        volunteer_location = volunteer_location_query.first()

        if volunteer_location is None or len(volunteer_location) != 2:
            raise HTTPException(status_code=404, detail="Volunteer location not found or invalid.")

        volunteer_latitude, volunteer_longitude = volunteer_location

        if type == 'available':
            current_time_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            query = select(models.Applications, models.Locations, models.Customer).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).join(
                models.Customer, models.Applications.creator_id == models.Customer.id
            ).filter(
                models.Applications.is_done.is_(False),
                models.Applications.is_in_progress.is_(False),
                models.Applications.is_active.is_(True),
                models.Applications.active_to > current_time_str
            )
            if categories:
                query = query.filter(models.Applications.category_id.in_(categories))

        elif type == 'in_progress':
            current_time_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            query = select(models.Applications, models.Locations, models.Customer).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).join(
                models.Customer, models.Applications.creator_id == models.Customer.id
            ).filter(
                models.Applications.is_in_progress.is_(True),
                models.Applications.executor_id == current_volunteer.id,
                models.Applications.is_done.is_(False),
                models.Applications.is_active.is_(True),
                models.Applications.active_to > current_time_str  # Порівняння рядків
            )

        elif type == 'finished':
            current_time_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            query = select(models.Applications, models.Locations, models.Customer).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).join(
                models.Customer, models.Applications.creator_id == models.Customer.id
            ).filter(
                models.Applications.is_done.is_(True),
                models.Applications.executor_id == current_volunteer.id,
                models.Applications.is_active.is_(True),
                models.Applications.active_to > current_time_str
            )

        else:
            raise HTTPException(status_code=404, detail="Invalid application type")

        result = await db.execute(query)
        applications = result.fetchall()

        response_data = []
        for application in applications:
            app_latitude = application.Locations.latitude
            app_longitude = application.Locations.longitude
            distance = haversine(volunteer_latitude, volunteer_longitude, app_latitude, app_longitude)

            if distance <= radius_km:
                response_data.append({
                    "id": application.Applications.id,
                    "description": application.Applications.description,
                    "category_id": application.Applications.category_id,
                    "location": {
                        "latitude": app_latitude,
                        "longitude": app_longitude,
                        "address_name": application.Locations.address_name
                    },
                    "creator": {
                        "id": application.Customer.id,
                        "first_name": application.Customer.firstname,
                        "phone_num": application.Customer.phone_num
                    },
                    "executor_id": application.Applications.executor_id,
                    "is_in_progress": application.Applications.is_in_progress,
                    "is_done": application.Applications.is_done,
                    "date_at": application.Applications.date_at,
                    "active_to": application.Applications.active_to,
                    "distance": round(distance, 1)
                })

        if not response_data:
            return JSONResponse(content={"detail": "No applications found within the specified radius."},
                                status_code=200)

        return JSONResponse(content=response_data, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


from sqlalchemy import func


@router.get('/rating/', status_code=200)
async def get_volunteer_rating(
        db: AsyncSession = Depends(get_db),
        current_user: models.Customer = Depends(get_current_volonter)
):
    """
    **Отримати рейтинг волонтерів на основі кількості закритих заявок.**

    Цей ендпоінт дозволяє отримати список волонтерів, відсортованих за кількістю закритих заявок. Рейтинг базується на тому, скільки заявок було успішно закрито кожним волонтером.

    **Аргументи:**
    - **db**: Залежність для асинхронного підключення до бази даних.
    - **current_user**: Поточний авторизований волонтер.

    **Винятки:**
    - **403**: Якщо користувач не є авторизованим або не є перевіреним модератором.
      - Повертається повідомлення:
        ```json
        {
            "detail": "Access denied. User not verified by moderator"
        }
        ```
    - **500**: Якщо виникла помилка при виконанні запиту до бази даних.
      - Повертається повідомлення:
        ```json
        {
            "detail": "Error: <error_message>"
        }
        ```

    **Повертає:**
    - **200**: Успішний запит з інформацією про волонтерів та кількість закритих заявок, відсортовану за кількістю:
      ```json
      [
          {
              "volunteer_name": "Ім'я Прізвище",
              "closed_app_count": <number_of_closed_applications>
          },
          ...
      ]
      ```

    **Примітка:**
    - Заявки, які вважаються "закритими", це ті, що мають статус `is_done = True`.
    """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

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

        response_data = [{
            "volunteer_name": f"{volunteer.firstname} {volunteer.lastname}",
            "closed_app_count": closed_app_count
        } for volunteer, closed_app_count in volunteer_data]

        return JSONResponse(content=response_data, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error: {e}')
