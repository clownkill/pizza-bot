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
```

## Как запустить

* Для запуска telegram-бота необходимо выполнить:
```
python tg_bot.py
```

## Цель проекта

Код написан в образовательных целях на онлайн-курсе для веб-разработчиков [dvmn.org](https://dvmn.org).
