from typing import Optional, Tuple
from collections import deque
from statistics import mean, stdev
from data.models import HistoricData, Security
from django.db.models.query import QuerySet

import numpy as np


class MovingAverage:
    def __init__(self, length: int):
        # ma length
        self._length = length
        self._queue: deque = deque(maxlen=length)

    def queue(self) -> deque:
        return self._queue


class EMA(MovingAverage):
    """
    Exponential Moving Average is calculated first computing the simple moving average for the first
    length entries and afterwards that sma is basis for the upcoming ema value.

    for a 5% trend, hence using a factor of 0.05 use a length of 39

    """

    def __init__(self, length: int):
        super().__init__(length)

        self.__factor = float(2 / (1 + length))
        self.__ema_reached = False

    def add(self, value: float) -> Optional[float]:
        """
        returns the current ema for the given value if a valid ema does exist, else None
        """

        self.__value = value

        # if the threshold for the ema is reached, we can use the factor calculation
        # in addition we use this value now for the queue
        if self.__ema_reached:
            self.__ema = (value * self.__factor) + (self.__ema * (1 - self.__factor))
            self._queue.appendleft(self.__ema)
            return self.__ema
        # for the first ema value, we have to calculate the sma as a first basis
        else:
            self._queue.appendleft(value)
            if len(self._queue) == self._length:
                self.__ema_reached = True
                self.__ema = mean(self._queue)
            return None


class SMA(MovingAverage):
    def __init__(self, length: int):
        super().__init__(length)

    def add(self, value: float) -> float:
        """
        returns the current ema for the given value if a valid ema does exist, else None
        """

        self.__value = value
        self._queue.appendleft(self.__value)
        self.__sma = mean(self._queue)

        return self.__sma
    
    def current_value(self) -> float:
        return self.__sma
    
    def getN(self) -> int:
        return len(self._queue)
    
    def getMax(self) -> float:
        return max(self._queue)
    
    def getMin(self) -> float:
        return min(self._queue)
    
    def getFirst(self) -> float:
        return self._queue[0]
    
    def getLast(self) -> float:
        return self._queue[-1]

    def sigma_delta(self) -> Optional[float]:
        if len(self._queue) == self._length:
            return (self.__value - self.__sma) / stdev(self._queue)
        else:
            return None

    def stdev(self) -> Optional[float]:
        if len(self._queue) == self._length:
            return stdev(self._queue)
        else:
            return None

    def hurst(self) -> Optional[float]:
        if len(self._queue) == self._length:
            hurst = Hurst()
            hurst_value = hurst.hurst(list(self._queue))
            return hurst_value
        else:
            return None

    def latest(self, history: QuerySet[HistoricData]) -> dict:
        if history.count() > self._length:
            data = dict()
            r_history = list()
            for entry in reversed(history):
                close = float(entry.close)
                self.add(close)
                r_history.append(close)
            data["sma"] = self.__sma
            data["sd"] = self.sigma_delta()
            data["length"] = self._length
            data["delta"] = 100 * (r_history[-1] - self.__sma) / self.__sma
            hurst = Hurst()
            data["hurst"] = hurst.hurst(r_history)
            return data
        else:
            raise ValueError("History size not sufficient.")


class BollingerBands:
    def __init__(self, window_size=20, std=2):
        self.__length = window_size
        self.__std = std
        self.__ma = SMA(window_size)

    def add(self, value: float) -> Optional[Tuple[float, float]]:
        current_ma = self.__ma.add(value)
        current_stdev = self.__ma.stdev()
        if current_stdev is not None:
            upper_limit = current_ma + current_stdev * self.__std
            lower_limit = current_ma - current_stdev * self.__std
            return (lower_limit, upper_limit)
        else:
            return None


class MACD:
    def __init__(self, fast_period=12, slow_period=26, signal_period=9):
        self.__fast_period = fast_period
        self.__slow_period = slow_period
        self.__signal_period = signal_period
        
        self.__fast_ma = EMA(fast_period)
        self.__slow_ma = EMA(slow_period)
        self.__macd_ma = EMA(signal_period)

    def add(self, value: float) -> Optional[Tuple[float, float, float, float]]:
        """
        returning a tupel with macd line, signal line and histogram
        Note: all values are normalized
        """
        current_fast_ma = self.__fast_ma.add(value)
        current_slow_ma = self.__slow_ma.add(value)

        if current_slow_ma is not None:
            macd_line = 100 * (current_fast_ma - current_slow_ma) / value
            signal_line = self.__macd_ma.add(macd_line)

            if signal_line is not None:
                # normalize also the signal line
                histogram = macd_line - signal_line
                return (macd_line, signal_line, histogram)

        else:
            return None


