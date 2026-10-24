from app.monitors.compare import describe, diff, is_terminal_status


def test_first_run_has_no_changes():
    assert diff(None, {"status": "Initiated"}) == []


def test_terminal_status_detection():
    assert is_terminal_status({"status": "Credited"}) is True
    assert is_terminal_status({"status": "Dispatched via Speed Post"}) is True
    assert is_terminal_status({"status": "Refund Completed"}) is True
    assert is_terminal_status({"status": "Initiated"}) is False
    assert is_terminal_status({"status": "Under Review"}) is False
    assert is_terminal_status(None) is False


def test_detects_changed_field():
    assert diff({"status": "Initiated", "amount": 8420}, {"status": "Credited", "amount": 8420}) == [
        {"field": "status", "old": "Initiated", "new": "Credited"}
    ]


def test_ignores_case_and_whitespace_noise():
    assert diff({"status": "Under  Review"}, {"status": " under review "}) == []


def test_new_and_removed_fields_count_as_changes():
    out = diff({"a": 1}, {"b": 2})
    assert {c["field"] for c in out} == {"a", "b"}


def test_describe_mentions_url_and_values():
    msg = describe({"url": "https://x.com"}, [{"field": "status", "old": "A", "new": "B"}])
    assert "https://x.com" in msg and "A → B" in msg
