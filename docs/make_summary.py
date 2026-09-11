#!/usr/bin/env python3
"""Regenerate Project_Summary.pdf.

Usage: python3 docs/make_summary.py

Keep the content here, not in the PDF: the PDF is a build artefact, and this
script is the thing to edit when the project moves on.
"""

import subprocess
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Project_Summary.pdf"

INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#5c5c5c")
RULE = colors.HexColor("#d4d4d4")
BAND = colors.HexColor("#f2f2f0")
GOOD = colors.HexColor("#1b6b3a")
WARN = colors.HexColor("#9a5b00")

styles = getSampleStyleSheet()
S = {
    "title": ParagraphStyle(
        "title", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=21, leading=25, textColor=INK, alignment=TA_LEFT, spaceAfter=2,
    ),
    "sub": ParagraphStyle(
        "sub", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9.5, leading=13, textColor=MUTED, spaceAfter=14,
    ),
    "h2": ParagraphStyle(
        "h2", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12.5, leading=15, textColor=INK, spaceBefore=16, spaceAfter=6,
    ),
    "body": ParagraphStyle(
        "body", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9.5, leading=13.5, textColor=INK, spaceAfter=7,
    ),
    "cell": ParagraphStyle(
        "cell", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.5, leading=11.5, textColor=INK,
    ),
    "cellb": ParagraphStyle(
        "cellb", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8.5, leading=11.5, textColor=INK,
    ),
    "mono": ParagraphStyle(
        "mono", parent=styles["Normal"], fontName="Courier",
        fontSize=8.5, leading=11.5, textColor=INK,
    ),
}


def p(text, style="body"):
    return Paragraph(text, S[style])


def table(rows, widths, header=True, zebra=True):
    data = [[c if not isinstance(c, str) else p(c, "cellb" if header and i == 0 else "cell")
             for c in row] for i, row in enumerate(rows)]
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, INK if header else RULE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]
    if zebra:
        for i in range(2 if header else 1, len(data), 2):
            style.append(("BACKGROUND", (0, i), (-1, i), BAND))
    t = Table(data, colWidths=widths, hAlign="LEFT")
    t.setStyle(TableStyle(style))
    return t


def tag(text, color):
    return Paragraph(
        f'<font color="{color.hexval()}"><b>{text}</b></font>', S["cell"]
    )


def git(*args, default="unknown"):
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return default


