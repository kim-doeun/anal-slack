import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analslack import db


def test_get_sales_forecast_returns_none_when_never_uploaded():
    conn = db.connect(":memory:")
    assert db.get_sales_forecast(conn) is None


def test_replace_and_get_round_trip():
    conn = db.connect(":memory:")
    db.replace_sales_forecast(
        conn,
        "forecast.xlsx",
        ["사업명", "금액"],
        [["A", 100], ["B", 200]],
    )
    conn.commit()

    forecast = db.get_sales_forecast(conn)
    assert forecast.filename == "forecast.xlsx"
    assert forecast.columns == ["사업명", "금액"]
    assert forecast.rows == [["A", 100], ["B", 200]]


def test_replace_fully_overwrites_previous_upload():
    conn = db.connect(":memory:")
    db.replace_sales_forecast(conn, "old.xlsx", ["a"], [["1"], ["2"], ["3"]])
    conn.commit()

    db.replace_sales_forecast(conn, "new.xlsx", ["x", "y"], [["p", "q"]])
    conn.commit()

    forecast = db.get_sales_forecast(conn)
    assert forecast.filename == "new.xlsx"
    assert forecast.columns == ["x", "y"]
    assert forecast.rows == [["p", "q"]]


def test_row_order_is_preserved():
    conn = db.connect(":memory:")
    rows = [[str(i)] for i in range(20)]
    db.replace_sales_forecast(conn, "f.xlsx", ["n"], rows)
    conn.commit()

    forecast = db.get_sales_forecast(conn)
    assert forecast.rows == rows


def test_empty_rows_list_is_valid():
    conn = db.connect(":memory:")
    db.replace_sales_forecast(conn, "empty.xlsx", ["사업명"], [])
    conn.commit()

    forecast = db.get_sales_forecast(conn)
    assert forecast.columns == ["사업명"]
    assert forecast.rows == []