class RSI:
    def __init__(self, period=14):
        self.__previous = None
        self.__gain_sma = SMA(period)
        self.__loss_sma = SMA(period)

    def add(self, value: float) -> Optional[float]:
        
        if self.__previous is None:
            self.__previous = value
            return None
        else:
            # Calculate price change and gain/loss
            delta = value - self.__previous
            gain = max(0, delta)
            loss = max(0, -delta)

            # Calculate average gain and loss
            avg_gain = self.__gain_sma.add(gain)
            avg_loss = self.__loss_sma.add(loss)

            self.__previous = value

            if avg_gain != 0 and avg_loss != 0:
                return 100 - (100 / (1 + (avg_gain / avg_loss)))
            else:
                return None


class Momentum:
    """
    typical length is 14 or 30
    """
    def __init__(self, length=14):
        # ma length
        self._length = length
        self._queue: deque = deque(maxlen=length)

    def add(self, value: float) -> float:
        """
        returns the current ema for the given value if a valid ema does exist, else None
        """

        self._queue.appendleft(value)

        # once we have enough data, we can start calculating the momentum
        if len(self._queue) == self._length:
            # taking the difference of the first element and the last
            return self._queue[-1] - self._queue[0]
        else:
            return None
        

class Ichimoku:

    def __init__(self, 
                 kijun_lookback  = 26, 
                 tenkan_lookback =  9, 
                 chikou_lookback = 26, 
                 senkou_span_b_lookback = 52):
        
        self.__tenkan_length = tenkan_lookback
        self.__kijun_length = kijun_lookback
        self.__senko_span_length = senkou_span_b_lookback
        
        self.tenkan_sen_highs = SMA(self.__tenkan_length)
        self.tenkan_sen_lows = SMA(self.__tenkan_length)

        self.kijun_sen_highs = SMA(self.__kijun_length)
        self.kijun_sen_lows = SMA(self.__kijun_length)

        self.chikous = SMA(chikou_lookback)
        self.chikous_span_1s = SMA(chikou_lookback)
        self.chikous_span_2s = SMA(chikou_lookback)

        self.senko_span_highs = SMA(self.__senko_span_length)
        self.senko_span_lows = SMA(self.__senko_span_length)

        self.senko_a_history = list()
        self.senko_b_history = list()

        self.__latest = None

    def add(self, high, low, close) -> Optional[dict]:
        """
        returns the current ichimoku values: tenkan, kijun, senkos (cumo), chikou and future senkos, so the furture cloud
        """

        self.tenkan_sen_highs.add(high)
        self.kijun_sen_highs.add(high)
        self.senko_span_highs.add(high)

        self.tenkan_sen_lows.add(low)
        self.kijun_sen_lows.add(low)
        self.senko_span_lows.add(low)

        self.chikous.add(close)

        if (self.tenkan_sen_highs.getN() == self.__tenkan_length and self.kijun_sen_highs.getN() == self.__kijun_length):
            tenkan_sen = (self.tenkan_sen_highs.getMax() + self.tenkan_sen_lows.getMin()) / 2
            kijun_sen = (self.kijun_sen_highs.getMax() + self.kijun_sen_lows.getMin()) / 2

            senko = (tenkan_sen + kijun_sen) / 2
            self.senko_a_history.append(senko)

        if self.senko_span_highs.getN() == self.__senko_span_length:
            senko_span = (self.senko_span_highs.getMax() + self.senko_span_lows.getMin()) / 2
            self.senko_b_history.append(senko_span)

        if len(self.senko_a_history) > self.__kijun_length + self.__senko_span_length:

            senko_span_1 = self.senko_a_history[-1 - self.__kijun_length]
            senko_span_2 = self.senko_b_history[-1 - self.__kijun_length]

            self.chikous_span_1s.add(senko_span_1)
            self.chikous_span_2s.add(senko_span_2)

            self.__latest = {"tenkan_sen": tenkan_sen,
                    "kijun_sen": kijun_sen,
                    # kumo boundaries
                    "senko_span_1_current": senko_span_1,
                    "senko_span_2_current": senko_span_2,
                    # behind
                    "close_at_chikou": self.chikous.getLast(),
                    # the kumo at chikou position
                    "chikou_span_1": self.chikous_span_1s.getLast(),
                    "chikou_span_2": self.chikous_span_2s.getLast(),
                    # up front (future kumo)
                    "senko_span_1_future": self.senko_a_history[-1],
                    "senko_span_2_future": self.senko_b_history[-1]
                    }
            
            return self.__latest
    
    def current_value(self) -> Optional[dict]:
        return self.__latest
        
    def latest(self, history: QuerySet[HistoricData]) -> dict:
        if history.count() > self.__senko_span_length:
            for entry in reversed(history):
                current_ikh = self.add(float(entry.high_price), float(entry.low), float(entry.close))
            return {"ikh": current_ikh}
        else:
            raise ValueError("History size not sufficient.")


