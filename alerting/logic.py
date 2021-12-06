from opencoinwatch import config
from alerting.models import Alert, Job
from alerting import common_utils

from django.conf import settings

from binance.client import Client
import pandas as pd
import numpy as np
import os
import datetime
import math
import pytz
from dateutil import parser


"""
Credits for some portions of this file go to Peter Nistrup. Obtained from https://gist.github.com/nistrup/1e724d6e450fd1da09a0782e6bfcd41a
"""


def symbol_to_binance(symbol):
    return f'{symbol}USDT'


def get_initial_datetime():
    return datetime.datetime.now() - datetime.timedelta(days=7)


def minutes_of_new_data(client, symbol, kline_size, data):
    if len(data) > 0:
        old = parser.parse(data["timestamp"].iloc[-1])
    else:
        old = get_initial_datetime()
    new = pd.to_datetime(client.get_klines(symbol=symbol, interval=kline_size)[-1][0], unit='ms')
    return old, new


def get_all_binance(client, symbol, kline_size, save=False):
    binsizes = {"1m": 1, "5m": 5, "1h": 60, "6h": 360, "1d": 1440}

    symbol = symbol_to_binance(symbol)

    filename = f'{symbol}-{kline_size}-data.csv'
    data_df = pd.read_csv(filename) if os.path.isfile(filename) else pd.DataFrame()

    oldest_point, newest_point = minutes_of_new_data(client, symbol, kline_size, data_df)
    delta_min = (newest_point - oldest_point).total_seconds() / 60
    available_data = math.ceil(delta_min / binsizes[kline_size])

    if oldest_point == get_initial_datetime():
        print(f'Downloading all available {kline_size} data for {symbol}.')
    else:
        print(
            f'Downloading {delta_min} minutes of new data available for {symbol}, i.e. {available_data} instances of {kline_size} data.')
    klines = client.get_historical_klines(symbol, kline_size, oldest_point.strftime("%d %b %Y %H:%M:%S"),
                                          newest_point.strftime("%d %b %Y %H:%M:%S"))
    data = pd.DataFrame(klines,
                        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av',
                                 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    if len(data_df) > 0:
        temp_df = pd.DataFrame(data)
        data_df = data_df.append(temp_df)
    else:
        data_df = data
    data_df.set_index('timestamp', inplace=True)
    if save:
        data_df.to_csv(filename)
    return data_df


def get_symbols(client):
    symbols = list()
    exchange_info = client.get_exchange_info()
    for symbol in exchange_info['symbols']:
        if symbol['quoteAsset'] == 'USDT':
            symbols.append(symbol['symbol'])
    return symbols


def download_symbol_data(client, symbols, kline_size, save=False):
    symbol_data = dict()
    for symbol in symbols:
        symbol_data[symbol] = get_all_binance(client, symbol, kline_size, save=save).astype('float')
    return symbol_data


def remove_symbols_with_few_data(symbol_data):
    symbol_data = symbol_data.copy()

    symbols_with_few_data = list()

    for symbol, data in symbol_data.items():
        n_rows = data.shape[0]
        if n_rows < 2500:
            symbols_with_few_data.append(symbol)

    for symbol in symbols_with_few_data:
        del symbol_data[symbol]

    return symbol_data


def create_dataset(symbol_data):
    data = {}
    for symbol, symbol_df in symbol_data.items():
        symbol_df.index = pd.to_datetime(symbol_df.index)
        symbol_df = symbol_df[~symbol_df.index.duplicated(keep='first')]  # Drop duplicated index
        data[symbol] = symbol_df['close']
    df = pd.concat(data, axis=1)

    # Delete columns whose last value is nan
    #     for column_name in df.columns:
    #         if pd.isnull(df[column_name].iloc[-1]):
    #             del df[column_name]

    df.fillna(0, inplace=True)
    return df


def get_exchange_rates_and_importances(symbols):
    client = Client(api_key=settings.BINANCE_API_KEY, api_secret=settings.BINANCE_SECRET_KEY)

    print("Downloading data...")
    symbol_data = download_symbol_data(client, symbols, '5m')
    exchange_rates = create_dataset(symbol_data)
    print("... data downloaded.")

    percentages = (exchange_rates.iloc[
                       -1] / exchange_rates * 100) - 100  # Change in percentages, from the point of view of the previous values
    percentages = percentages.iloc[:-1]  # Remove last row (the latest exchange rates)

    limit_vectorized = np.vectorize(common_utils.percentage_limit)

    percentages['limit'] = 5
    percentages['limit'] = np.cumsum(percentages['limit'])[::-1].values
    percentages['limit'] = limit_vectorized(percentages['limit'])
    limit = percentages.pop('limit')
    importances = np.abs(percentages.divide(limit, axis=0))

    return exchange_rates, importances


def create_alert(symbol, index, current_exchange_rate, referenced_exchange_rate, publish=False):
    print("...creating alert...")

    alert = Alert()
    alert.generated_time = datetime.datetime.now(pytz.timezone('Europe/Prague'))
    alert.referenced_time = pytz.UTC.localize(index).astimezone(pytz.timezone('Europe/Prague'))
    alert.symbol = symbol
    alert.current_exchange_rate = current_exchange_rate
    alert.referenced_exchange_rate = referenced_exchange_rate

    if publish:
        alert.publish()
        print("...alert published.")
    else:
        alert.prepare_for_validation()
        print("...alert prepared for validation.")


def generate_alert(symbol, symbol_exchange_rates, symbol_importances):
    """
    Return: boolean indicating whether an alert was created
    """
    print(f"Symbol {symbol}...")

    if (symbol_exchange_rates == 0).any():
        print("...exchange rates for symbol contain zeros, skipping.")
        return

    last_alert_generated_time = Alert.get_last_published_or_declined_alert_generated_time(symbol)
    if last_alert_generated_time is not None:
        last_alert_time_utc = last_alert_generated_time.astimezone(pytz.UTC).replace(tzinfo=None)
        symbol_importances = symbol_importances[symbol_importances.index > last_alert_time_utc]
        if len(symbol_importances) == 0:
            print(f"...no unprocessed data.")
            return

    argmax = symbol_importances.argmax()
    index = symbol_importances.index[argmax]
    current_exchange_rate = symbol_exchange_rates.iloc[-1]
    referenced_exchange_rate = symbol_exchange_rates.loc[index]
    importance = symbol_importances.loc[index]
    handicap = Alert.get_handicap_for_symbol(symbol, current_exchange_rate)
    importance_with_handicap = importance / handicap

    if importance_with_handicap < 1:
        Alert.get_all_validating_alerts(symbol).delete()
        print("...no significant changes, deleted any previous alerts.")
        return

    create_alert(symbol, index, current_exchange_rate, referenced_exchange_rate, publish=True)


def generate_alerts():
    symbols = config.SYMBOLS.keys()
    exchange_rates, importances = get_exchange_rates_and_importances(symbols)

    for symbol in symbols:
        symbol_importances = importances[symbol]
        symbol_exchange_rates = exchange_rates[symbol]
        generate_alert(symbol, symbol_exchange_rates, symbol_importances)


def generate_alerts_wrapper():
    print("############################# GENERATING ALERTS START #############################")

    job = Job()
    job.start_time = datetime.datetime.now(pytz.timezone('Europe/Prague'))
    job.save()

    try:
        generate_alerts()
    except:
        job.failed()
        raise

    job.succeeded()

    print("############################# GENERATING ALERTS END #############################")


def warn_recently_published():
    last_published_alert_published_time = Alert.get_last_published_alert_published_time()
    if last_published_alert_published_time is None:
        return False
    current_time = datetime.datetime.now(pytz.timezone('Europe/Prague'))
    time_difference_seconds = (current_time - last_published_alert_published_time).total_seconds()
    return time_difference_seconds < 60 * config.RECENTLY_PUBLISHED_WARNING_DURATION_MINUTES
