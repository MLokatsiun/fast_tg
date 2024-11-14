from fastapi import Depends, HTTPException, APIRouter, Query
from sqlalchemy.orm import Session
import os
import base64
from fastapi.responses import JSONResponse
from sqlalchemy.sql.functions import current_user

from database import get_db
from business_logical import (get_current_volonter, get_coordinates, get_current_user)
import models
from schemas import CreateCustomerBase, EditCustomerBase, CloseApplicationBase, AcceptApplicationBase
from typing import Optional

router = APIRouter()


@router.put('/profile/')
async def edit_customer(
        customer_info: EditCustomerBase,
        db: Session = Depends(get_db),
        volunteer: models.Customer = Depends(get_current_volonter)
):
    """
    Редагувати профіль існуючого волонтера.

    Аргументи:
        customer_info (EditCustomerBase): Інформація для редагування профілю волонтера.
        db (Session): Залежність для підключення до бази даних.
        volunteer (models.Customer): Поточний авторизований волонтер.

    Винятки:
        HTTPException: Якщо профіль волонтера не може бути оновлений або доступ до нього обмежений.

    Повертає:
        JSONResponse: Відповідь з оновленою інформацією волонтера.
    """
    if not volunteer.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    try:
        customer = volunteer


        if customer_info.location is not None:

            if customer_info.location.latitude is None or customer_info.location.longitude is None:
                if customer_info.location.address:
                    coordinates = get_coordinates(customer_info.location.address)
                    latitude = coordinates["latitude"]
                    longitude = coordinates["longitude"]
                else:
                    raise HTTPException(status_code=400, detail="Provide either coordinates or an address.")
            else:
                latitude = customer_info.location.latitude
                longitude = customer_info.location.longitude


            location = db.query(models.Locations).filter(
                models.Locations.latitude == latitude,
                models.Locations.longitude == longitude,
                models.Locations.address_name == customer_info.location.address
            ).first()


            if not location:
                location = models.Locations(
                    latitude=latitude,
                    longitude=longitude,
                    address_name=customer_info.location.address
                )
                db.add(location)
                db.commit()


            customer.location_id = location.id

        if customer_info.categories is not None:
            current_categories = db.query(models.Ink_CustomerCategories).filter(
                models.Ink_CustomerCategories.customer_id == customer.id).all()

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
                category_to_remove = db.query(models.Ink_CustomerCategories).filter_by(
                    customer_id=customer.id,
                    category_id=category_id
                ).first()
                if category_to_remove:
                    db.delete(category_to_remove)

            db.commit()

        db.refresh(customer)

        return JSONResponse(status_code=200, content={
            'id': customer.id,
            'phone_num': customer.phone_num,
            'tg_id': customer.tg_id,
            'firstname': customer.firstname,
            'lastname': customer.lastname,
            'categories': customer_info.categories,
            'location': customer.location_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error: {str(e)}')


@router.delete('/profile/', status_code=204)
async def delete_profile(
        db: Session = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):

    """
    Видалити профіль поточного волонтера.

    Аргументи:
        db (Session): Залежність для підключення до бази даних.
        current_volunteer (models.Customer): Поточний авторизований волонтер.

    Винятки:
        HTTPException: Якщо профіль волонтера не знайдений або виникла помилка при його видаленні.

    Повертає:
        None: Успішне видалення профілю.
    """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")
    try:
        profile = db.query(models.Customer).filter(models.Customer.tg_id == current_volunteer.tg_id).first()

        if not profile:
            raise HTTPException(status_code=404,
                                detail=f'Customer with Telegram ID {current_volunteer.tg_id} not found')

        db.delete(profile)
        db.commit()

        return

    except Exception as e:
        raise HTTPException(status_code=404, detail=f'Error {e}')


@router.post('/applications/accept/', status_code=200)
async def accept_application(
        app_id: AcceptApplicationBase,
        db: Session = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
    """
    Прийняти заявку, призначивши її виконання поточному волонтеру.

    Аргументи:
        app_id (AcceptApplicationBase): ID заявки для прийняття.
        db (Session): Залежність для підключення до бази даних.
        current_volunteer (models.Customer): Поточний авторизований волонтер.

    Винятки:
        HTTPException: Якщо заявка не знайдена або неможливо її прийняти.

    Повертає:
        JSONResponse: Відповідь з деталями прийнятої заявки.
    """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")
    try:
        customer = db.query(models.Customer).filter(models.Customer.tg_id == current_volunteer.tg_id).first()

        if not customer:
            raise HTTPException(status_code=404, detail="Volunteer not found.")

        application = db.query(models.Applications).filter(models.Applications.id == app_id.application_id).first()

        if application:
            application.is_in_progress = True
            application.executor_id = customer.id
            db.commit()

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
        else:
            raise HTTPException(status_code=404, detail=f'Application with ID {app_id.application_id} not found')

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error {e}')


@router.post('/applications/close/', status_code=200)
async def close_application(
        close_info: CloseApplicationBase,
        db: Session = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
    """
        Закрити заявку після її виконання, зберігаючи файли.

        Аргументи:
            close_info (CloseApplicationBase): Інформація про заявку, яку треба закрити, і файли, що зберігаються.
            db (Session): Залежність для підключення до бази даних.
            current_volunteer (models.Customer): Поточний авторизований волонтер.

        Винятки:
            HTTPException: Якщо заявка не знайдена, неможливо зберегти файли або виникла інша помилка.

        Повертає:
            JSONResponse: Відповідь з деталями закритої заявки та її файлів.
        """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")
    try:
        application = db.query(models.Applications).filter(models.Applications.id == close_info.application_id).first()
        if not application:
            raise HTTPException(status_code=404, detail=f'Application with ID {close_info.application_id} not found')

        save_directory = f'saved_images/{close_info.application_id}'
        os.makedirs(save_directory, exist_ok=True)

        for image in close_info.files:
            try:
                image_bytes = base64.b64decode(image.images)
                image_path = os.path.join(save_directory, image.filename)
                with open(image_path, 'wb') as f:
                    f.write(image_bytes)

            except Exception as e:
                raise HTTPException(status_code=400, detail=f'Error saving file {image.filename}: {str(e)}')

        create_media = models.Media(
            filepath=save_directory,
            creator_id=current_volunteer.id
        )
        db.add(create_media)
        db.flush()

        create_ink_media = models.Ink_ApplicationsMedia(
            application_id=application.id,
            media_id=create_media.id
        )
        db.add(create_ink_media)

        application.is_done = True
        application.is_in_progress = False
        db.commit()

        return JSONResponse(content={
            'files': [{'filename': file.filename} for file in close_info.files],
            'application_id': application.id
        })

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f'An error occurred: {str(e)}')


@router.post('/applications/cancel/', status_code=200)
async def cancel_application(
        app_id: CloseApplicationBase,
        db: Session = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
    """
    Cancel an application accepted by the current volunteer.

    Args:
        app_id (AcceptApplicationBase): The ID of the application to cancel.
        db (Session): The database session dependency.
        current_volunteer (models.Customer): The current logged-in volunteer.

    Raises:
        HTTPException: If the application cannot be found or canceled.

    Returns:
        JSONResponse: A response indicating successful cancellation.
    """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")
    try:
        application = db.query(models.Applications).filter(models.Applications.id == app_id.application_id).first()

        if not application:
            raise HTTPException(status_code=404, detail=f'Application with ID {app_id.application_id} not found')

        if current_volunteer.id == application.executor_id:
            application.is_in_progress = False
            application.is_done = False
            application.is_finished = False
            application.executor_id = None
            db.commit()
            db.refresh(application)
            return JSONResponse(status_code=200, content={"status": "Application cancelled successfully"})
        else:
            raise HTTPException(
                status_code=403,
                detail=f'Application accepted by user with ID {application.executor_id}, not by {current_volunteer.id}'
            )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error: {e}')


@router.get('/applications/get')
async def get_applications(
        db: Session = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter),
        type: Optional[str] = Query(...)
):
    """
        Скасувати заявку, якщо вона була прийнята волонтером.

        Аргументи:
            app_id (CloseApplicationBase): ID заявки для скасування.
            db (Session): Залежність для підключення до бази даних.
            current_volunteer (models.Customer): Поточний авторизований волонтер.

        Винятки:
            HTTPException: Якщо заявка не знайдена або волонтер не має доступу до її скасування.

        Повертає:
            JSONResponse: Відповідь з деталями скасованої заявки.
        """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")
    try:
        if type == 'available':
            applications = db.query(models.Applications).filter(
                models.Applications.is_done == False,
                models.Applications.is_in_progress == False
            ).all()
        elif type == 'in_progress':
            applications = db.query(models.Applications).filter(
                models.Applications.is_in_progress == True,
                models.Applications.is_done == False
            ).all()
        elif type == 'finished':
            applications = db.query(models.Applications).filter(
                models.Applications.is_done == True
            ).all()
        else:
            raise HTTPException(status_code=404, detail='Invalid application type')

        response_data = [{
            'id': application.id,
            'description': application.description,
            'category_id': application.category_id,
            'location_id': application.location_id,
            'executor_id': application.executor_id,
            'is_in_progress': application.is_in_progress,
            'is_done': application.is_done,
            'date_at': application.date_at,
            'active_to': application.active_to,
        } for application in applications]

        return JSONResponse(content=response_data, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error: {e}')


from sqlalchemy import func


@router.get('/rating/', status_code=200)
async def get_volunteer_rating(
        db: Session = Depends(get_db),
):
    """
    Отримати рейтинг волонтерів на основі кількості закритих заявок.

    Аргументи:
        db (Session): Залежність для підключення до бази даних.
        current_user (models.Customer): Поточний авторизований користувач (волонтер).

    Винятки:
        HTTPException: Якщо користувач не авторизований або виникла помилка при отриманні даних.

    Повертає:
        JSONResponse: Список волонтерів з кількістю закритих заявок, відсортованих за цією кількістю.
    """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")
    try:
        results = (
            db.query(
                models.Customer,
                func.count(models.Applications.id).label('closed_app_count')
            )
            .join(models.Applications, models.Applications.executor_id == models.Customer.id)
            .filter(models.Applications.is_done == True, models.Applications.executor_id == models.Customer.id)
            .group_by(models.Customer.id)
            .order_by(func.count(models.Applications.id).desc())
            .all()
        )

        response_data = [{
            "volunteer_name": f"{volunteer.firstname} {volunteer.lastname}",
            "closed_app_count": closed_app_count
        } for volunteer, closed_app_count in results]

        return JSONResponse(content=response_data, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error: {e}')
