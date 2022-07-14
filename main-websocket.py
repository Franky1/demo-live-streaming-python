from __future__ import annotations

import configparser
import json
import os
import sys
from datetime import datetime, timedelta

import msgpack
import websocket
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
        allow_no_value=True, inline_comment_prefixes=('#', ';'))
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


def check_token(api_key: str, expires_at: datetime):
    '''Check if the token is still valid, one hour before expiration.'''
    now = datetime.now() + timedelta(hours=1)
    if now > expires_at:
        print("Token expired. Fetching new token...")
        lemon_markets_client, user_id, token, expires_at = get_credentials(api_key)
    return lemon_markets_client, user_id, token, expires_at


def print_quote(quote) -> None:
    '''Print a single quote.'''
    ask = format(quote.a / 10000, ".4f")
    bid = format(quote.b / 10000, ".4f")
    date = datetime.fromtimestamp(quote.t / 1000.0).isoformat(timespec='milliseconds')
    print(f"{quote.isin} (exc={quote.mic}, ask={ask}, bid={bid}, date={date})")


def on_message(ws, message):
    msgpack_data = msgpack.loads(message)
    action = msgpack_data.get('action', None)
    if action == 0:
        print("Heartbeat received")
    elif action == 4:
        print("Connection Details received")
    print(f'Message: {msgpack_data}')


def on_error(ws, error):
    print(f'Error: {error}')


def on_close(ws, close_status_code, close_msg):
    print("Closed connection")


def on_open(ws):
    print("Opened connection")


def on_pong(ws, pong_data):
    print(f'Pong: {pong_data}')


def on_data(ws, data, datatype, flag):
    msgpack_data = msgpack.loads(data)
    print(f'Data: {msgpack_data}')


# so far the connection with websockets is working
# however i have no clue how to activate or subscribe to the data
if __name__ == "__main__":
    # Load configuration
    api_key, instruments = load_config()

    # Request Live Streaming Credentials
    lemon_markets_client, user_id, token, expires_at = get_credentials(api_key)
    print(f"Fetched.     Token expires at {expires_at.isoformat()}")

    # Prepare Live Streaming Connection
    # websocket.enableTrace(True)
    websocket.setdefaulttimeout(5)
    ws = websocket.WebSocketApp(url=f'wss://realtime.ably.io?client_id={user_id}&access_token={token}&format=msgpack&heartbeats=true',
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close,
                                on_pong=on_pong,
                                on_data=on_data)

    # Handle loop and disconnect on keyboard interrupt
    try:
        ws.run_forever(ping_interval=5, ping_payload="PING")
        # ws.run_forever()
    except KeyboardInterrupt:
        ws.close()
    finally:
        print("Disconnected. Exiting...")
        sys.exit(0)
