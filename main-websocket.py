from __future__ import annotations

import configparser
import json
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


def attach_channel(ws: websocket.WebSocketApp, user_id: str) -> None:
    '''Attaching to my channel.'''
    print("Attaching to channel...")
    ws.send(json.dumps({
        'action': WsActions.ATTACH.value,
        'channel': user_id,
    }))


def detach_channel(ws: websocket.WebSocketApp, user_id: str) -> None:
    '''Detaching from my channel.'''
    print("Detaching from channel...")
    ws.send(json.dumps({
        'action': WsActions.DETACH.value,
        'channel': user_id,
    }))


def close(ws: websocket.WebSocketApp, user_id: str) -> None:
    '''Close the websocket connection gracefully.'''
    print("Closing connection...")
    ws.send(json.dumps({
        'action': WsActions.CLOSE.value,
        'channel': user_id,
    }))


# This DOES NOT work, because i get a "Permission denied" error
def publish_message(ws: websocket.WebSocketApp, user_id: str, instruments: list) -> None:
    '''Publish message.'''
    print("Publish message...")
    ws.send(json.dumps({
        'action': WsActions.MESSAGE.value,
        'channel': user_id,
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
    print(f"{WsActions(action).name} received")
    print(f'{WsActions(action).name} : {decoded_data}')
    if action == WsActions.HEARTBEAT.value:
        pass
    elif action == WsActions.NACK.value:
        pass
    elif action == WsActions.CONNECTED.value:
        attach_channel(ws, user_id)
    elif action == WsActions.ATTACHED.value:
        publish_message(ws, user_id, instruments)
    elif action == WsActions.DETACHED.value:
        pass
    elif action == WsActions.SYNC.value:
        pass
    else:
        pass


def on_error(ws, error):
    print(f'Error: {error}')


def on_close(ws, close_status_code, close_msg):
    print("Closed connection")


def on_open(ws):
    print("Opened connection")


def on_pong(ws, pong_data):
    print(f'Pong: {pong_data}')


def on_data(ws, data, datatype, flag):
    # decoded_data = msgpack.loads(data)
    decoded_data = json.loads(data)
    print(f'Datatype: {datatype}')
    print(f'Data: {decoded_data}')


# so far the connection with websockets is working, but the subscription is not working
if __name__ == "__main__":
    # Load configuration
    api_key, instruments = load_config()

    # Request Live Streaming Credentials
    lemon_markets_client, user_id, token, expires_at = get_credentials(api_key)
    print(f"Fetched.     Token expires at {expires_at.isoformat()}")

    # Prepare Live Streaming Connection
    # websocket.enableTrace(True)  # enable for debugging
    websocket.setdefaulttimeout(5)
    ws = websocket.WebSocketApp(url=f'wss://realtime.ably.io?client_id={user_id}&access_token={token}&format=json&heartbeats=true',
                                on_open=on_open,
                                on_message=on_message,
                                # on_data=on_data,
                                on_error=on_error,
                                on_close=on_close,
                                # on_pong=on_pong,
                                keep_running=False)

    # Handle loop and disconnect on keyboard interrupt
    try:
        ws.run_forever(ping_interval=5, ping_payload="PING")
        # ws.run_forever()
    except KeyboardInterrupt:
        # Close the websocket connection gracefully
        # However this does not work...
        print("KeyboardInterrupt...")
        detach_channel(ws, user_id)
        time.sleep(1)
        close(ws, user_id)
        time.sleep(1)
    finally:
        ws.close()
        print("Disconnected. Exiting...")
        sys.exit(0)
