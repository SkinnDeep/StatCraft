"""SVG and Clean Standalone HTML Report Exporter for StatCraft.

Provides:
1. Direct lossless vector SVG rendering to clipboard and disk via QSvgGenerator.
2. Single-file, zero-dependency standalone HTML5 session report generation with embedded styling.
"""
from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QMimeData, QRectF
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QApplication, QWidget

from .executive_summary import generate_executive_summary


def export_widget_to_svg_bytes(widget: QWidget) -> bytes:
    """Render any QWidget vector chart directly to SVG bytes in memory."""
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)

    generator = QSvgGenerator()
    generator.setOutputDevice(buf)
    w_size = widget.size()
    if w_size.width() <= 0 or w_size.height() <= 0:
        w_size = widget.minimumSizeHint()
    generator.setSize(w_size)
    generator.setViewBox(widget.rect())
    generator.setTitle("StatCraft Vector Plot")
    generator.setDescription("Rendered by StatCraft Desktop")

    from PySide6.QtCore import QPoint
    painter = QPainter(generator)
    widget.render(painter, QPoint(0, 0))
    painter.end()
    del painter

    return bytes(buf.data())


def copy_widget_svg_to_clipboard(widget: QWidget) -> bool:
    """Render widget as crisp SVG vector graphics and copy to system clipboard."""
    svg_bytes = export_widget_to_svg_bytes(widget)
    mime = QMimeData()
    mime.setData("image/svg+xml", QByteArray(svg_bytes))
    mime.setText(svg_bytes.decode("utf-8", errors="replace"))

    cb = QApplication.clipboard()
    if cb is not None:
        cb.setMimeData(mime)
        return True
    return False


def export_session_to_html(
    history: List[Dict[str, Any]],
    worksheet_name: str = "Active Worksheet",
    output_path: Optional[str] = None,
    chart_widgets: Optional[Dict[int, QWidget]] = None,
) -> str:
    """Export complete session log into a clean, zero-dependency standalone HTML5 report."""
    from .app import format_entry
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cards_html = []
    for idx, entry in enumerate(history, 1):
        title = html.escape(entry.get("title", f"Analysis {idx}"))
        result = entry.get("result", {})
        analysis = html.escape(str(result.get("analysis", "Procedure")))

        # Executive summary
        bullets = generate_executive_summary(entry)
        brief_html = ""
        if bullets:
            b_items = "".join(f"<li style='margin-bottom: 4px;'>{html.escape(b)}</li>" for b in bullets)
            brief_html = f"""
            <div style="background: #f0fdf4; border-left: 4px solid #16a34a; border-radius: 4px; padding: 10px 14px; margin: 12px 0;">
                <div style="font-weight: 700; color: #166534; font-size: 11px; text-transform: uppercase; margin-bottom: 4px;">Executive Brief</div>
                <ul style="margin: 0; padding-left: 18px; color: #14532d; font-size: 13px; line-height: 1.5;">
                    {b_items}
                </ul>
            </div>
            """

        # Full statistical formatted output block
        formatted_txt = html.escape(format_entry(entry).strip())
        metrics_html = (
            f'<pre style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; '
            f'padding: 12px; font-size: 12px; line-height: 1.45; overflow-x: auto; color: #0f172a;">{formatted_txt}</pre>'
        )

        # Inline vector SVG chart when available
        chart_html = ""
        if chart_widgets and (idx - 1) in chart_widgets:
            svg_raw = export_widget_to_svg_bytes(chart_widgets[idx - 1]).decode("utf-8", errors="replace")
            chart_html = f'<div style="margin-top: 14px; text-align: center; overflow-x: auto;">{svg_raw}</div>'

        cards_html.append(f"""
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px;">
                <h3 style="margin: 0; font-size: 16px; color: #0f172a;">{title}</h3>
                <span style="font-size: 11px; background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 12px; font-weight: 600;">{analysis}</span>
            </div>
            {brief_html}
            {metrics_html}
            {chart_html}
        </div>
        """)

    body_content = "\n".join(cards_html) if cards_html else "<p style='color: #64748b;'>No session analyses recorded.</p>"

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StatCraft Session Report — {html.escape(worksheet_name)}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #f8fafc;
            color: #1e293b;
            margin: 0;
            padding: 32px 16px;
        }}
        .container {{
            max-width: 880px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid #e2e8f0;
        }}
        h1 {{
            font-size: 24px;
            font-weight: 800;
            color: #0f172a;
            margin: 0 0 6px 0;
        }}
        .meta {{
            font-size: 12px;
            color: #64748b;
        }}
        footer {{
            margin-top: 40px;
            text-align: center;
            font-size: 11px;
            color: #94a3b8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>StatCraft Statistical Session Report</h1>
            <div class="meta">Worksheet: <strong>{html.escape(worksheet_name)}</strong> · Generated: {now_str} · StatCraft v116.4.0</div>
        </header>
        <main>
            {body_content}
        </main>
        <footer>
            Generated locally by StatCraft · 100% Offline & Private Quality Engineering
        </footer>
    </div>
</body>
</html>"""

    if output_path:
        Path(output_path).write_text(html_doc, encoding="utf-8")

    return html_doc


def export_session_to_markdown(
    history: List[Dict[str, Any]],
    worksheet_name: str = "Active Worksheet",
    output_path: Optional[str] = None,
    chart_widgets: Optional[Dict[int, QWidget]] = None,
) -> str:
    """Export complete session analyses, Executive Briefs, and vector SVGs to Markdown."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = [
        f"# StatCraft Session Report — {worksheet_name}",
        f"*Generated locally: {now_str} · StatCraft v116.4.0*",
        "",
        "## Table of Contents",
    ]
    for idx, entry in enumerate(history, 1):
        lines.append(f"- [{idx}. {entry.get('title', f'Analysis {idx}')}](#analysis-{idx})")
    lines.append("")

    assets_dir = None
    if output_path and chart_widgets:
        assets_dir = Path(output_path).parent / f"{Path(output_path).stem}_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

    from .app import format_entry
    for idx, entry in enumerate(history, 1):
        title = entry.get("title", f"Analysis {idx}")
        lines.append(f"---")
        lines.append(f'## <a id="analysis-{idx}"></a>{idx}. {title}')
        bullets = generate_executive_summary(entry)
        if bullets:
            lines.append("")
            lines.append("**Executive Brief:**")
            for b in bullets:
                lines.append(f"- {b}")
        lines.append("")
        lines.append("```text")
        lines.append(format_entry(entry).strip())
        lines.append("```")
        if chart_widgets and idx - 1 in chart_widgets and assets_dir is not None:
            svg_bytes = export_widget_to_svg_bytes(chart_widgets[idx - 1])
            svg_name = f"chart_{idx}.svg"
            (assets_dir / svg_name).write_bytes(svg_bytes)
            lines.append("")
            lines.append(f"![{title}]({assets_dir.name}/{svg_name})")
        lines.append("")

    md_doc = "\n".join(lines)
    if output_path:
        Path(output_path).write_text(md_doc, encoding="utf-8")
    return md_doc
