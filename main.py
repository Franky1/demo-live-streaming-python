import configparser
import json
import sys
from datetime import datetime

import paho.mqtt.client as mqtt
from lemon import api
from lemon.market_data.model.quote import Quote


# Configuration
config = configparser.ConfigParser(allow_no_value=True, inline_comment_prefixes=('#',))
config.optionxform = str  # keep the case of the keys, don't convert to lowercase
config.read('config.ini')  # read the config file
api_key = config.get('API', 'key', fallback=None)  # get the api key
isins = config.items('ISINS')  # get all items from section 'ISINS'
instruments = [isin[0] for isin in isins]  # get only the isins keys

## Quotes
quotes = {}
updates = 0
spinner = "-\\|/"


def get_credentials(api_key : str):
    print("Fetching credentials for live streaming...")
    # Lemon Markets API Client
    lemon_markets_client = api.create(market_data_api_token=api_key, trading_api_token="trading-api-is-not-used", env='paper')
    try:
        response = lemon_markets_client.market_data.post("https://realtime.lemon.markets/v1/auth", json={})
        response = response.json()
        user_id = response['user_id']
        token = response['token']
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    return lemon_markets_client, user_id, token


def print_quotes():
    print("\r", end="")
    for instrument in instruments:
        ask = format(quotes[instrument].a / 10000, ".4f")
        bid = format(quotes[instrument].b / 10000, ".4f")
        date = datetime.fromtimestamp(quotes[instrument].t / 1000.0).isoformat(timespec='milliseconds')
        print(f"{instrument}(ask={ask},bid={bid},date={date})", end=" ")
    print(spinner[updates % len(spinner)], end="")
    sys.stdout.flush()


# Live Streaming Callback Functions
def on_connect(mqtt_client, userdata, flags, rc):
    print(f"Connected.   Subscribing to {user_id}")
    mqtt_client.subscribe(user_id)


def on_subscribe(mqtt_client, userdata, level, buff):
    print(f"Subscribed.  Publishing requested instruments to {user_id}.subscriptions...")
    mqtt_client.publish(f"{user_id}.subscriptions", ",".join(instruments))
    # This is a great place to fetch `/v1/quotes/latest` on time via REST, so
    # you have _all_ the latest quotes and you can update them via incoming
    # live stream messages.
    print("Published.   Fetching latest quotes for initialization...")
    latest = lemon_markets_client.market_data.quotes.get_latest(isin=instruments, epoch=True, decimals=False)
    for quote in latest.results:
        quotes[quote.isin] = quote
    print("Initialized. Waiting for live stream messages...")
    print_quotes()


def on_message(client, userdata, msg):
    global updates
    data = json.loads(msg.payload)
    quote = Quote._from_data(data, int, int)
    quotes[quote.isin] = quote
    updates += 1
    print_quotes()


if __name__ == "__main__":
    # Request Live Streaming Credentials
    lemon_markets_client, user_id, token = get_credentials(api_key)

    # Prepare Live Streaming Connection
    mqtt_client = mqtt.Client("Ably_Client")
    mqtt_client.username_pw_set(username=token)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_subscribe = on_subscribe

    ##Connect and receive data
    print("Fetched.     Connecting MQTT client...")
    mqtt_client.connect("mqtt.ably.io")
    mqtt_client.loop_forever()
    print("Disconnected.")
