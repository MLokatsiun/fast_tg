from pydantic import BaseModel, constr
from datetime import datetime
from typing import Optional


class LoginRequest(BaseModel):
    user_id: int
    role_id: int
    client: str
    password: str

class LocationCreate(BaseModel):
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CreateCustomerBase(BaseModel):
    phone_num: constr(min_length=12, max_length=12)
    tg_id: constr(min_length=9, max_length=10)
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
    active_duration: Optional[int] = None

class CategoryDelete(BaseModel):
    id: int

class Create_Location(BaseModel):
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
    address: Optional[str] = None

class EditCustomerBase(BaseModel):
    location: Optional[LocationUpdate] = None
    categories: Optional[List[int]] = None

class VerificationUser(BaseModel):
    user_id: int
    is_verified: bool

class VerificationResponse(BaseModel):
    id: int
    is_verified: bool
    message: str

class ModeratorLoginRequest(BaseModel):
    phone_number: str
    password: str
    client: str
    client_password: str
    role_id: int



