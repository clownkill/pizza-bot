# Telegram pizza bot
Telegram-бот для продажи пиццы в телеграмм. Принимает оплату и организует доставку пиццы по адресу или самовывоз.

## Как установить

* Python3 должен быть установлен
* Скопировать репозиторий к себе на компьютер:
```
https://github.com/clownkill/pizza-bot
```
* Установите зависимости:
```
pip install -r requrirements
```

## Переменные окружения

```
CLIENT_ID=[ID для доступа CMS moltin.com]
CLIENT_SECRET=[ClientSecret для доступа CMS moltin.com]
GRANT_TYPE=[GrantType для установки прав доступа к CMS moltin.com]
TELEGRAM_TOKEN=[Telegram-токен для достуба к боту]
REDIS_HOST=[Хост для базы данных Redix]
REDIS_PORT=[Порт базы данных Redis]
REDIS_DB_PSWD=[Пароль к базе данных Redis]
YANDEX_TOKEN=[Токен для доступа к API Yandex Geocoder]
PAY_TOKEN=[Токен для платежной системы]
PAGE_ACCESS_TOKEN=[Токен для страницы бота в Facebook]
VERIFY_TOKEN=[Токен для валидации вебхука в Facebook]
```

## Как запустить

* Для запуска telegram-бота необходимо выполнить:
```
python tg_bot.py
```

* Для запуска facebook-бота с помощью локального вебхука:
- создать [страницу Facebook](https://www.facebook.com/bookmarks/pages?ref_type=logout_gear).
- [создать приложение](https://developers.facebook.com/apps/).
- получить токен с правами на messenger:
![token_1](https://dvmn.org/filer/canonical/1565713050/213/)
![token_2](https://dvmn.org/filer/canonical/1565713050/214/)
![token_3](https://dvmn.org/filer/canonical/1565713041/195/)
![token_4](https://dvmn.org/filer/canonical/1565713041/196/)
![token_5](https://dvmn.org/filer/canonical/1565713042/197/)
![token_6](https://dvmn.org/filer/canonical/1565713043/199/)
![token_7](https://dvmn.org/filer/canonical/1565713043/200/)
- выполнить ```gunicorn app:app```.
- выполнить ```ngrok http 127.0.0.1:8000```.
- подключить вебхук к facebook:
![connect webhook](https://dvmn.org/filer/canonical/1565713044/201/)
- добавить подписки (messages, messaging_postbacks) для вебхука:
![add subscriptions](https://dvmn.org/filer/canonical/1565713044/202/)

## Цель проекта

Код написан в образовательных целях на онлайн-курсе для веб-разработчиков [dvmn.org](https://dvmn.org).
