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
3. Run the code: `python main.py`

You should see something like this:

```log
Fetching credentials for live streaming...
Fetched.     Connecting MQTT client...
Connected.   Subscribing to usr_qyJDQss5546j0bXjtWtLlRC3B4CNBdmg9V...
Subscribed.  Publishing requested instruments to usr_qyJDQss5546j0bXjtWtLlRC3B4CNBdmg9V.subscriptions...
Published.   Fetching latest quotes for initialization...
Initialized. Waiting for live stream messages...
US0378331005(ask=140.6000,bid=140.5200,date=2022-07-07T13:05:31.000) US88160R1014(ask=689.3000,bid=688.2000,date=2022-07-07T13:05:34.806) -
```

If you pay close attention, you will notice updates to the data in the
bottom line as your code receives new updates.
