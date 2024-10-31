from fastapi import APIRouter
from fastapi import  Depends, HTTPException
from sqlalchemy.orm import Session
import models
from business_logical import get_current_moderator
from schemas import CategoryCreate, CategoryDelete, ApplicationDelete
from database import get_db


router = APIRouter()

@router.post("/categories/", status_code=201)
async def create_category(category: CategoryCreate, db: Session = Depends(get_db), current_moderator=Depends(get_current_moderator)):
    new_category = models.Categories(
        name=category.name,
        parent_id=category.parent_id,
        active_duration=None
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
async def delete_category(category_delete: CategoryDelete, db: Session = Depends(get_db), current_moderator=Depends(get_current_moderator)):
    category = db.query(models.Categories).filter(models.Categories.id == category_delete.id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db.delete(category)
    db.commit()
    return {"detail": "Category deleted successfully"}

@router.delete("/applications/", status_code=204)
async def delete_application(application_delete: ApplicationDelete, db: Session = Depends(get_db), current_moderator=Depends(get_current_moderator)):
    application = db.query(models.Applications).filter(models.Applications.id == application_delete.application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    db.delete(application)
    db.commit()
    return {"detail": "Application deleted successfully"}
