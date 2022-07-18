import json
import logging
import os
from datetime import datetime
from functools import partial
from textwrap import dedent

import redis
from dotenv import load_dotenv
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from keyboard import (get_main_menu,
                      get_description_menu,
                      get_cart_menu)
from shop import (get_client_token_info,
                  get_products,
                  get_product,
                  get_product_image,
                  add_to_cart,
                  get_cart_items,
                  get_cart_total_amount,
                  delete_cart_items,
                  create_customer
                  )


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

_database = None


def error(state, error):
    logger.warning(f'State {state} caused error {error}')


def get_cart_message(cart_id, access_token):
    cart_items = get_cart_items(access_token, cart_id)
    cart_total_amount = get_cart_total_amount(access_token, cart_id)
    total_amount = cart_total_amount['meta']['display_price']['with_tax']['formatted']

    message = ''

    for item in cart_items:
        item_name = item['name']
        item_description = item['description']
        item_quantity = item['quantity']
        item_price = item['meta']['display_price']['with_tax']['unit']['formatted']
        total_price = item['meta']['display_price']['with_tax']['value']['formatted']
        message += f'''
                {item_name}
                {item_description}
                {item_price} per kg
                {item_quantity}kg in cart for {total_price}

                '''
    message += total_amount

    return message


def start(context, update, products):
    update.message.reply_text(
        'Please choose:',
        reply_markup=get_main_menu(products)
    )

    return 'HANDLE_MENU'


def handle_menu(context, update, access_token):
    query = update.callback_query
    product_id = query.data
    user = f"user_tg_{query.message.chat_id}"
    _database.set(
        user,
        json.dumps({'product_id': product_id})
    )
    context.user_data['product_id'] = product_id
    product_data = get_product(access_token, product_id)
    product_name = product_data['name']
    # product_weight = product_data['weight']['kg']
    product_price = product_data['meta']['display_price']['with_tax']['formatted']
    product_description = product_data['description']

    message = f'''
    {product_name}
    {product_price}
    {product_description}
    '''
    image_url = get_product_image(access_token, product_data)

    context.bot.send_photo(
        chat_id=query.message.chat_id,
        photo=image_url,
        caption=dedent(message),
        reply_markup=get_description_menu()
    )

    context.bot.delete_message(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id
    )

    return 'HANDLE_DESCRIPTION'


def handle_description(context, update, access_token, products):
    query = update.callback_query
    user = f"user_tg_{query.message.chat_id}"
    product_id = json.loads(_database.get(user))['product_id']

    if query.data == 'back':
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text='Please choose:',
            reply_markup=get_main_menu(products)
        )
        context.bot.delete_message(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )
        return 'HANDLE_MENU'

    elif query.data == 'cart':
        cart_id = query.message['chat']['id']
        cart_items = get_cart_items(access_token, cart_id)
        message = get_cart_message(cart_id, access_token)

        context.bot.send_message(
            chat_id=query.message.chat_id,
            text=dedent(message),
            reply_markup=get_cart_menu(cart_items)
        )
        context.bot.delete_message(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )

        return 'HANDLE_CART'

    elif query.data.isdigit():
        add_to_cart(
            token=access_token,
            product_id=product_id,
            cart_id=query.message['chat']['id'],
            quantity=int(query.data)
        )
        product_data = get_product(access_token, product_id)
        product_name = product_data['name']
        context.bot.answer_callback_query(
            callback_query_id=query.id,
            text=f'Вы добавили в корзину {query.data} кг {product_name}',
            show_alert=True
        )
        return 'HANDLE_DESCRIPTION'


def handle_cart(context, update, access_token, products):
    query = update.callback_query
    cart_id = query.message['chat']['id']
    if query.data.startswith('del'):
        item_id = query.data.split(' ')[-1]
        delete_cart_items(access_token, cart_id, item_id)
        cart_items = get_cart_items(access_token, cart_id)
        message = get_cart_message(cart_id, access_token)
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text=dedent(message),
            reply_markup=get_cart_menu(cart_items)
        )
        context.bot.delete_message(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )

        return 'HANDLE_CART'

    elif query.data == 'pay':
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text='Для оформления заказа введите ваш email'
        )
        context.bot.delete_message(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )

        return 'WAITING_EMAIL'

    elif query.data == 'menu':
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text='Please choose:',
            reply_markup=get_main_menu(products)
        )
        context.bot.delete_message(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )
        return 'HANDLE_MENU'


def handle_waiting_email(context, update, access_token):
    print(update.message)
    username = update.message['chat']['username']
    email = update.message.text
    message = f'''
    Вы ввели email: {email}

    В ближайшее время менеджер свяжется с вами для оформления заказа.
    '''
    update.message.reply_text(
        text=dedent(message)
    )

    create_customer(access_token, username, email)

    return 'START'


def handle_users_reply(update, context, client_id, client_secret, grant_type):
    db = get_database_connection()
    if context.user_data.get('token_timestamp'):
        diff = datetime.now() - context.user_data['token_timestamp']
        if diff.total_seconds() >= get_client_token_info(client_id, client_secret, grant_type)['expires_in']:
            context.user_data['token_timestamp'] = datetime.now()
            context.user_data['access_token'] = get_client_token_info(client_id,
                                                                      client_secret,
                                                                      grant_type)['access_token']
    else:
        context.user_data['token_timestamp'] = datetime.now()
        context.user_data['access_token'] = get_client_token_info(client_id,
                                                                  client_secret,
                                                                  grant_type)['access_token']
    access_token = context.user_data['access_token']
    products = get_products(access_token)
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = db.get(chat_id)

    states_functions = {
        'START': partial(start, products=products),
        'HANDLE_MENU': partial(handle_menu, access_token=access_token),
        'HANDLE_DESCRIPTION': partial(handle_description, access_token=access_token, products=products),
        'HANDLE_CART': partial(handle_cart, access_token=access_token, products=products),
        'WAITING_EMAIL': partial(handle_waiting_email, access_token=access_token),
    }
    state_handler = states_functions[user_state]
    try:
        next_state = state_handler(context, update)
        db.set(chat_id, next_state)
    except Exception as err:
        error(user_state, err)


def get_database_connection():
    global _database
    if _database is None:
        database_password = os.getenv("DATABASE_PASSWORD")
        database_host = os.getenv("DATABASE_HOST")
        database_port = os.getenv("DATABASE_PORT")
        _database = redis.Redis(
            host=database_host,
            port=database_port,
            password=database_password,
            decode_responses=True,
        )
    return _database


if __name__ == '__main__':
    load_dotenv()
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    grant_type = os.getenv('GRANT_TYPE')
    tg_token = os.getenv("TELEGRAM_TOKEN")

    updater = Updater(tg_token)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CallbackQueryHandler(partial(
        handle_users_reply,
        client_id=client_id,
        client_secret=client_secret,
        grant_type=grant_type,
    )))
    dispatcher.add_handler(MessageHandler(Filters.text, partial(
        handle_users_reply,
        client_id=client_id,
        client_secret=client_secret,
        grant_type=grant_type
    )))
    dispatcher.add_handler(CommandHandler('start', partial(
        handle_users_reply,
        client_id=client_id,
        client_secret=client_secret,
        grant_type=grant_type
    )))

    dispatcher.add_error_handler(error)

    updater.start_polling()
