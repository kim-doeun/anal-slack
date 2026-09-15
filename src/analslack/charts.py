"""대시보드용 SVG 차트 생성.

외부 차트 라이브러리 없이 순수 SVG 마크업을 만든다. 색/스타일 규칙(CSS 변수,
gridline, 데이터 끝 라운딩, hover 툴팁)은 templates/base.html의 <style>에서
클래스 단위로 정의하고, 여기서는 구조(geometry)만 만든다.
"""

from __future__ import annotations

import math
from html import escape
from typing import NamedTuple, Optional, Sequence


class BarItem(NamedTuple):
    label: str
    value: float
    href: Optional[str] = None


def _nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(value))
    for m in (1, 2, 2.5, 5, 10):
        step = m * magnitude
        if step >= value:
            return step
    return float(value)


def _tick_fracs(max_v: float) -> list[float]:
    """y축 눈금 위치(0~1 비율). 값이 작을 때(<=4) 5분할하면 반올림으로 라벨이
    중복(예: 0,0,1,1,1)되므로, 정수 단위로 나눠 떨어지게 눈금 개수를 줄인다.
    """
    if max_v <= 4:
        n = max(1, round(max_v))
        return [i / n for i in range(n + 1)]
    return [0.0, 0.25, 0.5, 0.75, 1.0]


def _rounded_top_rect_path(x: float, y: float, w: float, h: float, r: float) -> str:
    """상단만 둥근 막대 (기준선에 붙는 하단은 각지게) - 세로 막대용."""
    if w <= 0 or h <= 0:
        return ""
    r = min(r, w / 2, h)
    return (
        f"M{x:.1f},{y + h:.1f} L{x:.1f},{y + r:.1f} "
        f"Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"L{x + w - r:.1f},{y:.1f} "
        f"Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
        f"L{x + w:.1f},{y + h:.1f} Z"
    )


def _rounded_right_rect_path(x: float, y: float, w: float, h: float, r: float) -> str:
    """우측만 둥근 막대 (기준선에 붙는 좌측은 각지게) - 가로 막대용."""
    if w <= 0 or h <= 0:
        return ""
    r = min(r, w, h / 2)
    return (
        f"M{x:.1f},{y:.1f} L{x + w - r:.1f},{y:.1f} "
        f"Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
        f"L{x + w:.1f},{y + h - r:.1f} "
        f"Q{x + w:.1f},{y + h:.1f} {x + w - r:.1f},{y + h:.1f} "
        f"L{x:.1f},{y + h:.1f} Z"
    )


def line_chart_svg(
    points: Sequence[tuple[str, float]],
    width: int = 640,
    height: int = 220,
    unit: str = "건",
    aria_label: str = "추이",
) -> str:
    """points: (라벨, 값) 시계열. 단일 시리즈 라인 차트."""
    pad_left, pad_right, pad_top, pad_bottom = 40, 16, 16, 26
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    n = len(points)
    values = [v for _, v in points]
    max_v = _nice_max(max(values) if values else 0)

    def px(i: int) -> float:
        return pad_left + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)

    def py(v: float) -> float:
        return pad_top + plot_h - (plot_h * v / max_v if max_v else 0)

    grid_parts = []
    for frac in _tick_fracs(max_v):
        gy = pad_top + plot_h - plot_h * frac
        grid_parts.append(
            f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{width - pad_right}" y2="{gy:.1f}" class="chart-grid" />'
        )
        grid_parts.append(
            f'<text x="{pad_left - 8}" y="{gy + 3:.1f}" text-anchor="end" class="chart-axis-label">{round(max_v * frac)}</text>'
        )

    if n == 0:
        body = '<text x="50%" y="50%" text-anchor="middle" class="chart-empty">데이터 없음</text>'
        return f'<svg viewBox="0 0 {width} {height}" class="viz-root chart" role="img" aria-label="{escape(aria_label)}">{body}</svg>'

    path_d = " ".join(
        f"{'M' if i == 0 else 'L'}{px(i):.1f},{py(v):.1f}" for i, (_, v) in enumerate(points)
    )

    points_svg = []
    for i, (label, v) in enumerate(points):
        cx, cy = px(i), py(v)
        points_svg.append(
            f'<g class="chart-pt">'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" class="chart-hit" />'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" class="chart-dot" />'
            f'<g class="chart-tip" transform="translate({cx:.1f},{max(cy - 14, 12):.1f})">'
            f'<rect x="-38" y="-20" width="76" height="20" rx="4" class="chart-tip-bg" />'
            f'<text x="0" y="-6" text-anchor="middle" class="chart-tip-text">{escape(label)}: {v}{unit}</text>'
            f'</g></g>'
        )

    step = max(1, n // 6)
    x_labels = []
    for i, (label, _) in enumerate(points):
        if i % step != 0 and i != n - 1:
            continue
        x_labels.append(
            f'<text x="{px(i):.1f}" y="{height - 6}" text-anchor="middle" class="chart-axis-label">{escape(label)}</text>'
        )

    return (
        f'<svg viewBox="0 0 {width} {height}" class="viz-root chart" role="img" aria-label="{escape(aria_label)}">'
        f'{"".join(grid_parts)}'
        f'<line x1="{pad_left}" y1="{pad_top + plot_h:.1f}" x2="{width - pad_right}" y2="{pad_top + plot_h:.1f}" class="chart-baseline" />'
        f'<path d="{path_d}" class="chart-line" fill="none" />'
        f'{"".join(points_svg)}'
        f'{"".join(x_labels)}'
        f'</svg>'
    )


def bar_chart_svg(
    items: Sequence[BarItem],
    width: int = 640,
    row_height: int = 30,
    unit: str = "건",
    label_width: int = 200,
    max_label_len: int = 26,
    aria_label: str = "순위",
) -> str:
    """items: 값 내림차순 정렬된 (라벨, 값, 링크) 목록. 가로 막대 차트."""
    if not items:
        return (
            f'<svg viewBox="0 0 {width} 60" class="viz-root chart" role="img" aria-label="{escape(aria_label)}">'
            f'<text x="50%" y="50%" text-anchor="middle" class="chart-empty">데이터 없음</text></svg>'
        )

    pad_left, pad_right, pad_top = 8, 48, 8
    plot_x = pad_left + label_width
    plot_w = width - plot_x - pad_right
    height = pad_top * 2 + len(items) * row_height
    max_v = _nice_max(max(v for _, v, _ in items))

    rows = []
    for i, (label, value, href) in enumerate(items):
        y = pad_top + i * row_height
        bar_h = row_height - 10
        bar_w = max((plot_w * value / max_v) if max_v else 0, 2)
        label_text = label if len(label) <= max_label_len else label[: max_label_len - 1] + "…"
        bar_path = _rounded_right_rect_path(plot_x, y, bar_w, bar_h, r=4)
        cy = y + bar_h / 2 + 4

        content = (
            f'<text x="{plot_x - 10}" y="{cy:.1f}" text-anchor="end" class="chart-row-label">{escape(label_text)}</text>'
            f'<path d="{bar_path}" class="chart-bar" />'
            f'<text x="{plot_x + bar_w + 8:.1f}" y="{cy:.1f}" class="chart-value-label">{value:g}{unit}</text>'
        )

        if href:
            rows.append(f'<a href="{escape(href)}" class="chart-bar-row"><g>{content}</g></a>')
        else:
            rows.append(f'<g class="chart-bar-row">{content}</g>')

    return (
        f'<svg viewBox="0 0 {width} {height}" class="viz-root chart" role="img" aria-label="{escape(aria_label)}">'
        f'{"".join(rows)}'
        f'</svg>'
    )
