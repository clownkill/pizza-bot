import os
from pprint import pprint
import sys
import json
from datetime import datetime

import requests
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
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
grant_type = os.getenv("GRANT_TYPE")

app = Flask(__name__)


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
    log(data)
    access_token = get_client_token_info(client_id, client_secret, grant_type)[
        "access_token"
    ]

    if data["object"] == "page":

        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:

                if messaging_event.get("message"):

                    sender_id = messaging_event["sender"]["id"]
                    recipient_id = messaging_event["recipient"]["id"]
                    message_text = messaging_event["message"]["text"]
                    
                    send_menu(sender_id, access_token)

                if messaging_event.get("delivery"):
                    pass

                if messaging_event.get("optin"):
                    pass

                if messaging_event.get("postback"):
                    pass

    return "ok", 200


def send_message(recipient_id, message_text):

    log(
        "sending message to {recipient}: {text}".format(
            recipient=recipient_id, text=message_text
        )
    )

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
    if response.status_code != 200:
        log(response.status_code)
        log(response.text)


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
            "image_url": "https://primepizza.ru/uploads/position/large_0c07c6fd5c4dcadddaf4a2f1a2c218760b20c396.jpg",
            "subtitle": "Остальные пиццы можно посмотреть в одной из категорий",
            "buttons": category_buttons,
        },
    )

    return elements


def send_menu(recipient_id, access_token):
    headers = {
        "Content-Type": "application/json",
    }

    params = {
        "access_token": os.getenv("PAGE_ACCESS_TOKEN"),
    }

    json_data = {
        "recipient": {
            "id": recipient_id,
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

    if response.status_code != 200:
        log(response.status_code)
        log(response.text)


def log(msg, *args, **kwargs):
    try:
        if type(msg) is dict:
            msg = json.dumps(msg)
        else:
            msg = msg
        print("{}: {}".format(datetime.now(), msg))
    except UnicodeEncodeError:
        pass
    sys.stdout.flush()


if __name__ == "__main__":
    app.run(debug=True)
