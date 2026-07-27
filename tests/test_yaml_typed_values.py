"""Tests for nb_wrangler/yaml_typed_values.py."""

from datetime import date, datetime

from nb_wrangler.yaml_typed_values import normalize_value


class TestNormalizeValueNone:
    def test_none_passthrough(self):
        assert normalize_value(None) is None


class TestBoolNormalization:
    def test_true_becomes_string(self):
        assert normalize_value(True) == "True"

    def test_false_becomes_string(self):
        assert normalize_value(False) == "False"


class TestDateNormalization:
    def test_date_isoformat(self):
        d = date(2026, 4, 13)
        assert normalize_value(d) == "2026-04-13"

    def test_datetime_isoformat(self):
        dt = datetime(2026, 5, 1, 12, 30, 0)
        assert normalize_value(dt) == "2026-05-01T12:30:00"


class TestIntFloatNormalization:
    def test_int_to_str(self):
        assert normalize_value(42) == "42"

    def test_float_to_str(self):
        assert normalize_value(3.12) == "3.12"


class TestStrPassthrough:
    def test_string_unchanged(self):
        assert normalize_value("hello") == "hello"


class TestDictMutation:
    def test_single_level_mutation(self):
        d = {"a": True, "b": 42}
        result = normalize_value(d)
        assert result is d  # mutates in place
        assert result["a"] == "True"
        assert result["b"] == "42"

    def test_nested_dict(self):
        d = {"outer": {"inner": True}}
        result = normalize_value(d)
        assert result["outer"]["inner"] == "True"


class TestListMutation:
    def test_simple_list(self):
        lst = [True, 3.12, "keep"]
        result = normalize_value(lst)
        assert result is lst
        assert result[0] == "True"
        assert result[1] == "3.12"
        assert result[2] == "keep"


class TestDeepNesting:
    def test_deeply_nested_mixed(self):
        d = {
            "a": [{"b": True}, {"c": date(2026, 1, 1)}],
            "d": 42,
        }
        result = normalize_value(d)
        assert result["a"][0]["b"] == "True"
        assert result["a"][1]["c"] == "2026-01-01"
        assert result["d"] == "42"

    def test_three_level_deep(self):
        d = {"l1": {"l2": {"l3": False}}}
        normalize_value(d)
        assert d["l1"]["l2"]["l3"] == "False"
