import requests
from fastapi import HTTPException


def get_location_info(query):
    """
    Виконує пряме або зворотне геокодування за допомогою Nominatim API.

    Args:
        query (str or tuple): Якщо передано адресу (str), виконується пряме геокодування.
                              Якщо передано координати (tuple: широта, довгота), виконується зворотне геокодування.

    Returns:
        dict: Словник з координатами (latitude, longitude) або адресою.

    Raises:
        HTTPException: Якщо запит до Nominatim API не вдається або дані не знайдено.
    """
    base_url = "https://nominatim.openstreetmap.org/"
    headers = {

        "User-Agent": "api/1.0 (misaloka29@gmail.com)"
    }

    if isinstance(query, str):
        url = base_url + "search"
        params = {
            "q": query,
            "format": "json",
            "limit": 1
        }
        response = requests.get(url, params=params, headers=headers)

    elif isinstance(query, tuple) and len(query) == 2:
        url = base_url + "reverse"
        params = {
            "lat": query[0],
            "lon": query[1],
            "format": "json"
        }
        response = requests.get(url, params=params, headers=headers)

    else:
        raise ValueError(
            "Неправильний формат введених даних. Передайте адресу (str) або координати (tuple: широта, довгота).")

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Помилка під час з'єднання з Nominatim API")

    data = response.json()

    if isinstance(query, str):
        if not data:
            raise HTTPException(status_code=400, detail="Адресу не знайдено")
        location = data[0]
        return {
            "latitude": location["lat"],
            "longitude": location["lon"]
        }

    elif isinstance(query, tuple):
        if "error" in data or not data.get("display_name"):
            raise HTTPException(status_code=400, detail="Адресу не знайдено за вказаними координатами")
        return {
            "address": data["display_name"]
        }


print(get_location_info("Київ, Україна"))
print(get_location_info((50.44894813746246, 30.512981502780786)))
