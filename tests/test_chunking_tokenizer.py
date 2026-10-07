import pytest

from app.chunking.tokenizer import SimpleTokenCounter, TokenCounter


def test_simple_token_counter_counts_whitespace_tokens() -> None:
    counter = SimpleTokenCounter()

    assert counter.count("Hello world") == 2


def test_simple_token_counter_handles_multiple_spaces() -> None:
    counter = SimpleTokenCounter()

    assert counter.count("Hello   world   DocPilot") == 3


def test_simple_token_counter_handles_empty_text() -> None:
    counter = SimpleTokenCounter()

    assert counter.count("") == 0


def test_simple_token_counter_is_token_counter() -> None:
    counter = SimpleTokenCounter()

    assert isinstance(counter, TokenCounter)


def test_token_counter_requires_count_implementation() -> None:
    with pytest.raises(TypeError):
        TokenCounter()

def test_simple_token_counter_takes_last_tokens() -> None:
    counter = SimpleTokenCounter()

    assert counter.take_last(
        "one two three four five",
        2,
    ) == "four five"


def test_simple_token_counter_returns_empty_for_zero_tokens() -> None:
    counter = SimpleTokenCounter()

    assert counter.take_last(
        "one two three",
        0,
    ) == ""


def test_simple_token_counter_returns_all_when_count_is_larger() -> None:
    counter = SimpleTokenCounter()

    assert counter.take_last(
        "one two three",
        10,
    ) == "one two three"

def test_simple_token_counter_take_first() -> None:
    counter = SimpleTokenCounter()

    assert counter.take_first("one two three four", 2) == "one two"


def test_simple_token_counter_take_first_more_than_available() -> None:
    counter = SimpleTokenCounter()

    assert counter.take_first("one two three", 10) == "one two three"


def test_simple_token_counter_take_first_zero() -> None:
    counter = SimpleTokenCounter()

    assert counter.take_first("one two three", 0) == ""


def test_simple_token_counter_take_first_negative() -> None:
    counter = SimpleTokenCounter()

    assert counter.take_first("one two three", -1) == ""


def test_simple_token_counter_splits_text() -> None:
    counter = SimpleTokenCounter()

    assert counter.split(
        "one two three four five",
        2,
    ) == [
        "one two",
        "three four",
        "five",
    ]


def test_simple_token_counter_split_preserves_all_tokens() -> None:
    counter = SimpleTokenCounter()

    pieces = counter.split("one two three four five", 2)

    assert " ".join(pieces) == "one two three four five"


def test_simple_token_counter_split_rejects_non_positive_limit() -> None:
    counter = SimpleTokenCounter()

    try:
        counter.split("one two three", 0)
    except ValueError as exc:
        assert str(exc) == "max_tokens must be greater than 0"
    else:
        raise AssertionError("Expected ValueError")
