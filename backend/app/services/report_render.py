"""Renderers for the report content model: PDF (reportlab), DOCX (python-docx) and standalone HTML."""
from __future__ import annotations

import html as _html
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK, SLATE, LINE, ACCENT, SOFT = (colors.HexColor(c) for c in ("#0f172a", "#475569", "#cbd5e1", "#1d4ed8", "#f1f5f9"))
LABEL_NOTE = {"ENGINE": "produced by GhostTrace agents and rules; requires human review",
              "HUMAN": "recorded by a human reviewer", "SYSTEM": "deterministic platform records",
              "ENGINE + HUMAN": "engine decision with the human review status"}


def cell_text(c) -> str:
    """Plain text of a cell (str, citation dict, or list of them)."""
    if c is None:
        return "—"
    if isinstance(c, dict):
        return c.get("text", "")
    if isinstance(c, list):
        return " ".join(cell_text(x) for x in c) if c else "—"
    return str(c)


# ------------------------------------------------------------------ PDF
def _styles():
    ss = getSampleStyleSheet()
    b = ParagraphStyle("b", parent=ss["Normal"], fontName="Helvetica", fontSize=8.4, leading=11.2, textColor=INK)
    return {"title": ParagraphStyle("t", parent=b, fontName="Helvetica-Bold", fontSize=19, leading=23),
            "sub": ParagraphStyle("s", parent=b, fontSize=9.5, textColor=SLATE, leading=13),
            "h1": ParagraphStyle("h1", parent=b, fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=10, spaceAfter=4),
            "lab": ParagraphStyle("lab", parent=b, fontSize=7, textColor=ACCENT, leading=9, spaceAfter=3),
            "b": b, "cell": ParagraphStyle("c", parent=b, fontSize=7.2, leading=9.2),
            "head": ParagraphStyle("hd", parent=b, fontName="Helvetica-Bold", fontSize=7, textColor=SLATE, leading=9)}


def _pp(text, st):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), st)


def _cellp(c, st):
    if isinstance(c, (dict, list)):
        parts = c if isinstance(c, list) else [c]
        txt = " ".join(f'<font color="#1d4ed8">{escape(p["text"])}</font>' if isinstance(p, dict) else escape(str(p)) for p in parts)
        return Paragraph(txt or "—", st)
    return _pp(c if c not in (None, "") else "—", st)


def _tbl(cols, rows, widths, st, total=180):
    widths = widths or [total / len(cols)] * len(cols)
    scale = total / sum(widths)
    data = [[_pp(c, st["head"]) for c in cols]] + [[_cellp(c, st["cell"]) for c in r] for r in rows]
    t = Table(data, colWidths=[w * scale * mm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), SOFT),
                           ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


