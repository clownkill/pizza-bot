import json
import logging
import os
from datetime import datetime
from functools import partial
from pprint import pprint
from textwrap import dedent

import redis
from dotenv import load_dotenv
from telegram import LabeledPrice
from telegram.ext import (Filters,
                          Updater,
                          CallbackQueryHandler,
                          CommandHandler,
                          MessageHandler,
                          PreCheckoutQueryHandler,
                          )
from yandex_geocoder import Client, exceptions

from keyboard import (get_main_menu,
                      get_description_menu,
                      get_cart_menu,
                      get_delivery_menu,
                      )
from shop import (get_client_token_info,
                  get_products,
                  get_product,
                  get_product_image,
                  add_to_cart,
                  get_cart_items,
                  get_cart_total_amount,
                  delete_cart_items,
                  create_customer,
                  get_pizzerias,
                  add_customer_address
                  )
from utilits import get_nearest_pizzeria



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
                
                {item_price} руб. за одну пиццу
                
                В корзине пиццы: {item_quantity} шт. 
                на {total_price} руб.

                '''
    message += total_amount

    return message


def start(context, update, products):
    update.message.reply_text(
        'Выберите пиццу:',
        reply_markup=get_main_menu(products)
    )

    return 'HANDLE_MENU'


def handle_menu(context, update, access_token, products):
    query = update.callback_query

    if 'pag' in query.data:
        page = query.data.split(', ')[1]
        context.bot.edit_message_text(
            text='Выберите пиццу',
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            reply_markup=get_main_menu(products, int(page))
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

    else:
        product_id = query.data
        user = f"user_tg_{query.message.chat_id}"
        _database.set(
            user,
            json.dumps({'product_id': product_id})
        )
        context.user_data['product_id'] = product_id
        product_data = get_product(access_token, product_id)
        product_name = product_data['name']
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
            text=f'Вы добавили в корзину пиццу: {product_name}',
            show_alert=True
        )
        return 'HANDLE_DESCRIPTION'


def handle_cart(context, update, access_token, products):
    query = update.callback_query
    pay_with_price = query.data.split(', ')
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

    elif pay_with_price[0] == 'pay':
        price = int(pay_with_price[1])
        start_without_shipping(context, update, price)

        return 'HANDLE_WAITING'

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


def handle_waiting(context, update, yandex_token, access_token):
    if update.message.text:
        try:
            client = Client(yandex_token)
            lon, lat = client.coordinates(update.message.text)
            current_position = float(lat), float(lon)
        except exceptions.NothingFound:
            context.bot.send_message(
                chat_id=update.message.chat_id,
                text='Не могу распознать этот адрес'
            )

            return 'HANDLE_WAITING'
    else:
        current_position = (
            float(update.message.location.latitude),
            float(update.message.location.longitude)
        )

    flow_slug = 'pizzeria'
    pizzerias = get_pizzerias(access_token, flow_slug)
    pizzeria_address, distance = get_nearest_pizzeria(current_position, pizzerias)
    supplier = update.message.chat_id

    if distance <= 0.5:
        message_text = f'''
        Может, заберете пиццу из нашей пиццерии неподалеку?
        
        Она всего в {(distance * 100):.2f} метрах от Вас!
        Вот её адрес: {pizzeria_address}.
        
        А можем и бесплатно оставить, нам не сложно))
        '''
        reply_markup = get_delivery_menu(supplier, current_position)
    elif 0.5 < distance <= 5:
        message_text = f'''
        Доставим Вашу пиццу за 100 рублей.
        
        Или можете забрать ее по адресу: {pizzeria_address}
        '''
        reply_markup = get_delivery_menu(supplier, current_position)
    elif 5 < distance <= 20:
        message_text = f'''
        Доставим Вашу пиццу за 300 рублей.
        
        Или можете забрать ее по адресу: {pizzeria_address}
        '''
        reply_markup = get_delivery_menu(supplier, current_position)
    else:
        message_text = f'''
        Простите, но так далеко мы пиццу не доставим.
        
        Ближайшая пиццерия аж в {distance:.2f} километрах от Вас.
        
        Заезжайте к нам в гости: {pizzeria_address}
        '''
        reply_markup = None

    context.bot.send_message(
        chat_id=update.message.chat_id,
        text=dedent(message_text),
        reply_markup=reply_markup
    )

    return 'HANDLE_DELIVERY'


def pizza_not_delivered(context):
    message_text = '''
    Приятного аппетита! *место для рекламы*
    
    Курьер с пиццей очень спешит к Вам.
    Но увы не успевает доставить ее вовремя.
    В связи с этим можете забрать нашу пиццу совершенно бесплатно.))
    
    '''
    context.bot.send_message(
        chat_id=context.job.context,
        text=dedent(message_text)
    )


def handle_delivery(context, update):
    query = update.callback_query

    if query.data == 'pickup':
        context.bot.send_message(
            chat_id=query.message.chat.id,
            text='Вы выбрали самовывоз'
        )
    else:
        tg_id, position = json.loads(query.data)
        context.bot.send_message(
            chat_id=tg_id,
            text=f'Необходимо доставить заказ №{query.message.chat.id}'
        )
        context.bot.send_location(
            chat_id=tg_id,
            longitude=position[1],
            latitude=position[0]
        )

        context.job_queue.run_once(pizza_not_delivered, 10, context=query.message.chat.id)

    return 'END'


def start_without_shipping(context, update, price):
    chat_id = update.callback_query.message.chat.id
    payment_token = os.getenv('PAY_TOKEN')
    title = f'Order №{chat_id}'
    description = 'Сразу же после оплаты Ваша пицца отправится в печь'
    payload = 'Custom_order'
    currency = 'RUB'
    prices = [LabeledPrice('Test', price * 100)]
    context.bot.sendInvoice(
        chat_id,
        title,
        description,
        payload,
        payment_token,
        currency,
        prices
    )


def precheckout_callback(update, context):
    query = update.pre_checkout_query
    if query.invoice_payload != f"Custom_order":
        context.bot.answer_pre_checkout_query(
            pre_checkout_query_id=query.id,
            ok=False,
            error_message="Что то пошло не так"
        )
    else:
        context.bot.answer_pre_checkout_query(
            pre_checkout_query_id=query.id,
            ok=True
        )


def successful_payment_callback(update, context):

    context.bot.send_message(
        chat_id=update.message.chat_id,
        text='Пришлите Ваш адрес текстом или Вашу геопозицию'
    )
    context.bot.delete_message(
        chat_id=update.message.chat_id,
        message_id=update.message.message_id
    )


def handle_users_reply(update, context, client_id, client_secret, grant_type, yandex_token):
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
        'HANDLE_MENU': partial(handle_menu, access_token=access_token, products=products),
        'HANDLE_DESCRIPTION': partial(handle_description, access_token=access_token, products=products),
        'HANDLE_CART': partial(handle_cart, access_token=access_token, products=products),
        'HANDLE_WAITING': partial(handle_waiting, yandex_token=yandex_token, access_token=access_token),
        'HANDLE_DELIVERY': handle_delivery,
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
    tg_token = os.getenv('TELEGRAM_TOKEN')
    yandex_token = os.getenv('YANDEX_TOKEN')
    payment_token = os.getenv('PAYMENT_TOKEN')

    updater = Updater(tg_token)
    dispatcher = updater.dispatcher
    jq = updater.job_queue

    dispatcher.add_handler(CallbackQueryHandler(partial(
        handle_users_reply,
        client_id=client_id,
        client_secret=client_secret,
        grant_type=grant_type,
        yandex_token=yandex_token,
    )))
    dispatcher.add_handler(MessageHandler(Filters.text, partial(
        handle_users_reply,
        client_id=client_id,
        client_secret=client_secret,
        grant_type=grant_type,
        yandex_token=yandex_token,
    )))
    dispatcher.add_handler(CommandHandler('start', partial(
        handle_users_reply,
        client_id=client_id,
        client_secret=client_secret,
        grant_type=grant_type,
        yandex_token=yandex_token,
    )))
    dispatcher.add_handler(MessageHandler(Filters.location, partial(
        handle_users_reply,
        client_id=client_id,
        client_secret=client_secret,
        grant_type=grant_type,
        yandex_token=yandex_token
    )))
    dispatcher.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    dispatcher.add_handler(MessageHandler(Filters.successful_payment, successful_payment_callback))

    dispatcher.add_error_handler(error)

    updater.start_polling()
    updater.idle()
