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
    access_token = get_client_token_info(client_id,
                                        client_secret,
                                        grant_type)['access_token']
    products = get_products(access_token)[:5]

    if data["object"] == "page":

        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:

                if messaging_event.get("message"):

                    sender_id = messaging_event["sender"]["id"]
                    recipient_id = messaging_event["recipient"]["id"]
                    message_text = messaging_event["message"]["text"]

                    # send_message(sender_id, message_text)
                    send_menu(sender_id, products, access_token)

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


def send_menu(recipient_id, products, access_token):
    headers = {
        "Content-Type": "application/json",
    }

    params = {
        "access_token": os.getenv("PAGE_ACCESS_TOKEN"),
    }

    elements = []

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
                "default_action": {
                    "type": "web_url",
                    "url": "https://catalog.onliner.by/mobile/honor/honorx86128bo",
                    "messenger_extensions": False,
                    "webview_height_ratio": "tall",
                },
                "buttons": [
                    {
                        "type": "web_url",
                        "url": "https://catalog.onliner.by",
                        "title": "Здесь будет кнопка",
                    },
                ],
            },
        )

    json_data = {
        "recipient": {
            "id": recipient_id,
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

    if response.status_code != 200:
        log(response.status_code)
        log(response.text)


def send_keyboard(recipient_id):
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
                    "template_type": "button",
                    "text": "Try the postback button!",
                    "buttons": [
                        {
                            "type": "postback",
                            "title": "Postback Button",
                            "payload": "DEVELOPER_DEFINED_PAYLOAD",
                        },
                    ],
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
