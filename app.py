import json
import os
import logging
import re
from datetime import datetime
from textwrap import dedent

import requests
import redis
from flask import Flask, request
from dotenv import load_dotenv
from yandex_geocoder import Client, exceptions

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
    get_pizzerias,
    create_customer,
)
from utilits import get_nearest_pizzeria

load_dotenv()

app = Flask(__name__)

DATABASE = None

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def log_error(state, error):
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

    if not data["object"] == "page":
        return "wrong data", 500

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


def get_menu_elemets(slug="basic"):
    products = json.loads(DATABASE.get(slug))
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
        product_id = product["id"]
        price = int(product["price"][0]["amount"] / 100)
        description = product["description"]
        title = f"{name} ({price} р)"
        product_image = json.loads(DATABASE.get("product_image_urls"))[product_id]

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
        product_image = json.loads(DATABASE.get("product_image_urls"))[product_id]

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


def add_product_to_cart(sender_id, message_text, access_token):
    product_info = message_text.split("_")
    product_id = product_info[-1]
    product_name = product_info[-2]
    cart_id = f"facebookid_{sender_id}"
    add_to_cart(access_token, product_id, cart_id)
    send_message(sender_id, f"Пицца {product_name} добавлена в корзину")


def remove_from_cart(sender_id, message_text, access_token):
    product_info = message_text.split("_")
    product_id = product_info[-1]
    product_name = product_info[-2]
    cart_id = f"facebookid_{sender_id}"
    delete_cart_items(access_token, cart_id, product_id)
    send_message(sender_id, f"Пицца {product_name} удалена из корзины")


def get_target_pizzeria(sender_id, address):
    access_token = DATABASE.get("access_token")
    yandex_token = os.getenv("YANDEX_TOKEN")

    try:
        client = Client(yandex_token)
        lon, lat = client.coordinates(address)
        current_position = float(lat), float(lon)
    except exceptions.NothingFound:
        send_message(sender_id, "Не удалось определить координаты")

    flow_slug = "pizzeria"
    pizzerias = get_pizzerias(access_token, flow_slug)
    pizzeria_address, distance = get_nearest_pizzeria(current_position, pizzerias)

    return pizzeria_address, distance


def send_menu(sender_id, access_token, slug="basic", type="menu"):
    if type == "cart":
        elements = get_cart_menu_elements(sender_id, access_token)
    elif type == "menu":
        elements = get_menu_elemets(slug)
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

    elif message_text == "pickup":
        send_message(sender_id, "Введите свой адрес")
        return "PICKUP"

    elif message_text == "delivery":
        send_message(sender_id, "Введите свой адрес")
        return "DELIVERY"

    send_menu(sender_id, access_token, type="cart")
    return "CART"


def handle_pickup(sender_id, message_text):
    pizzeria_address, distance = get_target_pizzeria(sender_id, message_text)
    message = f"""Ближайшая пиццерия находится по адресу {pizzeria_address}.
    До нее {(distance):.2f} км. Приходите за своей пиццей!"""
    send_message(sender_id, message)

    send_message(sender_id, "Для завершения заказа пришлите свой email")

    return "EMAIL"


def handle_delivery(sender_id, message_text):
    pizzeria_address, distance = get_target_pizzeria(sender_id, message_text)
    if distance <= 0.5:
        message = f"""
        Может, заберете пиццу из нашей пиццерии неподалеку?

        Она всего в {(distance):.2f} метрах от Вас!
        Вот её адрес: {pizzeria_address}.

        А можем и бесплатно оставить, нам не сложно))
        """
    elif 0.5 < distance <= 5:
        message = f"""
        Доставим Вашу пиццу за 100 рублей.

        Или можете забрать ее по адресу: {pizzeria_address}
        """
    elif 5 < distance <= 20:
        message = f"""
        Доставим Вашу пиццу за 300 рублей.

        Или можете забрать ее по адресу: {pizzeria_address}
        """
    else:
        message = f"""
        Простите, но так далеко мы пиццу не доставим.

        Ближайшая пиццерия аж в {distance:.2f} километрах от Вас.

        Заезжайте к нам в гости: {pizzeria_address}
        """

    send_message(sender_id, dedent(message))

    send_message(sender_id, "Для завершения заказа пришлите свой email")

    return "EMAIL"


def handle_email(sender_id, message_text):
    access_token = DATABASE.get("access_token")
    username = f"facebookid_{sender_id}"

    if re.search(r"^\w+@\w+\.\w+$", message_text):
        send_message(sender_id, "Спасибо за заказ!")
        create_customer(access_token, username, message_text)
        send_menu(sender_id, access_token)
        return "START"

    send_message(sender_id, "Введите корректный email")
    return "EMAIL"


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
        "PICKUP": handle_pickup,
        "DELIVERY": handle_delivery,
        "EMAIL": handle_email,
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
        log_error(user_state, err)


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
    app.run(debug=False)
