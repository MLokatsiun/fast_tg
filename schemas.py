from pydantic import BaseModel, constr
from datetime import datetime
from typing import Optional

class RegisterRequest(BaseModel):
    phone_num: int
    role: str
    password: str


class LoginRequest(BaseModel):
    phone_num: int
    password: str

class BeneficiaryCreate(BaseModel):
    phone_num: int
    tg_id: int
    firstname: str
    lastname: Optional[str] = None
    patronymic: Optional[str] = None

class ApplicationCreate(BaseModel):
    description: str
    category_id: Optional[int] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ApplicationConfirm(BaseModel):
    application_id: int

class ApplicationDelete(BaseModel):
    application_id: int

from typing import List

class ApplicationCategory(BaseModel):
    id: int
    name: str
    active_duration: int

class ApplicationLocation(BaseModel):
    id: int
    latitude: float
    longitude: float
    address_name: str

class ApplicationResponse(BaseModel):
    id: int
    category: ApplicationCategory
    location: ApplicationLocation
    status: str
    date_at: datetime

class ApplicationsList(BaseModel):
    applications: List[ApplicationResponse]

class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None

class CategoryDelete(BaseModel):
    id: int


class CreateCustomerBase(BaseModel):
    phone_num: int
    tg_id: int
    firstname: constr(min_length=1)
    lastname: constr(min_length=1)
    patronymic: Optional[constr(min_length=1)] = None
    categories: Optional[List[int]]
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class AcceptApplicationBase(BaseModel):
    application_id: int

class CloseApplicationBase(BaseModel):
    application_id: int

class LocationUpdate(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address_name: Optional[str] = None

class EditCustomerBase(BaseModel):
    location: Optional[LocationUpdate] = None
    categories: Optional[List[int]] = None