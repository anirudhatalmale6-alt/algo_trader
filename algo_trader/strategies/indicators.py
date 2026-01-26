"""
Technical Indicators Library
Implements common indicators used in Pine Script
"""
import numpy as np
import pandas as pd
from typing import Union, List
from loguru import logger


class Indicators:
    """
    Technical indicators implementation compatible with Pine Script functions
    All functions work with pandas Series or numpy arrays
    """

    @staticmethod
    def sma(source: pd.Series, length: int) -> pd.Series:
        """Simple Moving Average - ta.sma()"""
        return source.rolling(window=length).mean()

    @staticmethod
    def ema(source: pd.Series, length: int) -> pd.Series:
        """Exponential Moving Average - ta.ema()"""
        return source.ewm(span=length, adjust=False).mean()

    @staticmethod
    def wma(source: pd.Series, length: int) -> pd.Series:
        """Weighted Moving Average - ta.wma()"""
        weights = np.arange(1, length + 1)
        return source.rolling(window=length).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )

    @staticmethod
    def vwma(source: pd.Series, volume: pd.Series, length: int) -> pd.Series:
        """Volume Weighted Moving Average - ta.vwma()"""
        return (source * volume).rolling(window=length).sum() / volume.rolling(window=length).sum()

    @staticmethod
    def rma(source: pd.Series, length: int) -> pd.Series:
        """Running Moving Average (Wilder's smoothing) - ta.rma()"""
        alpha = 1 / length
        return source.ewm(alpha=alpha, adjust=False).mean()

    @staticmethod
    def rsi(source: pd.Series, length: int = 14) -> pd.Series:
        """Relative Strength Index - ta.rsi()"""
        delta = source.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(source: pd.Series, fast_length: int = 12, slow_length: int = 26,
             signal_length: int = 9) -> tuple:
        """MACD - ta.macd()"""
        fast_ema = Indicators.ema(source, fast_length)
        slow_ema = Indicators.ema(source, slow_length)
        macd_line = fast_ema - slow_ema
        signal_line = Indicators.ema(macd_line, signal_length)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def bollinger_bands(source: pd.Series, length: int = 20, mult: float = 2.0) -> tuple:
        """Bollinger Bands - ta.bb()"""
        basis = Indicators.sma(source, length)
        dev = mult * source.rolling(window=length).std()
        upper = basis + dev
        lower = basis - dev
        return upper, basis, lower

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
        """Average True Range - ta.atr()"""
        tr = Indicators.tr(high, low, close)
        return Indicators.rma(tr, length)

    @staticmethod
    def tr(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """True Range - ta.tr()"""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    @staticmethod
    def stoch(high: pd.Series, low: pd.Series, close: pd.Series,
              k_length: int = 14, k_smooth: int = 1, d_smooth: int = 3) -> tuple:
        """Stochastic Oscillator - ta.stoch()"""
        lowest_low = low.rolling(window=k_length).min()
        highest_high = high.rolling(window=k_length).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        k = Indicators.sma(k, k_smooth)
        d = Indicators.sma(k, d_smooth)
        return k, d

    @staticmethod
    def cci(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 20) -> pd.Series:
        """Commodity Channel Index - ta.cci()"""
        tp = (high + low + close) / 3
        sma_tp = Indicators.sma(tp, length)
        mad = tp.rolling(window=length).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
        return (tp - sma_tp) / (0.015 * mad)

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
        """Average Directional Index - ta.adx()"""
        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        tr = Indicators.tr(high, low, close)
        atr = Indicators.rma(tr, length)

        plus_di = 100 * Indicators.rma(plus_dm, length) / atr
        minus_di = 100 * Indicators.rma(minus_dm, length) / atr

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return Indicators.rma(dx, length)

    @staticmethod
    def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
                   length: int = 10, mult: float = 3.0) -> tuple:
        """SuperTrend Indicator"""
        hl2 = (high + low) / 2
        atr = Indicators.atr(high, low, close, length)

        upper_band = hl2 + (mult * atr)
        lower_band = hl2 - (mult * atr)

        supertrend = pd.Series(index=close.index, dtype=float)
        direction = pd.Series(index=close.index, dtype=int)

        for i in range(1, len(close)):
            if close.iloc[i] > upper_band.iloc[i-1]:
                direction.iloc[i] = 1
            elif close.iloc[i] < lower_band.iloc[i-1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i-1]

            if direction.iloc[i] == 1:
                supertrend.iloc[i] = lower_band.iloc[i]
            else:
                supertrend.iloc[i] = upper_band.iloc[i]

        return supertrend, direction

    @staticmethod
    def pivot_points(high: pd.Series, low: pd.Series, close: pd.Series) -> dict:
        """Pivot Points"""
        pp = (high + low + close) / 3
        r1 = 2 * pp - low
        s1 = 2 * pp - high
        r2 = pp + (high - low)
        s2 = pp - (high - low)
        r3 = high + 2 * (pp - low)
        s3 = low - 2 * (high - pp)
        return {'pp': pp, 'r1': r1, 'r2': r2, 'r3': r3, 's1': s1, 's2': s2, 's3': s3}

    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Volume Weighted Average Price - ta.vwap()"""
        tp = (high + low + close) / 3
        return (tp * volume).cumsum() / volume.cumsum()

    @staticmethod
    def highest(source: pd.Series, length: int) -> pd.Series:
        """Highest value over period - ta.highest()"""
        return source.rolling(window=length).max()

    @staticmethod
    def lowest(source: pd.Series, length: int) -> pd.Series:
        """Lowest value over period - ta.lowest()"""
        return source.rolling(window=length).min()

    @staticmethod
    def crossover(series1: pd.Series, series2: pd.Series) -> pd.Series:
        """Crossover - ta.crossover()"""
        return (series1 > series2) & (series1.shift(1) <= series2.shift(1))

    @staticmethod
    def crossunder(series1: pd.Series, series2: pd.Series) -> pd.Series:
        """Crossunder - ta.crossunder()"""
        return (series1 < series2) & (series1.shift(1) >= series2.shift(1))

    @staticmethod
    def change(source: pd.Series, length: int = 1) -> pd.Series:
        """Change - ta.change()"""
        return source.diff(length)

    @staticmethod
    def mom(source: pd.Series, length: int = 10) -> pd.Series:
        """Momentum - ta.mom()"""
        return source.diff(length)

    @staticmethod
    def roc(source: pd.Series, length: int = 10) -> pd.Series:
        """Rate of Change - ta.roc()"""
        return 100 * (source - source.shift(length)) / source.shift(length)

    @staticmethod
    def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
        """Williams %R"""
        highest_high = Indicators.highest(high, length)
        lowest_low = Indicators.lowest(low, length)
        return -100 * (highest_high - close) / (highest_high - lowest_low)

    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """On Balance Volume - ta.obv()"""
        sign = np.sign(close.diff())
        return (sign * volume).cumsum()

    @staticmethod
    def mfi(high: pd.Series, low: pd.Series, close: pd.Series,
            volume: pd.Series, length: int = 14) -> pd.Series:
        """Money Flow Index - ta.mfi()"""
        tp = (high + low + close) / 3
        mf = tp * volume
        mf_pos = mf.where(tp > tp.shift(1), 0).rolling(window=length).sum()
        mf_neg = mf.where(tp < tp.shift(1), 0).rolling(window=length).sum()
        return 100 - (100 / (1 + mf_pos / mf_neg))

    @staticmethod
    def ichimoku(high: pd.Series, low: pd.Series, tenkan: int = 9,
                 kijun: int = 26, senkou: int = 52) -> dict:
        """Ichimoku Cloud"""
        tenkan_sen = (Indicators.highest(high, tenkan) + Indicators.lowest(low, tenkan)) / 2
        kijun_sen = (Indicators.highest(high, kijun) + Indicators.lowest(low, kijun)) / 2
        senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun)
        senkou_b = ((Indicators.highest(high, senkou) + Indicators.lowest(low, senkou)) / 2).shift(kijun)
        return {
            'tenkan_sen': tenkan_sen,
            'kijun_sen': kijun_sen,
            'senkou_a': senkou_a,
            'senkou_b': senkou_b
        }
