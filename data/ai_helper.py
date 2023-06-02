from data.technical_analysis import EMA, SMA, BollingerBands, MACD, RSI

import pandas as pd

from logging import getLogger

logger = getLogger(__name__)

def generate(securities) -> list():
    """
    generates a list of parameter values for input to category models
    we will generate output as strings in the form of
        -> under/above, oversold/overbought, rising falling
    """

    rows = list()

    for security in securities:
        if security.type != "EQUITY":
            logger.debug(f"skipping {security} as not an equity")
            continue
        else:
            history = security.daily_data.order_by("date").all()
            logger.info(f"processing {security} with {history.count()} entries in history")
            
            # define the list of features
            sma50 = SMA(50)         # mid term sma: rel. slope, delta, hurst and sigma delta
            ema20 = EMA(20)         # short term ema: rel. slope, delta
            macd = MACD()           # not sure if we want to use the MACD, requires a lot of regularisation
            rsi = RSI()             # using a simple momentum indicator
            bb = BollingerBands()   # bollinger bands

            previous_sma50 = 0
            previous_ema20 = 0
            previous_rsi = 0

            index = 0
            FORWARD_LABEL_SIZE = 3

            # list to store the historic values
            macd_line_list = list()
            macd_signal_list = list()
            macd_histogram_list = list()

            # loop through history
            for entry in history:

                # the disctionary holding the different values
                row = {}

                # the close as input for all the indicators
                close = float(entry.close)
                # logger.debug(f"processing {entry.date} with close at {__close}")
                
                # keep those three as reference
                row["time"] = str(entry.date)
                row["close"] = close
                row["symbol"] = security.symbol

                # this will be our label
                try:
                    next_close = float(history[index + FORWARD_LABEL_SIZE].close)
                except:
                    continue

                # building the label, using the forward percent as category 
                __change_forward_percent = 100 * (next_close - close) / close

                if __change_forward_percent > 5:
                    row["change_forward"] = 4
                elif __change_forward_percent > 2:
                    row["change_forward"] = 3
                elif __change_forward_percent < -5:
                    row["change_forward"] = 0
                elif __change_forward_percent < -2:
                    row["change_forward"] = 1
                else: 
                    row["change_forward"] = 2
                
                index += 1

                # now we work on the features
                # macd -> 3 values
                macd_value = macd.add(close)
                if macd_value is not None:
                    row["macd_line"] = macd_value[0]
                    row["macd_signal"] = macd_value[1]
                    row["macd_histogram"] = macd_value[2]

                # ema20 -> 3
                ema20_value = ema20.add(close)
                if previous_ema20 != 0:
                    if ema20_value is not None and previous_ema20 is not None:
                        # just as a reference
                        row["ema20"] = ema20_value
                        # we will use those as features
                        ema20_delta_percent = 100 * (close - ema20_value) / ema20_value
                        row["ema20_delta"] = ema20_delta_percent
                        row["ema20_slope"] = (ema20_value - previous_ema20) / previous_ema20

                previous_ema20 = ema20_value

                # sma50 -> 5
                sma50_value = sma50.add(close)
                if previous_sma50 != 0:
                    if sma50_value is not None and previous_sma50 is not None:
                        sma50_sd = sma50.sigma_delta()
                        sma50_hurst = sma50.hurst()
                        if (
                            sma50_value is not None
                            and sma50_sd is not None
                            and sma50_hurst is not None
                        ):
                            # reference
                            row["sma50_value"] = sma50_value
                            # features
                            row["sd50_value"] = sma50_sd
                            row["hurst"] = sma50_hurst
                            row["sma50_delta"] = 100 * (close - sma50_value) / sma50_value
                            row["sma50_slope"] = (sma50_value - previous_sma50) / previous_sma50

                previous_sma50 = sma50_value

                # rsi -> 2
                rsi_value = rsi.add(close)
                if previous_rsi != 0:
                    if rsi_value is not None and previous_rsi is not None:
                        row["rsi_value"] = rsi_value
                        row["rsi_slope"] = (rsi_value - previous_rsi) / previous_rsi

                previous_rsi = rsi_value

                # bollinger bands -> 1
                bb_value = bb.add(close)
                if bb_value is not None:
                    bb_center = (bb_value[0] + bb_value[1])/2
                    bb_position_rel = close - bb_center
                    try:
                        if bb_position_rel >= 0: # we are in the upper band
                            row["bband"] = 100 * bb_position_rel / (bb_value[1] - bb_center)
                        else:
                            row["bband"] = -100 * bb_position_rel / (bb_value[0] - bb_center)
                    except ZeroDivisionError:
                        row["bband"] = 0


                logger.debug(len(row))

                # only append complete rows
                if len(row) == 18:
                    logger.debug(f"... appending {row}")
                    rows.append(row)

    return pd.DataFrame(rows)