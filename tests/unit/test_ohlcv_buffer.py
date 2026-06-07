from __future__ import annotations

import math

from player_coach.market.ohlcv import OHLCVBuffer


def _append_closes(buf: OHLCVBuffer, closes: list[float]) -> None:
    for c in closes:
        buf.append(open=c, high=c * 1.01, low=c * 0.99, close=c, volume=1_000)


# ------------------------------------------------------------------ basics

def test_append_and_len():
    buf = OHLCVBuffer()
    _append_closes(buf, [100, 101, 102])
    assert len(buf) == 3


def test_closes_in_insertion_order():
    buf = OHLCVBuffer()
    _append_closes(buf, [100, 101, 102])
    assert list(buf.closes) == [100, 101, 102]


def test_ohlcv_columns_aligned():
    buf = OHLCVBuffer()
    buf.append(open=10, high=12, low=9, close=11, volume=500)
    assert buf.opens[-1] == 10
    assert buf.highs[-1] == 12
    assert buf.lows[-1] == 9
    assert buf.closes[-1] == 11
    assert buf.volumes[-1] == 500


# --------------------------------------------------------------- rolling window

def test_maxlen_evicts_oldest():
    buf = OHLCVBuffer(maxlen=2)
    _append_closes(buf, [100, 101, 102])
    assert len(buf) == 2
    assert list(buf.closes) == [101, 102]


# ------------------------------------------------------------- log returns

def test_log_returns_from_closes():
    buf = OHLCVBuffer()
    _append_closes(buf, [100, 110, 121])
    r = buf.log_returns()
    assert len(r) == 2
    assert math.isclose(r[0], math.log(1.1), rel_tol=1e-9)


def test_empty_buffer_yields_empty_arrays():
    buf = OHLCVBuffer()
    assert len(buf.closes) == 0
    assert len(buf.log_returns()) == 0


# ----------------------------------------------------- column caching (#10)

def test_column_accessor_is_cached_between_appends():
    buf = OHLCVBuffer()
    _append_closes(buf, [100, 101, 102])
    assert buf.closes is buf.closes  # same array object — not rebuilt each access


def test_log_returns_is_cached_between_appends():
    buf = OHLCVBuffer()
    _append_closes(buf, [100, 110, 121])
    assert buf.log_returns() is buf.log_returns()


def test_append_invalidates_cache():
    buf = OHLCVBuffer()
    _append_closes(buf, [100, 101])
    first = buf.closes
    _append_closes(buf, [102])
    assert buf.closes is not first
    assert list(buf.closes) == [100, 101, 102]
