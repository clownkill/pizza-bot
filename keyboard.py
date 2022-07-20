import json
from pprint import pprint

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_paginator(products, per_page):
    items_per_page = per_page
    max_page = len(products) // items_per_page

    start = 0
    end = items_per_page

    paginated_products = []

    for _ in range(max_page):
        paginated_products.append(products[start:end])
        start = end
        end += items_per_page

    return paginated_products


def get_main_menu(products, page=0):
    products = get_paginator(products, 8)
    inline_keyboard = [
        [InlineKeyboardButton(product['name'], callback_data=product['id'])] for product in products[page]
    ]

    if page == len(products) - 1:
        inline_keyboard.append([InlineKeyboardButton('Назад', callback_data=f'pag, {page - 1}')])
    elif page == 0:
        inline_keyboard.append([InlineKeyboardButton('Вперед', callback_data=f'pag, {page + 1}')])
    else:
        inline_keyboard.append([InlineKeyboardButton('Назад', callback_data=f'pag, {page - 1}'),
                         InlineKeyboardButton('Вперед', callback_data=f'pag, {page + 1}')])

    inline_keyboard.append([InlineKeyboardButton('Корзина', callback_data='cart')])

    inline_kb_markup = InlineKeyboardMarkup(inline_keyboard)

    return inline_kb_markup


def get_description_menu():
    inline_keyboard = [
        [InlineKeyboardButton('Добавить в корзину', callback_data=1)],
        [InlineKeyboardButton('Корзина', callback_data='cart')],
        [InlineKeyboardButton('Назад', callback_data='back')],
    ]
    inline_kb_markup = InlineKeyboardMarkup(inline_keyboard)

    return inline_kb_markup


def get_cart_menu(cart_items):
    inline_keyboard = [
        [InlineKeyboardButton(f"Убрать из корзины {item['name']}", callback_data=f"del {item['id']}")]
        for item in cart_items
    ]
    inline_keyboard.append([InlineKeyboardButton('Оплатить', callback_data='pay')])
    inline_keyboard.append([InlineKeyboardButton('В меню', callback_data='menu')])
    inline_kb_markup = InlineKeyboardMarkup(inline_keyboard)

    return inline_kb_markup


def get_delivery_menu(supplier, current_position):
    data = json.dumps([supplier, current_position])
    inline_keyboard = [
        [InlineKeyboardButton('Доставка', callback_data=f'{data}')],
        [InlineKeyboardButton('Самовывоз', callback_data='pickup')],
    ]
    inline_kb_markup = InlineKeyboardMarkup(inline_keyboard)

    return inline_kb_markup
