from fastapi import Depends, HTTPException, APIRouter, Query
from sqlalchemy.orm import Session
import os
import base64
from fastapi.responses import JSONResponse
from database import get_db
from business_logical import (get_current_volonter, get_coordinates, )
import models
from schemas import CreateCustomerBase, EditCustomerBase, CloseApplicationBase, AcceptApplicationBase
from typing import Optional

router = APIRouter()


@router.post("/volunteer/", status_code=200)
async def create_volunteer(
        volunteer_info: CreateCustomerBase,
        db: Session = Depends(get_db)
):
    """
        Create a new volunteer in the database.

        Args:
            volunteer_info (CreateCustomerBase): The volunteer information including
                                                  phone number, Telegram ID, and address.
            db (Session): The database session dependency.

        Raises:
            HTTPException: If the volunteer already exists or if the address/coordinates
                           are not provided.

        Returns:
            dict: A dictionary containing the created volunteer's information.
    """
    try:
        existing_volunteer = db.query(models.Customer).filter(
            models.Customer.phone_num == volunteer_info.phone_num
        ).first()

        if existing_volunteer:
            raise HTTPException(status_code=400, detail="Volunteer with this phone number already exists.")

        if volunteer_info.address:
            coordinates = get_coordinates(volunteer_info.address)
            latitude, longitude = coordinates["latitude"], coordinates["longitude"]
        elif volunteer_info.latitude is not None and volunteer_info.longitude is not None:
            latitude, longitude = volunteer_info.latitude, volunteer_info.longitude
        else:
            raise HTTPException(status_code=400, detail="Provide either address or both latitude and longitude.")

        create_location = models.Locations(
            latitude=latitude,
            longitude=longitude,
            address_name=volunteer_info.address
        )

        create_volunteer = models.Customer(
            phone_num=volunteer_info.phone_num,
            tg_id=volunteer_info.tg_id,
            firstname=volunteer_info.firstname,
            lastname=volunteer_info.lastname,
            patronymic=volunteer_info.patronymic,
            location_id=create_location.id
        )

        db.add(create_location)
        db.commit()
        db.refresh(create_location)

        create_volunteer.location_id = create_location.id
        db.add(create_volunteer)
        db.commit()
        db.refresh(create_volunteer)

        return {
            'id': create_volunteer.id,
            'phone_num': create_volunteer.phone_num,
            'tg_id': create_volunteer.tg_id,
            'firstname': create_volunteer.firstname,
            'lastname': create_volunteer.lastname,
            'patronymic': create_volunteer.patronymic,
            'location': create_location.id
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f'Error {e}')


@router.put('/volunteer/profile/')
async def edit_customer(customer_info: EditCustomerBase, db: Session = Depends(get_db),
                        volunteer: models.Customer = Depends(get_current_volonter)):
    """
        Edit an existing volunteer's profile.

        Args:
            customer_info (EditCustomerBase): Information for editing the volunteer's profile.
            db (Session): The database session dependency.
            volunteer (models.Customer): The current logged-in volunteer.

        Raises:
            HTTPException: If the volunteer's profile cannot be updated.

        Returns:
            JSONResponse: A response containing the updated volunteer's information.
    """
    try:
        customer = volunteer

        if customer_info.location is not None:
            if customer_info.location.latitude is None or customer_info.location.longitude is None:
                if customer_info.location.address_name:
                    coordinates = get_coordinates(customer_info.location.address_name)
                    latitude = coordinates["latitude"]
                    longitude = coordinates["longitude"]
                else:
                    raise HTTPException(status_code=400, detail="Provide either coordinates or an address.")
            else:
                latitude = customer_info.location.latitude
                longitude = customer_info.location.longitude

            if customer.location_id:
                location = db.query(models.Locations).filter(models.Locations.id == customer.location_id).first()
                if location:
                    location.latitude = latitude
                    location.longitude = longitude
                    location.address_name = customer_info.location.address_name
                else:
                    create_location = models.Locations(
                        latitude=latitude,
                        longitude=longitude,
                        address_name=customer_info.location.address_name
                    )
                    db.add(create_location)
                    db.commit()
                    customer.location_id = create_location.id
            else:
                create_location = models.Locations(
                    latitude=latitude,
                    longitude=longitude,
                    address_name=customer_info.location.address_name
                )
                db.add(create_location)
                db.commit()
                customer.location_id = create_location.id

            db.commit()

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
        raise HTTPException(status_code=404, detail=f'Error {e}')


@router.delete('/volunteer/profile/', status_code=204)
async def delete_profile(
        db: Session = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
    """
        Delete the current volunteer's profile.

        Args:
            db (Session): The database session dependency.
            current_volunteer (models.Customer): The current logged-in volunteer.

        Raises:
            HTTPException: If the volunteer's profile cannot be found or deleted.

        Returns:
            None: Indicates successful deletion.
    """
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


@router.post('/volunteer/applications/accept/', status_code=200)
async def accept_application(
        app_id: AcceptApplicationBase,
        db: Session = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
    """
        Accept an application assigned to the current volunteer.

        Args:
            app_id (AcceptApplicationBase): The ID of the application to be accepted.
            db (Session): The database session dependency.
            current_volunteer (models.Customer): The current logged-in volunteer.

        Raises:
            HTTPException: If the application cannot be found or accepted.

        Returns:
            JSONResponse: A response containing the accepted application's details.
    """
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


@router.post('/volunteer/applications/close/', status_code=200)
async def close_application(
        close_info: CloseApplicationBase,
        db: Session = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter)
):
    """
    Close an application by saving images and updating its status.

    Args:
        close_info (CloseApplicationBase): Information about the application to close and associated files.
        db (Session): The database session dependency.
        current_volunteer (models.Customer): The current logged-in volunteer.

    Raises:
        HTTPException: If the application cannot be found, closed, or if there is an error saving files.

    Returns:
        JSONResponse: A response containing details of the closed application.
    """
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


@router.post('/volunteer/applications/cancel/', status_code=200)
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


@router.get('/volunteer/applications/get')
async def get_applications(
        db: Session = Depends(get_db),
        current_volunteer: models.Customer = Depends(get_current_volonter),
        type: Optional[str] = Query(...)
):
    """
        Get a list of applications based on their status.

        Args:
            type (str): The type of applications to retrieve (available, in_progress, finished).
            db (Session): The database session dependency.
            current_volunteer (models.Customer): The current logged-in volunteer.

        Raises:
            HTTPException: If the application type is invalid or if an error occurs.

        Returns:
            JSONResponse: A list of applications matching the requested type.
    """
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


#
#
from sqlalchemy import func


@router.get('/volunteer/rating/', status_code=200)
async def get_volunteer_rating(
        db: Session = Depends(get_db),
):
    """
        Get the rating of volunteers based on their completed applications.

        Args:
            db (Session): The database session dependency.
            current_volunteer (models.Customer): The current logged-in volunteer.

        Raises:
            HTTPException: If an error occurs while fetching the rating.

        Returns:
            JSONResponse: A list of volunteer ratings.
    """
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
