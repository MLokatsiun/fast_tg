from typing import List, Optional
from fastapi import Depends, HTTPException, APIRouter, Query
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from database import get_db
from datetime import datetime
from business_logical import (get_current_beneficiary, get_coordinates)
import models
from schemas import BeneficiaryCreate, ApplicationCreate, ApplicationDelete, ApplicationConfirm, ApplicationsList

router = APIRouter()

# @router.post("/register/", status_code=201)
# async def sign_up_beneficiary(
#         beneficiary: BeneficiaryCreate,
#         db: Session = Depends(get_db)
# ):
#     """
#         Реєстрація нового бенефіціара з паролем та клієнтом (frontend чи telegram).
#     """
#     # Перевірка чи вже існує бенефіціар з таким телефоном і TG ID
#     existing_beneficiary = db.query(models.Customer).filter(
#         models.Customer.phone_num == beneficiary.phone_num,
#         models.Customer.tg_id == beneficiary.tg_id
#     ).first()
#
#     if existing_beneficiary:
#         raise HTTPException(status_code=400, detail="Beneficiary with this phone number and TG ID already exists.")
#
#     # Перевірка клієнта
#     client = db.query(models.Client).filter(models.Client.name == beneficiary.client).first()
#     if not client:
#         raise HTTPException(status_code=400, detail="Invalid client name")
#
#     # Перевірка пароля на сервері
#     clients = {
#         "telegram": "1234",  # Пароль для телеграма
#         "frontend": "4321",  # Пароль для фронтенду
#     }
#
#     # Перевірка, чи є клієнт і чи пароль правильний
#     if beneficiary.client not in clients or not verify_password(beneficiary.password, clients[beneficiary.client]):
#         raise HTTPException(status_code=400, detail="Incorrect password for the client.")
#
#     # Створюємо нового бенефіціара
#     new_beneficiary = models.Customer(
#         phone_num=beneficiary.phone_num,
#         tg_id=beneficiary.tg_id,
#         firstname=beneficiary.firstname,
#         lastname=beneficiary.lastname,
#         patronymic=beneficiary.patronymic,
#         client_id=client.id,  # Пов'язуємо з клієнтом
#
#     )
#
#     db.add(new_beneficiary)
#     db.commit()
#     db.refresh(new_beneficiary)
#
#     return {
#         "id": new_beneficiary.id,
#         "phone_num": new_beneficiary.phone_num,
#         "tg_id": new_beneficiary.tg_id,
#         "firstname": new_beneficiary.firstname,
#         "lastname": new_beneficiary.lastname
#     }


@router.delete("/profile/", status_code=200)
async def delete_beneficiary(current_user=Depends(get_current_beneficiary), db: Session = Depends(get_db)):
    """
        Delete a beneficiary.

        - **current_user**: The beneficiary currently authenticated in the system.
        - **db**: The database session.

        **Response:**
        - 200: Successfully deleted the beneficiary.
        - 404: Beneficiary not found.
    """
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
       Create a new application.

       - **application**: An object of type `ApplicationCreate` containing application data.
       - **db**: The database session.
       - **current_user**: The beneficiary currently authenticated in the system.

       **Response:**
       - 201: Successfully created a new application with its data.
       - 400: Neither address nor coordinates were provided.
    """

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
        Confirm the execution of an application.

        - **application_confirm**: An object of type `ApplicationConfirm` containing the application ID.
        - **db**: The database session.
        - **current_user**: The beneficiary currently authenticated in the system.

        **Response:**
        - 200: Successfully confirmed the application.
        - 404: Application not found.
        - 400: No executor assigned, or the task has not been marked as done.
    """
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
        Delete an application.

        - **application_delete**: An object of type `ApplicationDelete` containing the application ID.
        - **db**: The database session.
        - **current_user**: The beneficiary currently authenticated in the system.

        **Response:**
        - 204: Successfully deleted the application.
        - 404: Application not found.
    """
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
    Retrieve a list of applications by type.

    - **type**: The type of applications (required): 'available', 'in_progress', 'finished'.
    - **db**: The database session.
    - **current_user**: The beneficiary currently authenticated in the system.

    **Response:**
    - 200: A list of applications corresponding to the specified type.
    - 404: Invalid applications type.
    """
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
