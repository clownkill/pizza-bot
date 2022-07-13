import json
from pprint import pprint

with open('pizzas_json/addresses.json', 'r') as fin:
    addresses = json.load(fin)

with open('pizzas_json/menu.json', 'r') as fin:
    menu = json.load(fin)

pprint(addresses)
pprint(menu)