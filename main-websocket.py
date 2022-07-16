from __future__ import annotations
from cmath import log

import configparser
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from enum import Enum, unique

import msgpack
import websocket
from dotenv import load_dotenv
from lemon import api
from lemon.market_data.model.quote import Quote


@unique
class WsActions(Enum):
    HEARTBEAT = 0
    ACK = 1
    NACK = 2
    CONNECT = 3
    CONNECTED = 4
    DISCONNECT = 5
    DISCONNECTED = 6
    CLOSE = 7
    CLOSED = 8
    ERROR = 9
    ATTACH = 10
    ATTACHED = 11
    DETACH = 12
    DETACHED = 13
    PRESENCE = 14
    MESSAGE = 15
    SYNC = 16
    AUTH = 17


# config logging
logfmt = '%(asctime)s : %(levelname)7s : %(message)s'
logging.basicConfig(level=logging.INFO, format=logfmt)


# Global variable with latest Quotes
quotes: dict = {}
instruments: list = []
user_id: str = ""


def load_config() -> tuple[str, list]:
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
    isins = config.items('ISINS')  # get all items from section 'ISINS'
    instruments = [isin[0] for isin in isins]  # get only the isins keys

    if not api_key:
        logging.error("No API key found. Please set LEMON_API_KEY in env variable or .env or config.ini")
        sys.exit(1)

    return api_key, instruments


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


def check_token(api_key: str, expires_at: datetime):
    '''Check if the token is still valid, one hour before expiration.'''
    now = datetime.now() + timedelta(hours=1)
    if now > expires_at:
        logging.warn("Token expired. Fetching new token...")
        lemon_markets_client, user_id, token, expires_at = get_credentials(api_key)
    return lemon_markets_client, user_id, token, expires_at


def print_quote(quote) -> None:
    '''Print a single quote.'''
    ask = format(quote.a / 10000, ".4f")
    bid = format(quote.b / 10000, ".4f")
    date = datetime.fromtimestamp(quote.t / 1000.0).isoformat(timespec='milliseconds')
    logging.info(f"{quote.isin} (exc={quote.mic}, ask={ask}, bid={bid}, date={date})")


def attach_channel(ws: websocket.WebSocketApp, user_id: str) -> None:
    '''Attaching to my channel.'''
    logging.info("Attaching to channel...")
    ws.send(json.dumps({
        'action': WsActions.ATTACH.value,
        'channel': user_id,
    }))


def detach_channel(ws: websocket.WebSocketApp, user_id: str) -> None:
    '''Detaching from my channel.'''
    logging.info("Detaching from channel...")
    ws.send(json.dumps({
        'action': WsActions.DETACH.value,
        'channel': user_id,
    }))


def close(ws: websocket.WebSocketApp, user_id: str) -> None:
    '''Close the websocket connection gracefully.'''
    logging.info("Closing connection...")
    ws.send(json.dumps({
        'action': WsActions.CLOSE.value,
        'channel': user_id,
    }))


def publish_message(ws: websocket.WebSocketApp, user_id: str, instruments: list) -> None:
    '''Publish message. Subscribe to all instruments.'''
    logging.info("Publish message...")
    ws.send(json.dumps({
        'action': WsActions.MESSAGE.value,
        'channel': f'{user_id}.subscriptions',
        "msgSerial": 0,
        "messages": [
            {
                "name": "isins",
                "data": ",".join(instruments)
            }
        ]
    }))


def on_message(ws, message):
    global user_id
    global instruments
    # decoded_data = msgpack.loads(message)
    decoded_data = json.loads(message)
    action = decoded_data.get('action', None)
    logging.debug(f"{WsActions(action).name} received")
    logging.debug(f'{WsActions(action).name} : {decoded_data}')

    if action == WsActions.CONNECTED.value:
        attach_channel(ws, user_id)
    elif action == WsActions.ATTACHED.value:
        publish_message(ws, user_id, instruments)


def on_error(ws, error):
    logging.error(f'Error: {error}')


def on_close(ws, close_status_code, close_msg):
    logging.info("Closed connection")


def on_open(ws):
    logging.info("Opened connection")


def on_pong(ws, pong_data):
    logging.debug(f'Pong: {pong_data}')


def on_data(ws, data, datatype, flag):
    # decoded_data = msgpack.loads(data)
    decoded_data = json.loads(data)
    logging.debug(f'Datatype: {datatype}')
    logging.debug(f'Data: {decoded_data}')


# so far the connection with websockets is working, but the subscription is not working
if __name__ == "__main__":
    # Load configuration
    api_key, instruments = load_config()

    # Request Live Streaming Credentials
    lemon_markets_client, user_id, token, expires_at = get_credentials(api_key)
    logging.info(f"Fetched Token. Token expires at {expires_at.isoformat()}")

    # Prepare Live Streaming Connection
    # websocket.enableTrace(True)  # enable for debugging
    websocket.setdefaulttimeout(5)
    ws = websocket.WebSocketApp(url=f'wss://realtime.ably.io?client_id={user_id}&access_token={token}&format=json&heartbeats=true',
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close,
                                # on_data=on_data,
                                # on_pong=on_pong,
                                keep_running=False)

    # Handle loop and disconnect on keyboard interrupt
    try:
        ws.run_forever(ping_interval=5, ping_payload="PING")
        # ws.run_forever()
    except KeyboardInterrupt:
        # Close the websocket connection gracefully
        # However this does not work...
        logging.warn("KeyboardInterrupt...")
        detach_channel(ws, user_id)
        time.sleep(1)
        close(ws, user_id)
        time.sleep(1)
    finally:
        ws.close()
        logging.info("Disconnected. Exiting...")
        sys.exit(0)
