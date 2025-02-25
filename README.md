# Volunteer API

## Description
This project is a RESTful API for a volunteer platform built with **FastAPI**. It includes routes for authentication, volunteers, beneficiaries, moderators, and developers. Additionally, the project integrates **Google Maps API** for mapping functionalities.

## Technologies
- **Python 3.x**
- **FastAPI**
- **SQLAlchemy**
- **PostgreSQL**
- **Docker** (optional)
- **CORS Middleware**
- **Google Maps API** (map integration)

## Installation and Setup
### 1. Clone the Repository
```sh
git clone https://github.com/MLokatsiun/fast_tg.git
cd fast_tg
```

### 2. Install Dependencies
It is recommended to create a virtual environment:
```sh
python -m venv venv
source venv/bin/activate  # For Linux/Mac
venv\Scripts\activate  # For Windows
pip install -r requirements.txt
```

### 3. Run the Server
```sh
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
The API will be available at: [http://localhost:8000](http://localhost:8000)

### 4. API Documentation
FastAPI automatically generates documentation:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Redoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Project Structure
```
volunteer-api/
│── .idea/                  # IDE settings
│── alembic/                # Database migrations
│── routers/                # API routes
│── .gitignore              # Git ignored files
│── .gitlab-ci.yml          # CI/CD configuration
│── Dockerfile              # Docker setup
│── alembic.ini             # Alembic configuration
│── business_logical.py     # Business logic
│── create_tables.py        # Database table creation
│── data_initializer.py     # Initial data setup
│── database.py             # Database connection
│── main.py                 # Main FastAPI entry point
│── models.py               # Database models
│── requirements.txt        # Dependency list
│── schemas.py              # Pydantic schemas
│── README.md               # Documentation
```

## Features
### 1. Authentication `/auth`
- Registration
- Login
- Password recovery

### 2. Volunteers `/volunteer`
- Add volunteers
- View the list of volunteers
- Update profile

### 3. Beneficiaries `/beneficiary`
- Submit help requests
- View active requests

### 4. Moderators `/moderator`
- Review and moderate requests
- Manage volunteers

### 5. Developers `/developers`
- API access for integration

### 6. Google Maps Integration
- Display locations on the map
- Address geocoding
- Route optimization for volunteers

## CORS Configuration
The project uses **CORS Middleware**, allowing all domains to interact with the API:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
If necessary, `allow_origins` can be restricted to specific domains.

## Contact
If you have any questions or suggestions for project development, contact us at: `your-email@example.com`.

---

🚀 **Let's make the world a better place together!**

