from fastapi import FastAPI, Depends
from routers.beneficiaries import router as beneficiary_router
from routers.moderators import router as moderator_router
from routers.authorization import router as auth_router
from routers.volonters import router as volunteer_router
import uvicorn
from models import Client, Roles
from sqlalchemy.orm import Session
from database import get_db
app = FastAPI()

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(volunteer_router, prefix="/volunteer", tags=["Volunteer"])
app.include_router(beneficiary_router, prefix="/beneficiary", tags=["Beneficiary"])
app.include_router(moderator_router, prefix="/moderator", tags=["Moderator"])


@app.on_event("startup")
def startup_event():
    db = next(get_db())
    try:
        if not db.query(Roles).filter_by(name="beneficiary").first():
            db.add(Roles(name="beneficiary"))
        if not db.query(Roles).filter_by(name="volunteer").first():
            db.add(Roles(name="volunteer"))

        if not db.query(Client).filter_by(name="telegram").first():
            db.add(Client(name="telegram"))
        if not db.query(Client).filter_by(name="frontend").first():
            db.add(Client(name="frontend"))

        db.commit()
    finally:
        db.close()
