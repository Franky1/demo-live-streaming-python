from __future__ import annotations

import configparser
import json
import os
import sys
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from lemon import api
from lemon.market_data.model.quote import Quote

# Global variable with latest Quotes
quotes = {}


def load_config() -> tuple[str, list]:
    '''Load the configuration from env variable or .env file or config.ini file.'''
    load_dotenv()  # load environment variables from .env.
    api_key = os.getenv("LEMON_API_KEY")

    # Load configuration from config.ini file
    config = configparser.ConfigParser(
        # Allow keys without values for the isins, allow inline comments
        allow_no_value=True, inline_comment_prefixes=('#',';'))
    config.optionxform = str  # keep the case of the keys, don't convert to lowercase
    config.read('config.ini')  # read the config file
    if not api_key:  # if no API key is provided in env, read it from the config file
        api_key = config.get('API', 'LEMON_API_KEY', fallback=None)  # get the api key
    isins = config.items('ISINS')  # get all items from section 'ISINS'
    instruments = [isin[0] for isin in isins]  # get only the isins keys

    if not api_key:
        print("No API key found. Please set LEMON_API_KEY in env variable or .env or config.ini")
        sys.exit(1)

    return api_key, instruments


def get_credentials(api_key: str)-> tuple[api.Api, str, str, datetime]:
    '''Get the token for the MQTT broker connection from the Lemons REST API auth endpoint.'''
    print("Fetching.    Credentials for live streaming...")
    # Lemon Markets API Client
    lemon_markets_client = api.create(
        market_data_api_token=api_key, trading_api_token="trading-api-is-not-used", env='paper')
    try:
        response = lemon_markets_client.market_data.post(
            "https://realtime.lemon.markets/v1/auth", json={})
        response = response.json()
        # **NOTE:** Use `expires_at` to reconnect, because this connection will stop
        # receiving data: https://docs.lemon.markets/live-streaming/overview#stream-authorization
        expires_at = datetime.fromtimestamp(response['expires_at'] / 1000)
        user_id = response['user_id']
        token = response['token']
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    return lemon_markets_client, user_id, token, expires_at


def print_quote(quote) -> None:
    '''Print a single quote.'''
    ask = format(quote.a / 10000, ".4f")
    bid = format(quote.b / 10000, ".4f")
    date = datetime.fromtimestamp(quote.t / 1000.0).isoformat(timespec='milliseconds')
    print(f"{quote.isin} (exc={quote.mic}, ask={ask}, bid={bid}, date={date})")


# Live Streaming Callback Functions
def on_connect(mqtt_client, userdata, flags, rc):
    '''Callback when the client connects to the broker.'''
    print(f"Connected.   Subscribing to {user_id}...")
    mqtt_client.subscribe(user_id)


def on_subscribe(mqtt_client, userdata, level, buff):
    '''Callback when the client subscribes to a topic.'''
    global quotes
    print(f"Subscribed.  Publishing requested instruments to {user_id}.subscriptions...")
    mqtt_client.publish(f"{user_id}.subscriptions", ",".join(instruments))
    # This is a great place to fetch `/v1/quotes/latest` on time via REST, so
    # you have _all_ the latest quotes and you can update them via incoming
    # live stream messages.
    print("Published.   Fetching latest quotes for initialization...")
    latest = lemon_markets_client.market_data.quotes.get_latest(
        isin=instruments, epoch=True, decimals=False)
    for quote in latest.results:
        quotes[quote.isin] = quote
        print_quote(quote)
    print("Initialized. Waiting for live stream messages...")


def on_message(client, userdata, msg):
    '''Callback when the client receives a message.'''
    global quotes
    data = json.loads(msg.payload)
    quote = Quote._from_data(data, int, int)
    quotes[quote.isin] = quote
    print_quote(quote)


def on_log(client, userdata, level, buf):
    '''Callback when the client has log information.'''
    print(f"Log: {buf}")


def check_token(api_key: str, expires_at: datetime):
    '''Check if the token is still valid, one hour before expiration.'''
    now = datetime.now() + timedelta(hours=1)
    if now > expires_at:
        print("Token expired. Fetching new token...")
        lemon_markets_client, user_id, token, expires_at = get_credentials(api_key)
    return lemon_markets_client, user_id, token, expires_at


if __name__ == "__main__":
    # Load configuration
    api_key, instruments = load_config()

    # Request Live Streaming Credentials
    lemon_markets_client, user_id, token, expires_at = get_credentials(api_key)
    print(f"Fetched.     Token expires at {expires_at.isoformat()}")

    # Prepare Live Streaming Connection
    mqtt_client = mqtt.Client(client_id="Ably_Client")
    mqtt_client.username_pw_set(username=token)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_subscribe = on_subscribe
    # mqtt_client.on_log = on_log  # enable logging

    # Connect to the MQTT broker
    print("Prepared.    Connecting MQTT client...")
    try:
        mqtt_client.connect(host="mqtt.ably.io")
    except Exception as e:
        print(f"Connect Error: {e}")
        sys.exit(1)

    # Handle loop and disconnect on keyboard interrupt
    try:
        mqtt_client.loop_forever(timeout=5, retry_first_connection=True)
    except KeyboardInterrupt:
        mqtt_client.disconnect()
        mqtt_client.loop_stop()
    finally:
        print("Disconnected. Exiting...")
        sys.exit(0)