def to_pdf(c: dict) -> bytes:
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
                            title=f"GhostTrace report {c['case']['number']}")

    def footer(cv, d):
        cv.saveState()
        cv.setFont("Helvetica", 7)
        cv.setFillColor(SLATE)
        cv.drawString(15 * mm, 10 * mm, f"GhostTrace · {c['case']['number']} · for human review - contains engine interpretations, not legal conclusions")
        cv.drawRightString(195 * mm, 10 * mm, f"Page {d.page}")
        cv.restoreState()

    s = [_pp("GhostTrace", st["sub"]), _pp(("Scenario Lab Test Report" if c.get("scenario") else "Investigation Report") + f" — {c['case']['title']}", st["title"]),
         Spacer(1, 3), _pp(f"Case {c['case']['number']} · generated {c['generated_at']}" + (" · REDACTED" if c.get("redacted") else ""), st["sub"]), Spacer(1, 4),
         _pp("Citations: [EV-code | location]. Labels: ENGINE = agent/rule output requiring review; HUMAN = reviewer decision; SYSTEM = platform record.", st["sub"])]
    sc = c.get("scenario")
    if sc:
        s.append(_pp("Scenario evaluation", st["h1"]))
        s.append(_tbl(["Field", "Value"], [["Scenario", sc["scenario"]], ["Test ID", sc["test_code"]], ["Executed", sc["executed"]],
                                           ["Result", f"{sc['outcome']} — {sc['outcome_reason']}"], ["Expected", sc.get("expected_outcome", "—")],
                                           ["Duration", f"{sc['duration_ms']} ms"], ["Dataset", sc.get("dataset", "—")]], [40, 140], st))
        s.append(Spacer(1, 4))
        s.append(_tbl(["Metric", "Value", "Basis"], [[k.replace("_", " "), v.get("display"), v.get("basis", "")] for k, v in sc.get("metrics", {}).items()
                                                   if isinstance(v, dict)], [50, 26, 104], st))
        s.append(Spacer(1, 4))
        s.append(_tbl(["ID", "Expected finding", "Critical", "Result", "Matched by"], [[f["id"], f["description"], "yes" if f.get("critical") else "no",
                                                                                      f["status"], f.get("matched_by") or "—"] for f in sc.get("findings", [])],
                      [12, 70, 14, 16, 68], st))
        for title, key in (("Rule violations", "violations"), ("Recommended improvements", "recommendations"), ("Errors", "errors")):
            if sc.get(key):
                s.append(_pp(title, st["h1"]))
                s += [_pp("• " + str(x), st["b"]) for x in sc[key]]
    for sec in c["sections"]:
        s.append(_pp(f"{sec['n']}. {sec['title']}", st["h1"]))
        s.append(_pp(f"[{sec['label']}] {LABEL_NOTE.get(sec['label'], '')}", st["lab"]))
        for b in sec["blocks"]:
            if b["type"] == "para":
                s.append(_pp(b["text"], st["b"]))
                s.append(Spacer(1, 3))
            elif b["type"] == "list":
                s += [_pp("• " + str(x), st["b"]) for x in b["items"]]
            elif b["type"] == "table":
                s.append(_tbl(b["columns"], b["rows"], b.get("widths"), st))
                s.append(Spacer(1, 4))
            elif b["type"] == "card":
                s.append(KeepTogether([_tbl([b["title"], ""], b["rows"], [34, 146], st), Spacer(1, 4)]))
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# ------------------------------------------------------------------ DOCX
def to_docx(c: dict) -> bytes:
    import docx
    from docx.shared import Pt, RGBColor
    d = docx.Document()
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(9.5)
    d.add_heading(("Scenario Lab Test Report" if c.get("scenario") else "Investigation Report") + f" — {c['case']['title']}", level=0)
    d.add_paragraph(f"Case {c['case']['number']} · generated {c['generated_at']}" + (" · REDACTED" if c.get("redacted") else ""))
    d.add_paragraph("Citations: [EV-code | location]. Labels: ENGINE = agent/rule output requiring review; HUMAN = reviewer decision; "
                    "SYSTEM = platform record.").italic = True

    def add_table(cols, rows):
        t = d.add_table(rows=1, cols=len(cols))
        t.style = "Light Grid Accent 1"
        for i, col in enumerate(cols):
            t.rows[0].cells[i].text = str(col)
        for r in rows:
            cells = t.add_row().cells
            for i, v in enumerate(r[:len(cols)]):
                cells[i].text = cell_text(v)
        d.add_paragraph()

    sc = c.get("scenario")
    if sc:
        d.add_heading("Scenario evaluation", level=1)
        add_table(["Field", "Value"], [["Result", f"{sc['outcome']} — {sc['outcome_reason']}"], ["Expected", sc.get("expected_outcome", "—")],
                                       ["Test ID", sc["test_code"]], ["Duration", f"{sc['duration_ms']} ms"]])
        add_table(["Metric", "Value", "Basis"], [[k, v.get("display"), v.get("basis", "")] for k, v in sc.get("metrics", {}).items() if isinstance(v, dict)])
    for sec in c["sections"]:
        d.add_heading(f"{sec['n']}. {sec['title']}", level=1)
        p = d.add_paragraph(f"[{sec['label']}] {LABEL_NOTE.get(sec['label'], '')}")
        p.runs[0].font.color.rgb = RGBColor(0x1D, 0x4E, 0xD8)
        for b in sec["blocks"]:
            if b["type"] == "para":
                d.add_paragraph(b["text"])
            elif b["type"] == "list":
                for x in b["items"]:
                    d.add_paragraph(str(x), style="List Bullet")
            elif b["type"] == "table":
                add_table(b["columns"], b["rows"])
            elif b["type"] == "card":
                d.add_paragraph(b["title"]).runs[0].bold = True
                add_table(["", ""], b["rows"])
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()


