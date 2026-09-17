import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openpyxl import Workbook

from analslack.forecast import ForecastParseError, parse_excel


def _make_xlsx(rows) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_parse_basic_table():
    xlsx = _make_xlsx(
        [
            ["사업명", "고객사", "예상금액", "단계"],
            ["ERP고도화", "삼성전자", 100000000, "제안"],
            ["AI챗봇", "LG전자", 50000000, "협상"],
        ]
    )
    columns, rows = parse_excel(xlsx)
    assert columns == ["사업명", "고객사", "예상금액", "단계"]
    assert rows == [
        ["ERP고도화", "삼성전자", 100000000, "제안"],
        ["AI챗봇", "LG전자", 50000000, "협상"],
    ]


def test_parse_skips_fully_empty_rows():
    xlsx = _make_xlsx(
        [
            ["사업명", "금액"],
            ["A", 1],
            [None, None],
            ["B", 2],
        ]
    )
    columns, rows = parse_excel(xlsx)
    assert rows == [["A", 1], ["B", 2]]


def test_parse_pads_short_rows():
    xlsx = _make_xlsx(
        [
            ["사업명", "고객사", "금액"],
            ["A", "삼성전자"],  # 금액 열 누락
        ]
    )
    columns, rows = parse_excel(xlsx)
    assert rows == [["A", "삼성전자", None]]


def test_parse_fills_blank_header_cells():
    xlsx = _make_xlsx(
        [
            ["사업명", None, "금액"],
            ["A", "x", 1],
        ]
    )
    columns, rows = parse_excel(xlsx)
    assert columns == ["사업명", "열2", "금액"]


def test_parse_empty_workbook_raises():
    xlsx = _make_xlsx([])
    try:
        parse_excel(xlsx)
        assert False, "빈 워크북은 ForecastParseError를 던져야 한다"
    except ForecastParseError:
        pass


def test_parse_invalid_file_raises():
    bad = io.BytesIO(b"this is not an excel file")
    try:
        parse_excel(bad)
        assert False, "엑셀이 아닌 파일은 ForecastParseError를 던져야 한다"
    except ForecastParseError:
        pass


def test_parse_converts_date_only_cell_to_plain_date_string():
    import datetime

    xlsx = _make_xlsx(
        [
            ["사업명", "마감일"],
            ["A", datetime.date(2026, 3, 1)],
        ]
    )
    columns, rows = parse_excel(xlsx)
    # openpyxl은 순수 날짜 셀도 datetime으로 돌려주지만(자정 시각 포함),
    # 화면에는 시각 없이 날짜만 남기는 게 자연스럽다.
    assert rows[0][1] == "2026-03-01"


def test_parse_converts_datetime_with_time_to_readable_string():
    import datetime

    xlsx = _make_xlsx(
        [
            ["사업명", "최근업데이트"],
            ["A", datetime.datetime(2026, 3, 1, 14, 30, 0)],
        ]
    )
    columns, rows = parse_excel(xlsx)
    assert rows[0][1] == "2026-03-01 14:30:00"
