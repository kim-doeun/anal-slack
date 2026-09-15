import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analslack.charts import BarItem, _tick_fracs, bar_chart_svg, line_chart_svg


def test_tick_fracs_small_max_has_no_duplicate_labels():
    # 이전 버그: max_v=1일 때 5등분(0,0.25,0.5,0.75,1)을 반올림하면
    # 0,0,1,1,1처럼 라벨이 중복 표시됐다.
    fracs = _tick_fracs(1)
    labels = [round(1 * f) for f in fracs]
    assert labels == sorted(set(labels)) or len(labels) == len(set(labels))


def test_tick_fracs_zero_max_is_single_step():
    fracs = _tick_fracs(0)
    assert fracs == [0.0, 1.0]


def test_tick_fracs_large_max_uses_five_point_scale():
    assert _tick_fracs(100) == [0.0, 0.25, 0.5, 0.75, 1.0]


def test_line_chart_all_zero_values_no_duplicate_axis_labels():
    points = [(f"w{i}", 0) for i in range(12)]
    svg = line_chart_svg(points)
    labels = re.findall(r'class="chart-axis-label">(\d+)<', svg)
    # 왼쪽 y축 라벨만 추출 (앞쪽에 위치, x-axis 날짜 라벨은 숫자가 아님)
    y_labels = [l for l in labels if l.isdigit()]
    assert y_labels == sorted(set(y_labels), key=y_labels.index)


def test_line_chart_empty_points_does_not_crash():
    svg = line_chart_svg([])
    assert "<svg" in svg
    assert "데이터 없음" in svg


def test_line_chart_single_point_does_not_crash():
    svg = line_chart_svg([("w1", 5)])
    assert "<svg" in svg
    assert "chart-line" in svg


def test_bar_chart_basic_rendering():
    items = [
        BarItem(label="삼성전자-ERP고도화", value=3, href="/project/삼성전자/ERP고도화"),
        BarItem(label="LG전자-AI챗봇", value=2, href="/project/LG전자/AI챗봇"),
    ]
    svg = bar_chart_svg(items)
    assert "<svg" in svg
    assert "삼성전자-ERP고도화" in svg
    assert "href=" in svg


def test_bar_chart_empty_items_does_not_crash():
    svg = bar_chart_svg([])
    assert "<svg" in svg
    assert "데이터 없음" in svg


def test_bar_chart_long_label_is_truncated():
    items = [BarItem(label="아주아주아주아주아주아주아주아주아주아주긴고객사명-프로젝트명", value=1)]
    svg = bar_chart_svg(items, max_label_len=10)
    assert "…" in svg
