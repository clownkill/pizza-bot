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
    headers = {
        'Authorization': f'{token}',
    }

    json_data = {
        'data': {
            'type': 'flow',
            'name': name,
            'slug': str(uuid4())[-12:],
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
            'slug': str(uuid4())[-12:],
            'field_type': field_type,
            'description': field_description,
            'required': True,
            'default': 0,
            'enabled': True,
            'order': 1,
            'omit_null': False,
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