# ------------------------------------------------------------------ HTML
def to_html(c: dict, link_base: str = "") -> str:
    e = _html.escape

    def cell(v):
        if isinstance(v, list):
            return " ".join(cell(x) for x in v) or "—"
        if isinstance(v, dict):
            if v.get("evidence_id"):
                q = f"?segment={v['segment_id']}" if v.get("segment_id") else ""
                return f'<a class="cite" href="{link_base}/evidence/{e(v["evidence_id"])}{e(q)}">{e(v["text"])}</a>'
            return f'<span class="cite">{e(v.get("text", ""))}</span>'
        return e(str(v)) if v not in (None, "") else "—"

    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>GhostTrace report {e(c['case']['number'])}</title><style>"
           "body{font:14px/1.5 system-ui,Segoe UI,sans-serif;background:#0b1020;color:#e2e8f0;margin:0;padding:24px}main{max-width:1040px;margin:auto}"
           "h1{font-size:24px}h2{font-size:17px;margin-top:28px;border-bottom:1px solid #1e293b;padding-bottom:6px}"
           ".lab{color:#60a5fa;font-size:12px}table{border-collapse:collapse;width:100%;margin:8px 0;font-size:12.5px}"
           "td,th{border:1px solid #1e293b;padding:5px 7px;vertical-align:top;text-align:left}th{background:#111827;color:#94a3b8}"
           "a.cite,.cite{color:#60a5fa;font-family:ui-monospace,Consolas,monospace;font-size:11.5px;text-decoration:none}a.cite:hover{text-decoration:underline}"
           ".card{border:1px solid #1e293b;border-radius:8px;margin:10px 0}.card h3{margin:0;padding:8px 10px;font-size:13px;background:#111827}"
           ".muted{color:#94a3b8}</style></head><body><main>",
           f"<div class='muted'>GhostTrace</div><h1>{'Scenario Lab Test Report' if c.get('scenario') else 'Investigation Report'} — {e(c['case']['title'])}</h1>",
           f"<p class='muted'>Case {e(c['case']['number'])} · generated {e(c['generated_at'])}{' · REDACTED' if c.get('redacted') else ''}</p>",
           "<p class='muted'>Citations: [EV-code | location] link to the cited evidence location. ENGINE = agent/rule output requiring review; "
           "HUMAN = reviewer decision; SYSTEM = platform record.</p>"]
    for sec in c["sections"]:
        out.append(f"<h2>{sec['n']}. {e(sec['title'])}</h2><div class='lab'>[{e(sec['label'])}] {e(LABEL_NOTE.get(sec['label'], ''))}</div>")
        for b in sec["blocks"]:
            if b["type"] == "para":
                out.append(f"<p>{e(b['text'])}</p>")
            elif b["type"] == "list":
                out.append("<ul>" + "".join(f"<li>{e(str(x))}</li>" for x in b["items"]) + "</ul>")
            elif b["type"] == "table":
                out.append("<table><tr>" + "".join(f"<th>{e(str(x))}</th>" for x in b["columns"]) + "</tr>"
                           + "".join("<tr>" + "".join(f"<td>{cell(v)}</td>" for v in r) + "</tr>" for r in b["rows"]) + "</table>")
            elif b["type"] == "card":
                out.append(f"<div class='card'><h3>{e(b['title'])}</h3><table>"
                           + "".join(f"<tr><th style='width:150px'>{e(str(k))}</th><td>{cell(v)}</td></tr>" for k, v in b["rows"]) + "</table></div>")
    out.append("</main></body></html>")
    return "".join(out)
