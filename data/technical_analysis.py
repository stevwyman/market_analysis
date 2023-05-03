from typing import Optional, Tuple
from collections import deque
from statistics import mean, stdev
from data.models import HistoricData
from django.db.models.query import QuerySet

import numpy as np

class MovingAverage:

    def __init__(self, length: int):
        # ma length
        self._length = length

        self._value = 0.0
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

        self.__length = length
        self.__factor = float(2 / (1 + length))
        self.__ema = 0.0
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
    

    def sigma_delta(self) -> Optional[float]:

        if self.__ema_reached:
            return (self.__value - self.__ema) / stdev(self._queue)
        return None
    
 
class SMA(MovingAverage):
    def __init__(self, length: int):
        super().__init__(length)

        self.__length = length
        self.__sma = 0.0

    def add(self, value: float) -> float:
        """
        returns the current ema for the given value if a valid ema does exist, else None
        """

        self.__value = value
        self._queue.appendleft(self.__value)
        self.__sma = mean(self._queue)
        
        return self.__sma
    
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

        if history.count() > self.__length:
            data = {}
            r_history = list()
            for entry in reversed(history):
                self.add(float(entry.close))
                r_history.append(float(entry.close))
                # print(f"{entry.date} {entry.close}")
            data["sma"] = self.__sma
            data["sd"] = self.sigma_delta()
            data["length"] = self.__length
            hurst = Hurst()
            data["hurst"] = hurst.hurst(r_history)
            
            return data
        else: 
            raise ValueError("History size not sufficient.")


class BollingerBands():

    def __init__(self, window_size: int, std: int):
        
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


class Hurst():

    def hurst (self, input_ts, lags_to_test=[2,20]):
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