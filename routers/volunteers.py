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

        Цей ендпоінт дозволяє деактивувати профіль волонтера. Після деактивації волонтер не зможе більше користуватися своїм профілем.

        **Аргументи:**
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
        - **404**: Якщо профіль волонтера не знайдений.
          - Повертається повідомлення:
            ```json
            {
                "detail": "Customer with Telegram ID <tg_id> not found"
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

        **Примітка:**
        - Профіль може бути деактивований тільки після підтвердження користувача.
        """
    if not current_volunteer.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    try:
        result = await db.execute(
            select(models.Customer).filter(models.Customer.tg_id == current_volunteer.tg_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            raise HTTPException(status_code=404,
                                detail=f'Customer with Telegram ID {current_volunteer.tg_id} not found')

        profile.is_active = False
        await db.commit()

        return None

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error: {e}')


@router.post('/applications/accept/', status_code=200)
async def accept_application(
        app_id: AcceptApplicationBase,
        db: AsyncSession = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
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
        )
        application = application_query.scalars().first()

        if not application:
            raise HTTPException(status_code=404, detail=f"Application with ID {app_id.application_id} not found")

        application.is_in_progress = True
        application.executor_id = current_volunteer.id

        await db.commit()

        return JSONResponse(content={
            'id': application.id,
            'category_id': application.category_id,
            'location_id': application.location_id,
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


@router.get('/applications/', response_model=List[ApplicationsList])
async def get_applications(
        type: Optional[str] = Query(..., description="Тип заявок: 'available', 'in_progress', 'finished'"),
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
        # Отримуємо категорію волонтера через Ink_CustomerCategories
        category_query = await db.execute(
            select(models.Ink_CustomerCategories.category_id).where(
                models.Ink_CustomerCategories.customer_id == current_volunteer.id
            )
        )
        category = category_query.scalars().first()

        if not category:
            raise HTTPException(status_code=404, detail="Category for volunteer not found.")

        if type == 'available':
            query = select(models.Applications, models.Locations).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).filter(
                models.Applications.is_done.is_(False),
                models.Applications.is_in_progress.is_(False),
                models.Applications.is_active.is_(True),
                models.Applications.category_id == category
            )
        elif type == 'in_progress':
            query = select(models.Applications, models.Locations).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).filter(
                models.Applications.is_in_progress.is_(True),
                models.Applications.executor_id == current_volunteer.id,
                models.Applications.is_done.is_(False),
                models.Applications.is_active.is_(True)
            )
        elif type == 'finished':
            query = select(models.Applications, models.Locations).join(
                models.Locations, models.Applications.location_id == models.Locations.id
            ).filter(
                models.Applications.is_done.is_(True),
                models.Applications.executor_id == current_volunteer.id,
                models.Applications.is_active.is_(True)
            )
        else:
            raise HTTPException(status_code=404, detail="Invalid application type")

        result = await db.execute(query)
        applications = result.fetchall()

        response_data = [
            {
                "id": application.Applications.id,
                "description": application.Applications.description,
                "category_id": application.Applications.category_id,
                "location": {
                    "latitude": application.Locations.latitude,
                    "longitude": application.Locations.longitude,
                    "address_name": application.Locations.address_name
                },
                "executor_id": application.Applications.executor_id,
                "is_in_progress": application.Applications.is_in_progress,
                "is_done": application.Applications.is_done,
                "date_at": application.Applications.date_at,
                "active_to": application.Applications.active_to
            }
            for application in applications
        ]

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
