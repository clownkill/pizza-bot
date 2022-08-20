import json
import os
import logging
from datetime import datetime

import requests
import redis
from flask import Flask, request
from dotenv import load_dotenv

from shop import (
    add_to_cart,
    delete_cart_items,
    get_cart_items,
    get_cart_total_amount,
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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def error(state, error):
    logger.warning(f"State {state} caused error {error}")


@app.route("/", methods=["GET"])
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get(
        "hub.challenge"
    ):
        if not (request.args.get("hub.verify_token") == os.getenv("VERIFY_TOKEN")):
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200


@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["message"]["text"]
                elif messaging_event.get("postback"):
                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["postback"]["payload"]
                handle_users_reply(sender_id, message_text)

    return "ok", 200


def set_menu_cache(access_token):
    categories = get_categories(access_token)

    DATABASE.set("categories", json.dumps(categories))

    for category in categories:
        category_products = json.dumps(get_products_by_category(access_token, category))
        DATABASE.set(category, category_products)

    product_image_urls = {}
    products = get_products(access_token)
    for product in products:
        id = product["id"]
        product_data = get_product(access_token, id)
        product_image = get_product_image(access_token, product_data)
        product_image_urls[id] = product_image

    DATABASE.set("product_image_urls", json.dumps(product_image_urls))


def get_category_menu_cache(category):
    return json.loads(DATABASE.get(category))


def get_product_image_cache(product_id):
    return json.loads(DATABASE.get("product_image_urls"))[product_id]


def send_message(recipient_id, message_text):
    params = {"access_token": os.getenv("PAGE_ACCESS_TOKEN")}
    headers = {"Content-Type": "application/json"}
    data = json.dumps(
        {"recipient": {"id": recipient_id}, "message": {"text": message_text}}
    )
    response = requests.post(
        "https://graph.facebook.com/v2.6/me/messages",
        params=params,
        headers=headers,
        data=data,
    )
    response.raise_for_status()


def get_menu_elemets(access_token, slug="basic"):
    products = get_category_menu_cache(slug)
    categories = json.loads(DATABASE.get("categories"))

    elements = [
        {
            "title": "Меню",
            "image_url": "https://d1csarkz8obe9u.cloudfront.net/posterpreviews/pizza-logo-template-design-183c12cfbe00ef109c299d864f364e58_screen.jpg?ts=1635756978",
            "subtitle": "Здесь вы можете выбрать один из вариантов",
            "buttons": [
                {
                    "type": "postback",
                    "title": "Корзина",
                    "payload": "cart",
                },
                {
                    "type": "postback",
                    "title": "Акции",
                    "payload": "action",
                },
                {
                    "type": "postback",
                    "title": "Сделать заказ",
                    "payload": "order",
                },
            ],
        },
    ]

    for product in products:
        name = product["name"]
        price = int(product["price"][0]["amount"] / 100)
        description = product["description"]
        title = f"{name} ({price} р)"
        product_image = get_product_image_cache(product["id"])

        elements.append(
            {
                "title": title,
                "image_url": product_image,
                "subtitle": description,
                "buttons": [
                    {
                        "type": "postback",
                        "title": "Добавить в корзину",
                        "payload": f"ADD_{name}_{product['id']}",
                    },
                ],
            },
        )

    subtitle_text = "Остальные пиццы можно посмотреть в одной из категорий"
    iamge_url = "https://primepizza.ru/uploads/position/large_0c07c6fd5c4dcadddaf4a2f1a2c218760b20c396.jpg"
    category_buttons = []
    for category in categories:
        if category != slug:
            title = categories[category]["name"]
            category_buttons.append(
                {
                    "type": "postback",
                    "title": title,
                    "payload": f"CATEGORY_{category}",
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


def get_cart_menu_elements(sender_id, access_token):
    cart_id = f"facebookid_{sender_id}"
    products = get_cart_items(access_token, cart_id)

    cart_total_amount = get_cart_total_amount(access_token, cart_id)["meta"][
        "display_price"
    ]["with_tax"]["amount"]

    total_amount = int(int(cart_total_amount) / 100)

    elements = [
        {
            "title": f"Ваш заказ на сумму {total_amount} руб.",
            "image_url": "https://postium.ru/wp-content/uploads/2018/08/idealnaya-korzina-internet-magazina-1068x713.jpg",
            "buttons": [
                {
                    "type": "postback",
                    "title": "Самовывоз",
                    "payload": "pickup",
                },
                {
                    "type": "postback",
                    "title": "Доставка",
                    "payload": "delivery",
                },
                {
                    "type": "postback",
                    "title": "Меню",
                    "payload": "menu",
                },
            ],
        },
    ]
    for product in products:
        name = product["name"]
        price = int(product["unit_price"]["amount"] / 100)
        description = product["description"]
        title = f"{name} ({price} р)"
        product_id = product["product_id"]
        cart_item_id = product["id"]
        product_image = get_product_image_cache(product_id)

        elements.append(
            {
                "title": title,
                "image_url": product_image,
                "subtitle": description,
                "buttons": [
                    {
                        "type": "postback",
                        "title": "Добавить еще одну",
                        "payload": f"ADD_{name}_{product_id}",
                    },
                    {
                        "type": "postback",
                        "title": "Удалить",
                        "payload": f"REMOVE_{name}_{cart_item_id}",
                    },
                ],
            },
        )
    return elements


def add_product_to_cart(sender_id, message, access_token):
    product_info = message.split("_")
    product_id = product_info[-1]
    product_name = product_info[-2]
    cart_id = f"facebookid_{sender_id}"
    add_to_cart(access_token, product_id, cart_id)
    send_message(sender_id, f"Пицца {product_name} добавлена в корзину")


def remove_from_cart(sender_id, message, access_token):
    product_info = message.split("_")
    product_id = product_info[-1]
    product_name = product_info[-2]
    cart_id = f"facebookid_{sender_id}"
    delete_cart_items(access_token, cart_id, product_id)
    send_message(sender_id, f"Пицца {product_name} удалена из корзины")


def send_menu(sender_id, access_token, slug="basic", type="menu"):
    if type == "cart":
        elements = get_cart_menu_elements(sender_id, access_token)
    elif type == "menu":
        elements = get_menu_elemets(access_token, slug)
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
                    "elements": elements,
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


def handle_start(sender_id, message_text):
    access_token = DATABASE.get("access_token")

    if "CATEGORY" in message_text:
        send_menu(sender_id, access_token, message_text.split("_")[-1])

        return "MENU"

    send_menu(sender_id, access_token)
    return "MENU"


def handle_menu(sender_id, message_text):
    access_token = DATABASE.get("access_token")

    if message_text == "cart":
        send_menu(sender_id, access_token, type=message_text)

        return "CART"

    elif "CATEGORY" in message_text:
        send_menu(sender_id, access_token, message_text.split("_")[-1])

        return "MENU"

    elif "ADD" in message_text:
        add_product_to_cart(sender_id, message_text, access_token)
        send_menu(sender_id, access_token)

        return "MENU"
    else:
        send_menu(sender_id, access_token)
        return "START"


def handle_cart(sender_id, message_text):
    access_token = DATABASE.get("access_token")

    if message_text == "menu":
        send_menu(sender_id, access_token, type=message_text)

        return "MENU"

    elif "ADD" in message_text:
        add_product_to_cart(sender_id, message_text, access_token)
        send_menu(sender_id, access_token, type="cart")
        return "CART"

    elif "REMOVE" in message_text:
        remove_from_cart(sender_id, message_text, access_token)
        send_menu(sender_id, access_token, type="cart")
        return "CART"

    send_menu(sender_id, access_token, type="cart")
    return "CART"


def handle_users_reply(sender_id, message_text):
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    grant_type = os.getenv("GRANT_TYPE")

    db = get_database_connection()

    if db.get("token_timestamp"):
        diff = datetime.timestamp(datetime.now()) - float(db.get("token_timestamp"))
        client_token_info = get_client_token_info(client_id, client_secret, grant_type)
        expires_time = client_token_info["expires_in"]
        if diff >= expires_time:
            access_token = client_token_info["access_token"]
            db.set("token_timestamp", datetime.timestamp(datetime.now()))
            db.set("access_token", access_token)
            set_menu_cache(access_token)
    else:
        db.set("token_timestamp", datetime.timestamp(datetime.now()))
        client_token_info = get_client_token_info(client_id, client_secret, grant_type)
        db.set("access_token", client_token_info["access_token"])
        set_menu_cache(access_token)

    states_functions = {
        "START": handle_start,
        "MENU": handle_menu,
        "CART": handle_cart,
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
        DATABASE = redis.Redis(
            host=os.getenv("DATABASE_HOST"),
            port=os.getenv("DATABASE_PORT"),
            password=os.getenv("DATABASE_PASSWORD"),
            decode_responses=True,
        )
    return DATABASE


if __name__ == "__main__":
    app.run(debug=True)
