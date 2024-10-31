from fastapi import FastAPI
from routers.beneficiaries import router as beneficiary_router
from routers.moderators import router as moderator_router
from routers.authorization import router as auth_router
from routers.volonters import router as volunteer_router
import uvicorn

app = FastAPI()

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(volunteer_router, prefix="/volunteer", tags=["Volunteer"])
app.include_router(beneficiary_router, prefix="/beneficiary", tags=["Beneficiary"])
app.include_router(moderator_router, prefix="/moderator", tags=["Moderator"])



