from database import Base
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, BigInteger
from sqlalchemy import Column, Integer, Float, String
from sqlalchemy.orm import relationship


class Locations(Base):
    __tablename__ = 'Locations'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    latitude = Column(Float)
    longitude = Column(Float)
    address_name = Column(String)

    applications = relationship('Applications', back_populates='location')
    customers = relationship('Customer', back_populates='location')

    def __init__(self, latitude=None, longitude=None, address_name=None):
        """
        Ініціалізуємо об'єкт локації. Оновлення координат або адреси відбувається асинхронно.
        """
        self.latitude = latitude
        self.longitude = longitude
        self.address_name = address_name

    async def update_location(self, address=None, latitude=None, longitude=None):
        """
        Асинхронне оновлення даних локації.
        """
        from business_logical import get_coordinates
        if address:
            coordinates = await get_coordinates(address=address)
            self.latitude = coordinates["latitude"]
            self.longitude = coordinates["longitude"]
            self.address_name = address
        elif latitude is not None and longitude is not None:
            address_data = await get_coordinates(lat=latitude, lng=longitude)
            self.latitude = latitude
            self.longitude = longitude
            self.address_name = address_data["address"]
        else:
            raise ValueError("Either address or both latitude and longitude must be provided.")



class Customer(Base):
    __tablename__ = 'Customer'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone_num = Column(String)
    tg_id = Column(String)
    firstname = Column(String)
    lastname = Column(String)
    patronymic = Column(String)
    role_id = Column(Integer, ForeignKey("Roles.id"))
    location_id = Column(Integer, ForeignKey('Locations.id'))
    client_id = Column(Integer, ForeignKey('Clients.id'))
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    location = relationship("Locations", primaryjoin="Customer.location_id == Locations.id")
    applications = relationship('Applications', back_populates='customer')
    roles = relationship('Roles', secondary='Ink_CustomerRole', back_populates='customers')
    client = relationship('Client', back_populates='customers')
    # moderator = relationship('Moderators', back_populates='customers')

class Categories(Base):
    __tablename__ = 'Categories'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String)
    # active_duration = Column(String)
    parent_id = Column(Integer)
    is_active = Column(Boolean, default=True)

    applications = relationship('Applications', back_populates='category')
    customers = relationship('Customer', secondary='Ink_CustomerCategories')


class Applications(Base):
    __tablename__ = 'Applications'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    creator_id = Column(Integer, ForeignKey('Customer.id'))
    category_id = Column(Integer, ForeignKey('Categories.id'))
    location_id = Column(Integer, ForeignKey('Locations.id'))
    description = Column(String)
    executor_id = Column(Integer)
    is_in_progress = Column(Boolean)
    is_done = Column(Boolean)
    is_finished = Column(Boolean)
    date_at = Column(String)
    date_done = Column(String)
    active_to = Column(String)
    is_active = Column(Boolean, default=True)

    customer = relationship('Customer', back_populates='applications')
    category = relationship('Categories', back_populates='applications')
    location = relationship('Locations', back_populates='applications')
    media = relationship('Media', secondary='Ink_ApplicationsMedia')

class Roles(Base):
    __tablename__ = 'Roles'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, unique=True, index=True)

    customers = relationship('Customer', secondary='Ink_CustomerRole', back_populates='roles')
    moderators = relationship('Moderators', back_populates='role')

class Ink_CustomerRole(Base):
    __tablename__ = 'Ink_CustomerRole'

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey('Customer.id'))
    role_id = Column(Integer, ForeignKey('Roles.id'))


class Media(Base):
    __tablename__ = 'Media'

    id = Column(Integer, primary_key=True, autoincrement=True)
    filepath = Column(String)
    creator_id = Column(Integer, ForeignKey('Customer.id'))

    applications = relationship('Applications', secondary='Ink_ApplicationsMedia')


class Ink_ApplicationsMedia(Base):
    __tablename__ = 'Ink_ApplicationsMedia'

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey('Applications.id'))
    media_id = Column(Integer, ForeignKey('Media.id'))

    application = relationship('Applications')
    media = relationship('Media')


class Ink_CustomerCategories(Base):
    __tablename__ = 'Ink_CustomerCategories'

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey('Customer.id'))
    category_id = Column(Integer, ForeignKey('Categories.id'))

    customer = relationship('Customer')
    category = relationship('Categories')


class Client(Base):
    __tablename__ = 'Clients'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

    customers = relationship('Customer', back_populates='client')
    moderators = relationship('Moderators', back_populates='client')

class Moderators(Base):
    __tablename__ = 'Moderators'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone_number = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    client_id = Column(Integer, ForeignKey('Clients.id'), nullable=False)
    role_id = Column(Integer, ForeignKey('Roles.id'))

    client = relationship('Client', back_populates='moderators')

    role = relationship('Roles', back_populates='moderators')


