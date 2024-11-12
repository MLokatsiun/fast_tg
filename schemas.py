
from pydantic import BaseModel, constr
from datetime import datetime
from typing import Optional

# class RegisterRequest(BaseModel):
#     phone_num: int
#     role: int
#     password: str


class LoginRequest(BaseModel):
    user_id: int
    role_id: int
    client: str
    password: str

class LocationCreate(BaseModel):
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class BeneficiaryCreate(BaseModel):
    phone_num: int
    tg_id: int
    firstname: str
    lastname: Optional[str] = None
    patronymic: Optional[str] = None
    role_id: int
    client: str
    password: str

class CreateCustomerBase(BaseModel):
    phone_num: constr(min_length=12, max_length=12)
    tg_id: str
    firstname: str
    lastname: Optional[str] = None
    patronymic: Optional[str] = None
    role_id: int
    client: str
    password: str
    location: Optional[LocationCreate] = None

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

class Create_Location(BaseModel):
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

# class CreateCustomerBase(BaseModel):
#     phone_num: int
#     tg_id: int
#     firstname: constr(min_length=1)
#     lastname: constr(min_length=1)
#     patronymic: Optional[constr(min_length=1)] = None
#     categories: Optional[List[int]]
#     location: Optional[Create_Location]

class AcceptApplicationBase(BaseModel):
    application_id: int

class CloseApplicationBase(BaseModel):
    application_id: int

class LocationUpdate(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None

class EditCustomerBase(BaseModel):
    location: Optional[LocationUpdate] = None
    categories: Optional[List[int]] = None