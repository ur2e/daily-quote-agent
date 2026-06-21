from infra.scheduler.lambda_function import _should_send_to_user


def test_should_send_to_active_user_on_weekday() -> None:
    item = {"email": "friend@example.com", "is_active": True}

    assert _should_send_to_user(item, is_weekend=False) is True


def test_should_not_send_to_inactive_user_on_weekday() -> None:
    item = {"email": "friend@example.com", "is_active": False}

    assert _should_send_to_user(item, is_weekend=False) is False


def test_should_send_on_weekend_only_when_enabled() -> None:
    weekend_user = {
        "email": "weekend@example.com",
        "is_active": True,
        "send_on_weekends": True,
    }
    weekday_only_user = {"email": "weekday@example.com", "is_active": True}

    assert _should_send_to_user(weekend_user, is_weekend=True) is True
    assert _should_send_to_user(weekday_only_user, is_weekend=True) is False
