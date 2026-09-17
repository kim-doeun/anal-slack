import io
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openpyxl import Workbook

from analslack import db
from analslack.config import Config
from analslack.web import create_app

TZ = ZoneInfo("Asia/Seoul")


def _make_xlsx_bytes(rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_client(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.connect(db_path).close()
    cfg = Config(slack_bot_token=None, channel="test", db_path=db_path, timezone=TZ)
    app = create_app(cfg)
    app.testing = True
    return app.test_client(), db_path


def test_forecast_page_empty_state(tmp_path):
    client, _ = _make_client(tmp_path)
    resp = client.get("/forecast")
    assert resp.status_code == 200
    assert "아직 업로드된 세일즈포케스트가 없습니다" in resp.get_data(as_text=True)


def test_upload_valid_xlsx_shows_table(tmp_path):
    client, db_path = _make_client(tmp_path)
    xlsx_bytes = _make_xlsx_bytes(
        [
            ["사업명", "고객사", "예상금액"],
            ["ERP고도화", "삼성전자", 100000000],
        ]
    )

    resp = client.post(
        "/forecast/upload",
        data={"file": (io.BytesIO(xlsx_bytes), "forecast.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "ERP고도화" in body
    assert "삼성전자" in body
    assert "100000000" in body
    assert "forecast.xlsx" in body

    forecast = db.get_sales_forecast(db.connect(db_path))
    assert forecast.columns == ["사업명", "고객사", "예상금액"]


def test_upload_replaces_previous_data(tmp_path):
    client, db_path = _make_client(tmp_path)
    first = _make_xlsx_bytes([["a"], ["1"], ["2"]])
    second = _make_xlsx_bytes([["b", "c"], ["x", "y"]])

    client.post(
        "/forecast/upload",
        data={"file": (io.BytesIO(first), "first.xlsx")},
        content_type="multipart/form-data",
    )
    client.post(
        "/forecast/upload",
        data={"file": (io.BytesIO(second), "second.xlsx")},
        content_type="multipart/form-data",
    )

    forecast = db.get_sales_forecast(db.connect(db_path))
    assert forecast.filename == "second.xlsx"
    assert forecast.columns == ["b", "c"]
    assert forecast.rows == [["x", "y"]]


def test_upload_rejects_non_xlsx_extension(tmp_path):
    client, db_path = _make_client(tmp_path)
    resp = client.post(
        "/forecast/upload",
        data={"file": (io.BytesIO(b"not excel"), "data.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "xlsx 형식" in resp.get_data(as_text=True)
    assert db.get_sales_forecast(db.connect(db_path)) is None


def test_upload_rejects_corrupt_xlsx(tmp_path):
    client, db_path = _make_client(tmp_path)
    resp = client.post(
        "/forecast/upload",
        data={"file": (io.BytesIO(b"not a real xlsx file"), "forecast.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "엑셀 파일을 읽을 수 없습니다" in resp.get_data(as_text=True)
    assert db.get_sales_forecast(db.connect(db_path)) is None


def test_upload_without_file_shows_error(tmp_path):
    client, _ = _make_client(tmp_path)
    resp = client.post(
        "/forecast/upload",
        data={},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "파일을 선택해주세요" in resp.get_data(as_text=True)


def test_numeric_column_gets_number_sort_type(tmp_path):
    client, db_path = _make_client(tmp_path)
    xlsx_bytes = _make_xlsx_bytes(
        [
            ["사업명", "금액"],
            ["A", 100],
            ["B", 200],
        ]
    )
    client.post(
        "/forecast/upload",
        data={"file": (io.BytesIO(xlsx_bytes), "f.xlsx")},
        content_type="multipart/form-data",
    )

    resp = client.get("/forecast")
    body = resp.get_data(as_text=True)
    thead = body.split("<thead>", 1)[1].split("</thead>", 1)[0]
    assert 'data-sort="text">사업명' in thead
    assert 'data-sort="number">금액' in thead


def test_forecast_table_has_scroll_container(tmp_path):
    client, db_path = _make_client(tmp_path)
    xlsx_bytes = _make_xlsx_bytes([["a"], ["1"]])
    client.post(
        "/forecast/upload",
        data={"file": (io.BytesIO(xlsx_bytes), "f.xlsx")},
        content_type="multipart/form-data",
    )

    resp = client.get("/forecast")
    body = resp.get_data(as_text=True)
    assert 'class="grid-scroll"' in body
    assert 'class="grid-table" data-sortable' in body
