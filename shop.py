import json
import os
from pprint import pprint
from uuid import uuid4

from dotenv import load_dotenv
import requests


def get_client_token_info(client_id, client_secret, grant_type):
    url = 'https://api.moltin.com/oauth/access_token'
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': grant_type,
    }

    response = requests.post(url, data=data)
    response.raise_for_status()
    client_token_info = response.json()

    return client_token_info


def upload_product_image(token, image_url):
    url = 'https://api.moltin.com/v2/files'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    files = {
        'file_location': (None, image_url),
    }
    response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()
    product_image_info = response.json()

    return product_image_info['data']['id']


def add_product_image(token, product_id, image_id):
    url = f'https://api.moltin.com/v2/products/{product_id}/relationships/main-image'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    json_data = {
        'data': {
            'type': 'main_image',
            'id': image_id,
        },
    }
    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()


def create_product(token, product):
    url = 'https://api.moltin.com/v2/products'
    headers = {
        'Authorization': f'Bearer {token}',
    }
    json_data = {
        'data': {
            'type': 'product',
            'name': product['name'],
            'slug': str(uuid4())[-12:],
            'sku': 'sk' + str(product['id']),
            'description': product['description'],
            'manage_stock': True,
            'price': [
                {
                    'amount': product['price'] * 100,
                    'currency': 'RUB',
                    'includes_tax': True,
                },
            ],
            'status': 'live',
            'commodity_type': 'physical',
        },
    }

    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()

    stored_product = response.json()
    stored_product_id = stored_product['data']['id']
    product_image_url = product['product_image']['url']
    product_image_id = upload_product_image(token, product_image_url)

    add_product_image(token, stored_product_id, product_image_id)


def add_flows_and_get_id(token, name, description):
    url = 'https://api.moltin.com/v2/flows'
    slug = name.lower()
    headers = {
        'Authorization': f'{token}',
    }
    json_data = {
        'data': {
            'type': 'flow',
            'name': name,
            'slug': slug,
            'description': description,
            'enabled': True,
        },
    }

    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()

    flows = response.json()

    return flows['data']['id']


def create_flows_field(token, flow_id, field_name, field_description, field_type):
    url = 'https://api.moltin.com/v2/fields'
    headers = {
        'Authorization': f'{token}',
    }

    json_data = {
        'data': {
            'type': 'field',
            'name': field_name,
            'slug': field_name.lower(),
            'field_type': field_type,
            'description': field_description,
            'required': True,
            'enabled': True,
            'relationships': {
                'flow': {
                    'data': {
                        'type': 'flow',
                        'id': flow_id,
                    },
                },
            },
        },
    }

    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()


def add_pizzeria_info(token, flow_slug, pizzeria):
    url = f'https://api.moltin.com/v2/flows/{flow_slug}/entries'
    headers = {
        'Authorization': f'{token}',
        'Content-Type': 'application/json',
    }
    json_data = {
        "data":
            {
                "type": "entry",
                "address": pizzeria['address']['full'],
                "alias": pizzeria['alias'],
                "longitude": float(pizzeria['coordinates']['lon']),
                "latitude": float(pizzeria['coordinates']['lat']),
            },
    }

    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()


def add_customer_address(token, flow_slug, current_position, card_id):
    latitude, longitude = current_position
    url = f'https://api.moltin.com/v2/flows/{flow_slug}/entries'
    headers = {
        'Authorization': f'{token}',
        'Content-Type': 'application/json',
    }
    json_data = {
        "data":
            {
                "type": "entry",
                "longitude": longitude,
                "latitude": latitude,
                'card-id': card_id,
            },
    }

    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()


def get_products(token):
    url = 'https://api.moltin.com/v2/products/'
    headers = {
        'Authorization': f'Bearer {token}',
    }

    response = requests.get(
        url,
        headers=headers
    )
    response.raise_for_status()
    shop_data = response.json()

    products = shop_data['data']

    return products


