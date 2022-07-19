from __future__ import annotations

import asyncio
import configparser
import json
import logging
import os
import sys
from datetime import datetime, timedelta

import asyncio_mqtt
from dotenv import load_dotenv
from lemon import api
from lemon.market_data.model.quote import Quote

# config logging format
logfmt = '%(asctime)s : %(levelname)7s : %(message)s'

# Global variable with latest Quotes
quotes: dict = {}

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def load_config() -> tuple[str, str, list]:
    '''Load the configuration from env variable or .env file or config.ini file.'''
    load_dotenv()  # load environment variables from .env.
    api_key = os.getenv("LEMON_API_KEY")

    # Load configuration from config.ini file
    config = configparser.ConfigParser(
        # Allow keys without values for the isins, allow inline comments
        allow_no_value=True, inline_comment_prefixes=('#', ';'))
    # keep the case of the keys, don't convert to lowercase:
    config.optionxform = str  # type: ignore
    config.read('config.ini')  # read the config file
    if not api_key:  # if no API key is provided in env, read it from the config file
        api_key = config.get('API', 'LEMON_API_KEY', fallback=None)  # get the api key
    loglevel = config.get('LOGGING', 'loglevel', fallback='INFO')  # get the log level
    isins = config.items('ISINS')  # get all items from section 'ISINS'
    instruments = [isin[0] for isin in isins]  # get only the isins keys

    if not api_key:
        logging.error("No API key found. Please set LEMON_API_KEY in env variable or .env or config.ini")
        sys.exit(1)

    return api_key, loglevel, instruments


def get_credentials(api_key: str)-> tuple[api.Api, str, str, datetime]:
    '''Get the token for the MQTT broker connection from the Lemons REST API auth endpoint.
    Use `expires_at` to reconnect, because this connection will stop.
    receiving data: https://docs.lemon.markets/live-streaming/overview#stream-authorization
    '''
    logging.info("Fetching credentials for live streaming...")
    # Lemon Markets API Client
    lemon_markets_client = api.create(
        market_data_api_token=api_key, trading_api_token="trading-api-is-not-used", env='paper')
    try:
        response = lemon_markets_client.market_data.post(
            "https://realtime.lemon.markets/v1/auth", json={})
        response = response.json()
        expires_at = datetime.fromtimestamp(response['expires_at'] / 1000)
        user_id = response['user_id']
        token = response['token']
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)
    return lemon_markets_client, user_id, token, expires_at


def print_quote(quote) -> None:
    '''Print a single quote.'''
    ask = format(quote.a / 10000, ".4f")
    bid = format(quote.b / 10000, ".4f")
    date = datetime.fromtimestamp(quote.t / 1000.0).isoformat(timespec='milliseconds')
    logging.info(f"{quote.isin} (exc={quote.mic}, ask={ask}, bid={bid}, date={date})")


# Live Streaming Callback Functions
def on_connect(mqtt_client, userdata, flags, rc):
    '''Callback when the client connects to the broker.'''
    logging.info(f"Connected. Subscribing to {user_id}...")
    mqtt_client.subscribe(user_id)


def on_subscribe(mqtt_client, userdata, level, buff):
    '''Callback when the client subscribes to a topic.'''
    global quotes
    logging.info(f"Subscribed. Publishing requested instruments to {user_id}.subscriptions...")
    mqtt_client.publish(f"{user_id}.subscriptions", ",".join(instruments))
    # This is a great place to fetch `/v1/quotes/latest` on time via REST, so
    # you have _all_ the latest quotes and you can update them via incoming live stream messages.
    logging.info("Published. Fetching latest quotes for initialization...")
    latest = lemon_markets_client.market_data.quotes.get_latest(
        isin=instruments, epoch=True, decimals=False)
    for quote in latest.results:
        quotes[quote.isin] = quote
        print_quote(quote)
    logging.info("Initialized. Waiting for live stream messages...")


def on_message(client, userdata, msg):
    '''Callback when the client receives a message.'''
    global quotes
    data = json.loads(msg.payload)
    quote = Quote._from_data(data, int, int)
    quotes[quote.isin] = quote
    print_quote(quote)


def on_log(client, userdata, level, buf):
    '''Callback when the client has log information.'''
    logging.debug(f"Log: {buf}")


def check_token(api_key: str, expires_at: datetime):
    '''Check if the token is still valid, one hour before expiration.'''
    now = datetime.now() + timedelta(hours=1)
    if now > expires_at:
        logging.warn("Token expired. Fetching new token...")
        lemon_markets_client, user_id, token, expires_at = get_credentials(api_key)
    return lemon_markets_client, user_id, token, expires_at


async def main(mqtt_client, user_id):
    '''This does not work yet because of my lack of understanding of the asyncio stuff...'''
    async with mqtt_client as client:
        # client.on_connect = on_connect
        # client.on_subscribe = on_subscribe
        # client.on_message = on_message
        # client.on_log = on_log
        # await client.connect()
        # await client.subscribe(user_id)
        # await client.wait_for_disconnect()
        async with client.unfiltered_messages() as messages:
            await client.subscribe(user_id)
            async for message in messages:
                print(message.payload.decode())


if __name__ == "__main__":
    # Load configuration
    api_key, loglevel, instruments = load_config()

    # Set logging level and format
    logging.basicConfig(format=logfmt, level=loglevel)

    # Request Live Streaming Credentials
    lemon_markets_client, user_id, token, expires_at = get_credentials(api_key)
    logging.info(f"Fetched Token. Token expires at {expires_at.isoformat()}")

    # Prepare Live Streaming Connection
    mqtt_client = asyncio_mqtt.Client(hostname="mqtt.ably.io", username=token, client_id="Ably_Client")

    asyncio.run(main(mqtt_client, user_id))