def build(story):
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="mytools - Project Summary", author="Luis R Arriola",
    )

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 12 * mm, "mytools - project summary")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"page {doc_.page}")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(20 * mm, 15.5 * mm, A4[0] - 20 * mm, 15.5 * mm)
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def story():
    W = A4[0] - 40 * mm
    out = []

    out += [
        p("mytools", "title"),
        p(
            f"A subset of bedtools, rebuilt in Python against the real thing as oracle<br/>"
            f"Luis R Arriola &nbsp;·&nbsp; natoarriola/ai_agent_workshop &nbsp;·&nbsp; "
            f"{date.today():%d %B %Y}",
            "sub",
        ),
    ]

    out += [p("What this is", "h2")]
    out += [p(
        "<b>mytools</b> reimplements four things bedtools does - <font face='Courier'>sort</font>, "
        "<font face='Courier'>merge</font>, <font face='Courier'>intersect</font>, "
        "<font face='Courier'>subtract</font> - over BED interval files. Python 3, standard "
        "library only, one executable file."
    )]
    out += [p(
        "The method matters more than the code. Real bedtools is installed on the VM and is "
        "treated as the <b>oracle</b>: every subcommand is diffed against it byte for byte on "
        "the same input, and where we disagree, we are wrong. No expected-output file was ever "
        "written by hand, so no misunderstanding could be enshrined in a test."
    )]

    out += [p("Where it stands", "h2")]
    out += [table([
        ["", "Status", "Detail"],
        ["Golden tests", tag("20 / 20", GOOD), "every subcommand and flag, from a file and from stdin"],
        ["Randomised", tag("1,600 cases", GOOD), "merge, intersect and subtract vs. bedtools; all match"],
        ["Unit tests", tag("123 passing", GOOD), "stdlib unittest, 4 ms, no bedtools needed"],
        ["Linter", tag("clean", GOOD), "ruff 0.16.7 pinned, plus shellcheck on the test runner"],
        ["CI", tag("never run", WARN), "Actions needs enabling on the fork - see Outstanding"],
        ["Merged to main", tag("nothing yet", WARN), "8 pull requests open, 6 of them in one stack"],
    ], [30 * mm, 27 * mm, W - 57 * mm])]

    out += [p("Subcommands", "h2")]
    out += [table([
        ["Command", "Flags", "State"],
        ["sort", "-i", tag("done - 4/4 golden", GOOD)],
        ["merge", "-i, -d", tag("done - 6/6 golden", GOOD)],
        ["intersect", "-a, -b, -u, -v, -wa", tag("done - 7/7 golden", GOOD)],
        ["subtract", "-a, -b", tag("done - 3/3 golden", GOOD)],
        ["closest", "-", tag("out of scope for v1", MUTED)],
    ], [28 * mm, 45 * mm, W - 73 * mm])]

    out += [p(
        "<b>v1 is complete.</b> Scope was cut deliberately: <font face='Courier'>closest</font> was "
        "dropped when the spec was adopted, on the principle that four finished subcommands beat "
        "seven half-built ones."
    )]

    out += [PageBreak()]

    out += [p("What the oracle actually does", "h2")]
    out += [p(
        "This is the part worth keeping. BED is 0-based and half-open, so two intervals overlap "
        "only when <font face='Courier'>a.start &lt; b.end</font> and "
        "<font face='Courier'>b.start &lt; a.end</font>, strictly. Every off-by-one lives on that "
        "line. But zero-length intervals - legal in BED, and present in the fixtures on purpose - "
        "break the rule in a way nobody predicts:"
    )]
    out += [p(
        "<b>bedtools widens every zero-length interval <font face='Courier'>[x, x)</font> to "
        "<font face='Courier'>[x-1, x+1)</font> before testing overlap.</b> Confirmed on 12 probes "
        "before a line was written. What each subcommand then does with that widening is "
        "<i>different every time</i>:"
    )]
    out += [table([
        ["Subcommand", "What the widening affects", "Example the oracle gives"],
        ["intersect", "the decision only; reported coordinates mix -a's original with -b's widened",
         "chr1 100 200 ∩ chr1 150 150 → chr1 149 151"],
        ["merge", "the decision and the output - except a cluster of one feature, which prints unchanged",
         "chr1 0 0 beside chr1 0 10 → chr1 -1 10 (negative!)"],
        ["subtract", "the cut, but not the printing: a zero-length feature survives whole or not at all",
         "chr1 9 9 survives a hole at [9,10), dies at [8,10)"],
        ["sort", "nothing - ordering never consults it",
         "chr1 500 500 sorts before chr1 500 600"],
    ], [27 * mm, 59 * mm, W - 86 * mm])]

    out += [p(
        "<b>The golden suite did not catch the last one.</b> The first subtract passed all 20 "
        "golden cases and still disagreed with bedtools on 3 of 300 random inputs, every one a "
        "zero-length feature on the -a side. Randomised differential testing found in seconds what "
        "a hand-built fixture set had no reason to contain - worth remembering about any green "
        "suite: necessary, not sufficient."
    )]

    out += [p("Four more findings that cost real debugging", "h2")]
    out += [table([
        ["Finding", "Why it matters"],
        ["intersect reports hits in <b>-b file order</b>, not coordinate order",
         "Sorting the hits looks tidier and fails two golden cases."],
        ["<b>bedtools crashes</b> on a zero-length feature at position 0 in -b",
         "It widens to -1 and its bin tree rejects it. A golden case pins that exit code, so mytools refuses the same input rather than succeeding where the oracle dies."],
        ["merge checks sortedness <b>loosely</b>",
         "Start order within a chromosome only. chr2 before chr1 exits 0; only revisiting a chromosome is an error."],
        ["Chromosomes sort <b>byte-wise</b>, not naturally",
         "chr10 before chr2, and chr17 before chr7."],
    ], [62 * mm, W - 62 * mm])]

    out += [p("How the work was done", "h2")]
    out += [table([
        ["#", "Issue / PR", "Outcome"],
        ["1 / 5", "Warm-up: mytools --version", "usage to stderr, exit 2 with no arguments"],
        ["2 / 4", "Adopt or write a spec", "SPEC.md adopted from the fallback, then corrected twice from evidence"],
        ["3 / 6", "Tests, linter, CI", "20 golden cases, 30 unit cases, ruff, shellcheck, ci.yml"],
        ["7 / 8", "sort", "stable, byte-wise chromosome order, verbatim column preservation"],
        ["9 / 10", "merge", "streaming clusters; matched on 400 random inputs"],
        ["11 / 12", "intersect", "bisect index over -b; matched on 300 random inputs"],
        ["14 / 15", "subtract", "hole-punching; matched on 600 random inputs"],
        ["- / 13", "This summary", "generated by docs/make_summary.py"],
    ], [16 * mm, 48 * mm, W - 64 * mm])]

    out += [p(
        "Two spec corrections came out of implementation, not planning. SPEC §3 claimed ragged "
        "column counts were tolerated - bedtools refuses them outright. And merge streams, so a "
        "chromosome revisit discovered mid-file leaves already-completed clusters on stdout where "
        "bedtools writes nothing; that one is recorded in §8 as an accepted deviation, with its "
        "reason, rather than quietly fixed."
    )]

    out += [KeepTogether([
        p("Outstanding", "h2"),
        table([
            ["What", "Needs"],
            ["<b>Enable Actions on the fork</b>",
             "GitHub disables workflows on forks until the owner clicks through the banner on the Actions tab. CI has therefore never run: all three guardrails are verified locally only."],
            ["<b>Merge the PR stack</b>",
             "Six PRs chain off each other (#4, #5 → #6 → #8 → #10 → #12 → #15), plus #13 for this summary. main is still at the upstream commit, so none of the work is on it yet."],
            ["<b>Stretch goals</b>",
             "Untouched: VCF forensics, real-data scale, annotating real variants. issues/04-06 were never filed."],
        ], [46 * mm, W - 46 * mm]),
    ])]

    out += [p("Running it", "h2")]
    out += [p(
        "<font face='Courier'>./tests/run_golden.sh</font> &nbsp; diffs every subcommand against "
        "real bedtools<br/>"
        "<font face='Courier'>python3 -m unittest discover -s tests</font> &nbsp; unit tests, no "
        "bedtools required<br/>"
        "<font face='Courier'>ruff check .</font> &nbsp; lint, including the extensionless entry point"
    )]
    return out


if __name__ == "__main__":
    build(story())
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")