def evaluate_ikh(close:float, ikh:dict ) -> int:

    evaluation_value = 0

    # is close above the cloud
    if close > ikh["senko_span_1_current"] and close > ikh["senko_span_2_current"]:
         evaluation_value += 1
    # is the close below the cloud
    elif close < ikh["senko_span_1_current"] and close < ikh["senko_span_2_current"]:
         evaluation_value -= 1

    # current cumo(cloud) red or green
    if ikh["senko_span_1_current"] >= ikh["senko_span_2_current"]:
        evaluation_value += 1
    else:
        evaluation_value -= 1

    # check kijun
    if close > ikh["kijun_sen"]:
        evaluation_value += 1
    else:
        evaluation_value -= 1

    # check tenkan relative to kijun
    if ikh["tenkan_sen"] > ikh["kijun_sen"]:
        evaluation_value += 1
    else:
        evaluation_value -= 1

    # check chikou
    if close > ikh["close_at_chikou"]:
        evaluation_value += 1
        if close > ikh["chikou_span_1"] and close > ikh["chikou_span_2"]:
            evaluation_value += 1
    elif close < ikh["close_at_chikou"]:
        evaluation_value -= 1
        if close < ikh["chikou_span_1"] and close < ikh["chikou_span_2"]:
            evaluation_value -= 1

    return evaluation_value


class Hurst:
    def hurst(self, input_ts, lags_to_test=[2, 20]):
        # interpretation of return vale
        # hurst < 0.5 - input_ts is mean reverting
        # hurst = 0.5 - input_ts is effectively random/geometric brownian motion
        # hurst > 0.5 - input_ts is trending

        tau = []
        lagvec = []
        # Step through the different lags
        for lag in range(lags_to_test[0], lags_to_test[1]):
            # produce time series difference with lag
            pp = np.subtract(input_ts[lag:], input_ts[:-lag])
            # Write the different lags into a vector
            lagvec.append(lag)
            # Calculate the variance of the difference vector
            tau.append(np.std(pp))
        # linear fit to double-log graph (gives power)
        m = np.polyfit(np.log10(lagvec), np.log10(tau), 1)
        # hurst exponent is the slope of the line of best fit
        hurst = m[0]
        return hurst

from data.history_dao import History_DAO_Factory
from data.helper import humanize_price

def hl_watchlist(security:Security) -> dict:

    watchlist_entry = dict()

    watchlist_entry["security"] = security
    history = security.daily_data.all()[:200]
    
    if security.data_provider.name == "Yahoo":
        dao = History_DAO_Factory().get_online_dao(security.data_provider)
        watchlist_entry["price"] = humanize_price(dao.lookupPrice(security.symbol))
        try:
            watchlist_entry["pe_forward"] = dao.lookup_summary_detail(security)[
                "forwardPE"
            ]["raw"]
        except KeyError:
            watchlist_entry["pe_forward"] = float("nan")
    else:
        
        price = dict()
        price["change_percent"] = (
            100 * (history[0].close - history[1].close) / history[1].close
        )
        price["price"] = history[0].close
        price["change"] = history[0].close - history[1].close

        price["timestamp"] = history[0].date
        watchlist_entry["price"] = price


    # create our SMA and Ichimokou instances
    ikh = Ichimoku()
    sma = SMA(50)

    # loop over the history
    for h in reversed(history):
        close = float(h.close)
        ikh.add(high=float(h.high_price), low=float(h.low), close=close)
        sma.add(close)
    
    # update the watchlist_entry
    watchlist_entry["ikh_evaluation"] = evaluate_ikh(close, ikh.current_value())
    watchlist_entry["sma"] = {
        "hurst": sma.hurst(), 
        "sd": sma.sigma_delta(),
        "delta": 100 * (close - sma.current_value()) / sma.current_value()
        }   
    
    return watchlist_entry

