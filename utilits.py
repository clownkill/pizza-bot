import requests
from geopy import distance


def fetch_coordinates(apikey, address):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']

    if not found_places:
        return None

    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat


def get_nearest_pizzeria(customer_position, pizzerias):
    distance_to_pizzerias = {}
    for pizzeria, pizzeria_position in pizzerias.items():
        distance_to_pizzeria = distance.distance(
            customer_position,
            pizzeria_position
        ).km
        distance_to_pizzerias[pizzeria] = round(distance_to_pizzeria, 3)
    nearest_pizzeria = min(distance_to_pizzerias, key=distance_to_pizzerias.get)
    return nearest_pizzeria, distance_to_pizzerias[nearest_pizzeria]
