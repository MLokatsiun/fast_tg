from fastapi import FastAPI, Depends, HTTPException
from routers.beneficiaries import router as beneficiary_router
from routers.moderators import router as moderator_router
from routers.authorization import router as auth_router
from routers.volonters import router as volunteer_router
import uvicorn
from models import Client, Roles, Moderators
from database import get_db
from sqlalchemy.orm import Session
from passlib.context import CryptContext

app = FastAPI()

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(volunteer_router, prefix="/volunteer", tags=["Volunteer"])
app.include_router(beneficiary_router, prefix="/beneficiary", tags=["Beneficiary"])
app.include_router(moderator_router, prefix="/moderator", tags=["Moderator"])


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str):
    return pwd_context.hash(password)

@app.on_event("startup")
def startup_event():
    db = next(get_db())
    try:

        if not db.query(Roles).filter_by(name="beneficiary").first():
            db.add(Roles(name="beneficiary"))
        if not db.query(Roles).filter_by(name="volunteer").first():
            db.add(Roles(name="volunteer"))
        if not db.query(Roles).filter_by(name="moderator").first():
            db.add(Roles(name="moderator"))

        if not db.query(Client).filter_by(name="telegram").first():
            db.add(Client(name="telegram"))
        if not db.query(Client).filter_by(name="frontend").first():
            db.add(Client(name="frontend"))

        existing_moderator = db.query(Moderators).filter_by(phone_number="380968101250").first()
        if not existing_moderator:

            moderator = Moderators(
                phone_number="380968101250",
                role_id=3,
                client_id=2,
                hashed_password=get_password_hash("Admin.22r1")
            )
            db.add(moderator)
            db.commit()
        else:
            print(f"Модератор з номером телефону {existing_moderator.phone_number} вже існує!")

        db.commit()
    except Exception as e:
        print(f"Error during startup: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
