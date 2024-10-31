from database import Base
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, BigInteger
from sqlalchemy.orm import relationship
from geopy.geocoders import Nominatim


class Locations(Base):
    __tablename__ = 'Locations'

    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    address_name = Column(String)

    applications = relationship('Applications', back_populates='location')
    customers = relationship('Customer', back_populates='location')

    def __init__(self, latitude=None, longitude=None, address_name=None):
        """
            Initializes a new location instance. Sets latitude and longitude based on provided arguments.

            Args:
                latitude (float, optional): Latitude of the location.
                longitude (float, optional): Longitude of the location.
                address_name (str, optional): The address name for the location. If provided,
                                                the latitude and longitude are set using this address.

            Raises:
                 ValueError: If neither address_name nor both latitude and longitude are provided.
        """
        if address_name:
            self.set_location_by_address(address_name)
        elif latitude is not None and longitude is not None:
            self.latitude = latitude
            self.longitude = longitude
        else:
            raise ValueError("Either address_name or both latitude and longitude must be provided.")

    def set_location_by_address(self, address):
        """
            Sets the latitude and longitude of the location based on the provided address using Nominatim geocoding.

            Args:
                address (str): The address to geocode.

            Raises:
                ValueError: If the address cannot be found.
        """
        geolocator = Nominatim(user_agent="geoapiExercises")
        location = geolocator.geocode(address)

        if location:
            self.latitude = location.latitude
            self.longitude = location.longitude
            self.address_name = address
        else:
            raise ValueError("Address could not be found.")


class Customer(Base):
    __tablename__ = 'Customer'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone_num = Column(BigInteger, unique=True)
    tg_id = Column(BigInteger)
    firstname = Column(String)
    lastname = Column(String)
    patronymic = Column(String)
    location_id = Column(Integer, ForeignKey('Locations.id'))

    location = relationship("Locations", primaryjoin="Customer.location_id == Locations.id")
    applications = relationship('Applications', back_populates='customer')
    roles = relationship('Roles', secondary='Ink_CustomerRole')
    categories = relationship('Categories', secondary='Ink_CustomerCategories')


class Categories(Base):
    __tablename__ = 'Categories'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    active_duration = Column(String)
    parent_id = Column(Integer)

    applications = relationship('Applications', back_populates='category')
    customers = relationship('Customer', secondary='Ink_CustomerCategories')


class Applications(Base):
    __tablename__ = 'Applications'

    id = Column(Integer, primary_key=True, index=True)
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

    customer = relationship('Customer', back_populates='applications')
    category = relationship('Categories', back_populates='applications')
    location = relationship('Locations', back_populates='applications')
    media = relationship('Media', secondary='Ink_ApplicationsMedia')


class Roles(Base):
    __tablename__ = 'Roles'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    customers = relationship('Customer', secondary='Ink_CustomerRole')
    user_verifications = relationship('UserVerification', back_populates='role')


class Ink_CustomerRole(Base):
    __tablename__ = 'Ink_CustomerRole'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('Customer.id'))
    role_id = Column(Integer, ForeignKey('Roles.id'))


class Media(Base):
    __tablename__ = 'Media'

    id = Column(Integer, primary_key=True)
    filepath = Column(String)
    creator_id = Column(Integer, ForeignKey('Customer.id'))

    applications = relationship('Applications', secondary='Ink_ApplicationsMedia')


class Ink_ApplicationsMedia(Base):
    __tablename__ = 'Ink_ApplicationsMedia'

    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey('Applications.id'))
    media_id = Column(Integer, ForeignKey('Media.id'))

    application = relationship('Applications')
    media = relationship('Media')


class Ink_CustomerCategories(Base):
    __tablename__ = 'Ink_CustomerCategories'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('Customer.id'))
    category_id = Column(Integer, ForeignKey('Categories.id'))

    customer = relationship('Customer')
    category = relationship('Categories')


class UserVerification(Base):
    __tablename__ = 'UserVerification'

    id = Column(Integer, primary_key=True, index=True)
    phone_num = Column(BigInteger, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey('Roles.id'), nullable=False)
    extra_info = Column(String, nullable=True)

    role = relationship('Roles', back_populates='user_verifications')


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_num = Column(Integer, unique=True, index=True)
    role = Column(String, index=True)
    password = Column(String)