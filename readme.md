# Live Streaming for 🍋.markets

This is a small example about using the [live streaming API](https://docs.lemon.markets/live-streaming/overview) from [lemon.markets](https://lemon.markets/) using Python.

This example will implement a basic stock ticker for the command line.

## Get your API key

<https://docs.lemon.markets/authentication>

Login to your [lemon.markets](https://lemon.markets/) account and go to your [Dashboard](https://dashboard.lemon.markets/) page.
Select `Market Data` and click `Create key`, if no API Key exists yet.
Copy the API Key and make it accessible from this example application with one of the following options:

1. Put the API Key in an environment variable called `LEMON_API_KEY` or
2. Put the API Key in the `.env` file in the root directory of this project or
3. Put the API Key in the `config.ini` file in the root directory of this project.

## Quick Start

1. Set your API Key with one of the options described above.
2. Install the dependencies using `pip3 install -r requirements.txt`
3. Select the ISINs you want to track in the `config.ini` file.
4. Run the code: `python main.py`

You should see something like this:

```log
Fetching.    Credentials for live streaming...
Fetched.     Token expires at 2022-07-14T02:00:00.074000
Prepared.    Connecting MQTT client...
Connected.   Subscribing to usr_qyCcCHHPP729gVhgfP228NT3csVNNQ8MqB...
Subscribed.  Publishing requested instruments to usr_qyCcCHHPP729gVhgfP228NT3csVNNQ8MqB.subscriptions...
Published.   Fetching latest quotes for initialization...
US0378331005 (exc=XMUN, ask=144.7400, bid=144.4800, date=2022-07-13T21:59:59.421)
US88160R1014 (exc=XMUN, ask=706.9000, bid=705.9000, date=2022-07-13T21:59:57.225)
Initialized. Waiting for live stream messages...
US0378331005 (exc=XMUN, ask=145.5600, bid=145.3800, date=2022-07-13T21:59:59.740)
US88160R1014 (exc=XMUN, ask=697.4000, bid=696.8000, date=2022-07-13T21:59:59.273)
```

If you pay close attention, you will notice updates to the data in the
bottom line as your code receives new updates.
