import json
import os
from pprint import pprint

from dotenv import load_dotenv
import requests

from shop import (get_client_token_info,
                  create_product,
                  add_flows_and_get_id,
                  create_flows_field
                  )


def get_addresses():
    with open('pizzas_json/addresses.json', 'r') as fin:
        addresses = json.load(fin)

    return addresses


def get_menu():
    with open('pizzas_json/menu.json', 'r') as fin:
        menu = json.load(fin)

    return menu


def add_products(token, menu):
    for product in menu:
        create_product(token, product)


def add_categories(token, flow_id):
    create_flows_field(token, flow_id, 'Address', 'Pizzeria address', 'string')
    create_flows_field(token, flow_id, 'Alias', 'Alias for pizzeria', 'string')
    create_flows_field(token, flow_id, 'Longitude', 'Longitude pizzeria coordinates', 'float')
    create_flows_field(token, flow_id, 'Latitude', 'Latitude pizzeria coordinates', 'float')


if __name__ == '__main__':
    load_dotenv()
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    grant_type = os.getenv('GRANT_TYPE')
    tg_token = os.getenv("TELEGRAM_TOKEN")

    address = get_addresses()
    menu = get_menu()

    token = get_client_token_info(client_id, client_secret, grant_type)['access_token']

    name = 'Pizzeria'
    description = 'Pizzeria with address and coordinates'

    flow_id = add_flows_and_get_id(token, name, description)
    add_categories(token, flow_id)
