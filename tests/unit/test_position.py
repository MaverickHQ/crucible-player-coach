from player_coach.portfolio.position import Position

FIXTURE = Position(
    position_id="pos-001",
    symbol="AMZN",
    direction="long",
    entry_price=185.00,
    quantity=10.0,
    size_pct=0.05,
    stop_loss=180.00,
    take_profit=195.00,
    opened_at="2026-05-10T09:30:00+00:00",
    unrealized_pnl=50.0,
)


def test_to_dict_from_dict_round_trip():
    assert Position.from_dict(FIXTURE.to_dict()) == FIXTURE


def test_is_stop_hit_true_when_price_at_or_below_stop():
    assert FIXTURE.is_stop_hit(180.00) is True
    assert FIXTURE.is_stop_hit(179.99) is True


def test_is_stop_hit_false_above_stop():
    assert FIXTURE.is_stop_hit(180.01) is False


def test_is_target_hit_true_when_price_at_or_above_take_profit():
    assert FIXTURE.is_target_hit(195.00) is True
    assert FIXTURE.is_target_hit(196.00) is True


def test_is_target_hit_false_below_take_profit():
    assert FIXTURE.is_target_hit(194.99) is False


def test_current_value_returns_quantity_times_price():
    assert FIXTURE.current_value(190.00) == 1900.00


def test_short_position_stop_and_target_inverted():
    short = Position(
        position_id="pos-002",
        symbol="AMZN",
        direction="short",
        entry_price=185.00,
        quantity=10.0,
        size_pct=0.05,
        stop_loss=190.00,
        take_profit=175.00,
        opened_at="2026-05-10T09:30:00+00:00",
    )
    assert short.is_stop_hit(190.00) is True
    assert short.is_stop_hit(189.99) is False
    assert short.is_target_hit(175.00) is True
    assert short.is_target_hit(175.01) is False