def get_product(token, product_id):
    url = f'https://api.moltin.com/v2/products/{product_id}'
    headers = {
        'Authorization': f'Bearer {token}',
    }

    response = requests.get(
        url,
        headers=headers
    )
    response.raise_for_status()
    product = response.json()

    return product['data']


def get_product_image(token, product_data):
    image_id = product_data['relationships']['main_image']['data']['id']
    url = f'https://api.moltin.com/v2/files/{image_id}'
    headers = {
        'Authorization': f'Bearer {token}',
    }

    response = requests.get(
        url,
        headers=headers
    )
    response.raise_for_status()
    product_files = response.json()
    image_url = product_files['data']['link']['href']

    image = requests.get(image_url)
    image.raise_for_status()

    return image_url


def add_to_cart(token, product_id, cart_id, quantity):
    url = f'https://api.moltin.com/v2/carts/{cart_id}/items'
    headers = {
        'Authorization': f'Bearer {token}',
    }

    json_data = {
        'data': {
            'id': product_id,
            'type': 'cart_item',
            'quantity': quantity,
        },
    }

    response = requests.post(
        url,
        headers=headers,
        json=json_data
    )
    response.raise_for_status()


def get_cart_items(token, cart_id):
    url = f'https://api.moltin.com/v2/carts/{cart_id}/items'
    headers = {
        'Authorization': f'Bearer {token}',
    }

    response = requests.get(
        url,
        headers=headers
    )
    response.raise_for_status()

    return response.json()['data']


def get_cart_total_amount(token, cart_id):
    url = f'https://api.moltin.com/v2/carts/{cart_id}'
    headers = {
        'Authorization': f'Bearer {token}',
    }

    response = requests.get(
        url,
        headers=headers
    )
    response.raise_for_status()

    return response.json()['data']


def delete_cart_items(token, cart_id, item_id):
    url = f'https://api.moltin.com/v2/carts/{cart_id}/items/{item_id}'
    headers = {
        'Authorization': f'Bearer {token}',
    }

    response = requests.delete(url, headers=headers)
    response.raise_for_status()


def create_customer(token, user_name, email):
    url = 'https://api.moltin.com/v2/customers'
    headers = {
        'Authorization': f'Bearer {token}',
    }

    json_data = {
        'data': {
            'type': 'customer',
            'name': user_name,
            'email': email,
        },
    }

    response = requests.post(url, headers=headers, json=json_data)
    response.raise_for_status()


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


def add_model_fields(token, flow_id):
    # create_flows_field(token, flow_id, 'Address', 'Pizzeria address', 'string')
    # create_flows_field(token, flow_id, 'Alias', 'Alias for pizzeria', 'string')
    create_flows_field(token, flow_id, 'Longitude', 'Longitude pizzeria coordinates', 'float')
    create_flows_field(token, flow_id, 'Latitude', 'Latitude pizzeria coordinates', 'float')
    create_flows_field(token, flow_id, 'Card-id', 'ID', 'integer')


def add_pizzerias(token, flow_slug, pizzerias):
    for pizzeria in pizzerias:
        add_pizzeria_info(token, flow_slug, pizzeria)


def get_pizzerias(token, flow_slug):
    url = f'https://api.moltin.com/v2/flows/{flow_slug}/entries'

    headers = {
        'Authorization': f'Bearer {token}',
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    pizzerias = response.json()

    pizzerias_location = {}

    for pizzeria in pizzerias['data']:
        address = pizzeria['address']
        lat = pizzeria['latitude']
        lon = pizzeria['longitude']

        pizzerias_location[address] = (lat, lon)

    return pizzerias_location


if __name__ == '__main__':
    load_dotenv()
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    grant_type = os.getenv('GRANT_TYPE')

    token = get_client_token_info(client_id, client_secret, grant_type)['access_token']

    flow_id = add_flows_and_get_id(token, 'Customer-Addresses', 'Customer coordinates')
    add_model_fields(token, flow_id)
