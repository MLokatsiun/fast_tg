from typing import List, Optional
from fastapi import Depends, HTTPException, APIRouter, Query
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from database import get_db
from datetime import datetime
from business_logical import (get_current_beneficiary, get_coordinates)
import models
from schemas import ApplicationCreate, ApplicationDelete, ApplicationConfirm, ApplicationsList

router = APIRouter()


@router.delete("/profile/", status_code=200)
async def delete_beneficiary(current_user=Depends(get_current_beneficiary), db: Session = Depends(get_db)):
    """
        Видалити бенефіціара.

        - **current_user**: Бенефіціар, який наразі аутентифікований в системі.
        - **db**: Сесія бази даних.

        **Відповідь:**
        - 200: Бенефіціар успішно видалений.
        - 404: Бенефіціара не знайдено.
    """

    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    beneficiary = db.query(models.Customer).filter(models.Customer.id == current_user.id).first()
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Beneficiary not found")

    db.delete(beneficiary)
    db.commit()

    return {"detail": "Beneficiary deleted successfully"}


@router.post("/applications/", status_code=201)
async def create_application(application: ApplicationCreate, db: Session = Depends(get_db),
                             current_user=Depends(get_current_beneficiary)):
    """
        Видалити бенефіціара.

        - **current_user**: Бенефіціар, який наразі аутентифікований в системі.
        - **db**: Сесія бази даних.

        **Відповідь:**
        - 200: Бенефіціар успішно видалений.
        - 404: Бенефіціара не знайдено.
    """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    if application.address:
        coordinates = get_coordinates(application.address)
        latitude, longitude = coordinates["latitude"], coordinates["longitude"]
    elif application.latitude and application.longitude:
        latitude, longitude = application.latitude, application.longitude
    else:
        raise HTTPException(status_code=400, detail="Provide either address or both latitude and longitude.")

    existing_location = db.query(models.Locations).filter(
        models.Locations.latitude == latitude,
        models.Locations.longitude == longitude
    ).first()

    if existing_location:
        location_id = existing_location.id
    else:
        new_location = models.Locations(latitude=latitude, longitude=longitude, address_name=application.address)
        db.add(new_location)
        db.commit()
        db.refresh(new_location)
        location_id = new_location.id

    new_application = models.Applications(
        creator_id=current_user.id,
        category_id=application.category_id,
        location_id=location_id,
        description=application.description,
        is_in_progress=False,
        is_done=False,
        is_finished=False,
        date_at=str(datetime.utcnow())
    )

    db.add(new_application)
    db.commit()
    db.refresh(new_application)

    return {
        "id": new_application.id,
        "creator_id": current_user.id,
        "location_id": new_application.location_id,
        "description": new_application.description
    }



@router.put("/applications/", status_code=200)
async def confirm_application(
        application_confirm: ApplicationConfirm,
        db: Session = Depends(get_db),
        current_user: models.Customer = Depends(get_current_beneficiary)  # Залежність для бенефіціара
):
    """
            Підтвердити виконання заявки.

            - **application_confirm**: Об'єкт типу `ApplicationConfirm`, що містить ID заявки.
            - **db**: Сесія бази даних.
            - **current_user**: Бенефіціар, який наразі аутентифікований в системі.

            **Відповідь:**
            - 200: Заявка успішно підтверджена.
            - 404: Заявку не знайдено.
            - 400: Виконавець не призначений, або завдання не позначене як виконане.
        """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    application = db.query(models.Applications).filter(
        models.Applications.id == application_confirm.application_id).first()

    if not application:
        raise HTTPException(status_code=404, detail='Application not found')

    if application.executor_id is None:
        raise HTTPException(status_code=400, detail='No executor assigned to the application')

    if not application.is_done:
        raise HTTPException(status_code=400, detail='The task has not been marked as done by the executor')

    application.is_finished = True
    db.commit()

    return {"detail": "Application confirmed successfully"}


# Видалення заявки
@router.delete("/applications/", status_code=204)
async def delete_application(
        application_delete: ApplicationDelete,
        db: Session = Depends(get_db),
        current_user: models.Customer = Depends(get_current_beneficiary)  # Залежність для бенефіціара
):
    """
            Видалити заявку.

            - **application_delete**: Об'єкт типу `ApplicationDelete`, що містить ID заявки.
            - **db**: Сесія бази даних.
            - **current_user**: Бенефіціар, який наразі аутентифікований в системі.

            **Відповідь:**
            - 204: Заявка успішно видалена.
            - 404: Заявку не знайдено.
        """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")

    application = db.query(models.Applications).filter(
        models.Applications.id == application_delete.application_id).first()

    if not application:
        raise HTTPException(status_code=404, detail='Application not found')

    application.is_active = False
    db.commit()


@router.get('/applications/', response_model=List[ApplicationsList])
async def get_applications(
        type: Optional[str] = Query(..., description="Тип заявок: 'available', 'in_progress', 'finished'"),
        db: Session = Depends(get_db),
        current_user: str = Depends(get_current_beneficiary)
):
    """
    Отримати список заявок за типом.

    - **type**: Тип заявок (обов'язково): 'available', 'in_progress', 'finished'.
    - **db**: Сесія бази даних.
    - **current_user**: Бенефіціар, який наразі аутентифікований в системі.

    **Відповідь:**
    - 200: Список заявок, що відповідають вказаному типу.
    - 404: Некоректний тип заявок.
    """
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Access denied. User not verified by moderator")
    try:

        if type == 'available':
            applications = db.query(models.Applications).filter(
                models.Applications.creator_id == current_user.id,
                models.Applications.is_done.is_(False),
                models.Applications.is_in_progress.is_(False)
            ).all()
        elif type == 'in_progress':
            applications = db.query(models.Applications).filter(
                models.Applications.creator_id == current_user.id,
                models.Applications.is_in_progress.is_(True),
                models.Applications.is_done.is_(False)
            ).all()
        elif type == 'finished':
            applications = db.query(models.Applications).filter(
                models.Applications.creator_id == current_user.id,
                models.Applications.is_done.is_(True)
            ).all()
        else:
            raise HTTPException(status_code=404, detail='Invalid applications type')

        response_data = [
            {
                'id': application.id,
                'description': application.description,
                'category_id': application.category_id,
                'location_id': application.location_id,
                'executor_id': application.executor_id,
                'is_in_progress': application.is_in_progress,
                'is_done': application.is_done,
                'date_at': application.date_at,
                'active_to': application.active_to
            }
            for application in applications
        ]

        return JSONResponse(content=response_data, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error: {str(e)}')
