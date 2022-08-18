import os
import logging
from functools import partial

import requests
import redis
from flask import Flask, request
from dotenv import load_dotenv

from shop import (
    get_client_token_info,
    get_products,
    get_categories,
    get_products_by_category,
    get_product,
    get_product_image,
)

load_dotenv()

app = Flask(__name__)

DATABASE = None

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


def error(state, error):
    logger.warning(f"State {state} caused error {error}")


@app.route("/", methods=["GET"])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get(
        "hub.challenge"
    ):
        if not (
            request.args.get("hub.verify_token") == os.getenv("VERIFY_TOKEN")
        ):
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200


@app.route("/", methods=["POST"])
def webhook():
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    grant_type = os.getenv("GRANT_TYPE")
    access_token = get_client_token_info(client_id, client_secret, grant_type)[
        "access_token"
    ]

    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["message"]["text"]

                    handle_users_reply(sender_id, message_text, access_token)

    return "ok", 200


def get_menu_elemets(access_token):
    products = get_products_by_category(access_token)
    categories = get_categories(access_token)

    elements = [
        {
            "title": "Меню",
            "image_url": "https://d1csarkz8obe9u.cloudfront.net/posterpreviews/pizza-logo-template-design-183c12cfbe00ef109c299d864f364e58_screen.jpg?ts=1635756978",
            "subtitle": "Здесь вы можете выбрать один из вариантов",
            "buttons": [
                {
                    "type": "postback",
                    "title": "Корзина",
                    "payload": "CART",
                },
                {
                    "type": "postback",
                    "title": "Акции",
                    "payload": "ACTION",
                },
                {
                    "type": "postback",
                    "title": "Сделать заказ",
                    "payload": "ORDER",
                },
            ],
        },
    ]

    for product in products:
        name = product["name"]
        price = int(product["price"][0]["amount"] / 100)
        description = product["description"]
        title = f"{name} ({price} р)"
        product_data = get_product(access_token, product["id"])
        product_image = get_product_image(access_token, product_data)

        elements.append(
            {
                "title": title,
                "image_url": product_image,
                "subtitle": description,
                "buttons": [
                    {
                        "type": "postback",
                        "title": "Добавить в корзину",
                        "payload": f"ADD_{product['id']}",
                    },
                ],
            },
        )

    subtitle_text = "Остальные пиццы можно посмотреть в одной из категорий"
    iamge_url = "https://primepizza.ru/uploads/position/large_0c07c6fd5c4dcadddaf4a2f1a2c218760b20c396.jpg"
    category_buttons = []
    for category in categories:
        if category != "basic":
            title = categories[category]["name"]
            category_id = categories[category]["id"]
            category_buttons.append(
                {
                    "type": "postback",
                    "title": title,
                    "payload": f"CATEGORY_{category_id}",
                }
            )

    elements.append(
        {
            "title": "Не нашли нужную пиццу?",
            "image_url": iamge_url,
            "subtitle": subtitle_text,
            "buttons": category_buttons,
        },
    )

    return elements


def send_menu(sender_id, access_token):
    headers = {
        "Content-Type": "application/json",
    }

    params = {
        "access_token": os.getenv("PAGE_ACCESS_TOKEN"),
    }

    json_data = {
        "recipient": {
            "id": sender_id,
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": get_menu_elemets(access_token),
                },
            },
        },
    }

    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params,
        headers=headers,
        json=json_data,
    )
    response.raise_for_status()


def handle_start(sender_id, message_text, access_token):
    send_menu(sender_id, access_token)

    return "MENU"


def handle_users_reply(sender_id, message_text, access_token):
    db = get_database_connection()

    states_functions = {
        "START": partial(handle_start, access_token=access_token),
    }

    recorded_state = db.get(f"facebookid_{sender_id}")
    if not recorded_state or recorded_state not in states_functions.keys():
        user_state = "START"
    else:
        user_state = recorded_state
    if message_text == "/start":
        user_state = "START"
    state_handler = states_functions[user_state]
    try:
        next_state = state_handler(sender_id, message_text)
        db.set(f"facebookid_{sender_id}", next_state)
    except Exception as err:
        error(user_state, err)


def get_database_connection():
    global DATABASE
    if DATABASE is None:
        database_password = os.getenv("DATABASE_PASSWORD")
        database_host = os.getenv("DATABASE_HOST")
        database_port = os.getenv("DATABASE_PORT")
        DATABASE = redis.Redis(
            host=database_host,
            port=database_port,
            password=database_password,
            decode_responses=True,
        )
    return DATABASE


if __name__ == "__main__":
    app.run(debug=True)
