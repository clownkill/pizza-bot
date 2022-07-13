import json
import os
from pprint import pprint

from dotenv import load_dotenv
import requests

from shop import get_client_token_info, add_product_image, create_product


if __name__ == '__main__':
    load_dotenv()
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    grant_type = os.getenv('GRANT_TYPE')
    tg_token = os.getenv("TELEGRAM_TOKEN")

    with open('pizzas_json/addresses.json', 'r') as fin:
        addresses = json.load(fin)

    with open('pizzas_json/menu.json', 'r') as fin:
        menu = json.load(fin)

    token = get_client_token_info(client_id, client_secret, grant_type)['access_token']
    for product in menu:
        create_product(token, product)
