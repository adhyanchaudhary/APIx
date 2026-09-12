"""Generate line-by-line HTML walkthroughs for the current project files.

Unlike a hand-typed dump, this script reads each real source file at build
time and stitches it together with a hand-written explanation dict (one entry
per line). That guarantees the "code" column always matches the actual file,
and a hard assertion enforces 100% line coverage.

Usage (from the project root):
    python src/generate_walkthroughs.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "walkthroughs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

from walk_data_core import FILES as FILES_CORE
from walk_data_scraper import FILES as FILES_SCRAPER
from walk_data_cleaner import FILES as FILES_CLEANER
from walk_data_indexer import FILES as FILES_INDEXER

FILES = sorted(
    FILES_CORE + FILES_SCRAPER + FILES_CLEANER + FILES_INDEXER,
    key=lambda f: f["out"],
)

# ── Shared CSS template ──────────────────────────────────────────────────────
CSS = """
:root{--bg:#F08080;--card:rgba(255,255,255,0.92);--blue:#0D47A1;--blue-mid:#1565C0;--blue-light:#BBDEFB;--green:#1B5E20;--green-light:#C8E6C9;--red:#B71C1C;--red-light:#FFCDD2;--black:#1A1A2E;--grey:#546E7A}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Tahoma,sans-serif;background:var(--bg);color:var(--black);line-height:1.7}
.wrap{max-width:900px;margin:0 auto;padding:20px}
header{background:var(--blue);color:#fff;padding:24px 32px;border-radius:14px;margin-bottom:24px}
header h1{font-size:1.6rem}
header .sub{opacity:.75;margin-top:4px;font-size:.9rem}
.card{background:var(--card);border-radius:14px;padding:24px 28px;margin-bottom:20px;border-left:6px solid var(--blue-mid)}
.card h2{color:var(--blue);font-size:1.2rem;margin-bottom:8px}
.line-block{margin:14px 0;border-radius:8px;overflow:hidden;border:1px solid #ddd}
.line-header{background:var(--blue);color:#fff;padding:6px 14px;font-size:.85rem;font-weight:600}
.line-code{background:#263238;color:#80CBC4;padding:10px 16px;font-family:'Courier New',monospace;font-size:.85rem;white-space:pre;overflow-x:auto}
.line-explain{background:#E8F5E9;padding:10px 16px;font-size:.9rem;border-top:1px solid #C8E6C9}
.line-explain strong{color:var(--green)}
.line-explain code{background:#C8E6C9;padding:1px 5px;border-radius:3px;font-family:'Courier New',monospace;font-size:.85rem}
.nav{display:flex;justify-content:space-between;margin:20px 0}
.nav a{background:var(--blue);color:#fff;padding:8px 18px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.9rem}
.nav a:hover{background:var(--blue-mid)}
.note{background:var(--blue-light);border-left:4px solid var(--blue);padding:10px 14px;border-radius:6px;margin:10px 0;font-size:.9rem}
.summary{background:var(--green-light);border-left:4px solid var(--green);padding:12px 16px;border-radius:6px;margin:14px 0;color:var(--green)}
.summary::before{content:"Key takeaway: ";font-weight:700}
"""


def _esc(code: str) -> str:
    return code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def make_html(title, file_label, paired_lines, prev_file=None, next_file=None):
    """Build one walkthrough HTML file from (code, explanation) pairs."""
    body = []
    for i, (code, explanation) in enumerate(paired_lines, 1):
        body.append(
            f'''<div class="line-block">
<div class="line-header">Line {i}</div>
<div class="line-code">{_esc(code)}</div>
<div class="line-explain">{explanation}</div>
</div>'''
        )

    nav = '<div class="nav">'
    nav += f'<a href="{prev_file}">&larr; Previous</a>' if prev_file else "<span></span>"
    nav += f'<a href="{next_file}">Next &rarr;</a>' if next_file else "<span></span>"
    nav += "</div>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
<h1>{title}</h1>
<div class="sub">{file_label}</div>
</header>
{nav}
<div class="card">
<h2>File Overview</h2>
<p>Every line of this file is explained in plain English below. Code shown is read directly from the current file on disk.</p>
</div>
{"".join(body)}
<div class="card">
<h2>Summary</h2>
<p>This file has <strong>{len(paired_lines)} lines</strong>, each explained above.</p>
</div>
{nav}
</div>
</body>
</html>"""


def build_one(spec: dict) -> None:
    """Read the real source file, zip with explanations, render HTML."""
    src_path = ROOT / spec["src"]
    lines = src_path.read_text(encoding="utf-8").splitlines()
    notes = spec["notes"]

    missing = [i + 1 for i in range(len(lines)) if i not in notes]
    if missing:
        raise ValueError(f"{spec['src']}: no explanation for line(s): {missing}")
    extra = [i + 1 for i in notes if i >= len(lines)]
    if extra:
        raise ValueError(f"{spec['src']}: explanation for non-existent line(s): {extra}")

    paired = [(code, notes[i]) for i, code in enumerate(lines)]
    html = make_html(spec["title"], spec["src"], paired, spec["prev"], spec["next"])
    (OUT_DIR / spec["out"]).write_text(html, encoding="utf-8")
    print(f"  {spec['out']:26s} {len(lines):4d} lines")


# ── Master index ─────────────────────────────────────────────────────────────
INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Code Walkthrough - Master Index</title>
<style>
:root{--bg:#F08080;--card:rgba(255,255,255,0.92);--blue:#0D47A1;--blue-mid:#1565C0;--blue-light:#BBDEFB;--green:#1B5E20;--green-light:#C8E6C9;--black:#1A1A2E;--grey:#546E7A}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Tahoma,sans-serif;background:var(--bg);color:var(--black);line-height:1.7}
.wrap{max-width:900px;margin:0 auto;padding:20px}
header{background:var(--blue);color:#fff;padding:30px 36px;border-radius:14px;margin-bottom:28px}
header h1{font-size:2rem} header p{opacity:.8;margin-top:6px}
.card{background:var(--card);border-radius:14px;padding:24px 28px;margin-bottom:20px;border-left:6px solid var(--blue-mid)}
.card h2{color:var(--blue);font-size:1.2rem;margin-bottom:10px}
ol{padding-left:22px} ol li{margin-bottom:8px}
ol li a{color:var(--blue);text-decoration:none;font-weight:600;font-size:1.05rem}
ol li a:hover{text-decoration:underline}
ol li .desc{color:var(--grey);font-size:.9rem}
.phase-label{background:var(--blue);color:#fff;padding:2px 10px;border-radius:10px;font-size:.75rem;font-weight:700;margin-left:8px}
.phase-label.p0{background:var(--green)}
.phase-label.p1{background:var(--blue-mid)}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>Code Walkthrough - Master Index</h1>
<p>29 files, explained line by line against the current code. Read them in order.</p>
</header>

<div class="card">
<h2>Phase 0 - Environment &amp; Setup (Files 1-8)</h2>
<ol>
<li><a href="01-env.html">.env</a> <span class="phase-label p0">P0</span><br><span class="desc">Runtime settings: browser storage, log level, rate limits, retries.</span></li>
<li><a href="02-gitignore.html">.gitignore</a> <span class="phase-label p0">P0</span><br><span class="desc">What NOT to commit: secrets, database, cache files.</span></li>
<li><a href="03-requirements.html">requirements.txt</a> <span class="phase-label p0">P0</span><br><span class="desc">The 11 Python libraries the project depends on.</span></li>
<li><a href="04-routes-yaml.html">config/routes.yaml</a> <span class="phase-label p0">P0</span><br><span class="desc">4 cities, 12 directional routes, 3 lead windows, index settings.</span></li>
<li><a href="05-scraper-yaml.html">config/scraper.yaml</a> <span class="phase-label p0">P0</span><br><span class="desc">Rate limits, retry policy, browser settings, timeouts.</span></li>
<li><a href="06-indexer-yaml.html">config/indexer.yaml</a> <span class="phase-label p0">P0</span><br><span class="desc">Index formula settings, route weights, outlier detection rules.</span></li>
<li><a href="07-schemas-py.html">src/models/schemas.py</a> <span class="phase-label p0">P0</span><br><span class="desc">Pydantic models: FlightRecord, RouteConfig, CityConfig, IndexEntry.</span></li>
<li><a href="08-database-py.html">src/storage/database.py</a> <span class="phase-label p0">P0</span><br><span class="desc">SQLite layer: 5 table definitions, init and connection helpers.</span></li>
</ol>
</div>

<div class="card">
<h2>Phase 1 - The Scraper (Files 9-12, 16, 21)</h2>
<ol start="9">
<li><a href="09-base-py.html">src/scraper/base.py</a> <span class="phase-label p1">P1</span><br><span class="desc">Abstract contract every scraper must implement.</span></li>
<li><a href="10-driver-py.html">src/scraper/driver.py</a> <span class="phase-label p1">P1</span><br><span class="desc">Playwright browser launcher with guaranteed cleanup.</span></li>
<li><a href="11-google-flights-py.html">src/scraper/google_flights.py</a> <span class="phase-label p1">P1</span><br><span class="desc">Core scraper: URL builder, aria-label parsing, rate limit + retries. (314 lines)</span></li>
<li><a href="12-run-scrape-py.html">src/scraper/run_scrape.py</a> <span class="phase-label p1">P1</span><br><span class="desc">Batch runner: 12 routes x 3 windows, saves to raw_flights.</span></li>
<li><a href="16-run-smoke-py.html">src/scraper/run_smoke.py</a> <span class="phase-label p1">P1</span><br><span class="desc">One-route smoke test of the live scraper, prints + persists results.</span></li>
<li><a href="21-test-scraper-py.html">src/test_scraper.py</a> <span class="phase-label p1">P1</span><br><span class="desc">Duplicate single-route scraper test used during development.</span></li>
</ol>
</div>

<div class="card">
<h2>Phase 2 - Data Cleaning (Files 13, 17-20)</h2>
<ol start="13">
<li><a href="13-clean-py.html">src/cleaner/clean.py</a> <span class="phase-label p1">P2</span><br><span class="desc">Production cleaner: dedup, nulls, IQR outliers, quality score - raw_flights to cleaned_flights.</span></li>
<li><a href="17-pipeline-py.html">src/cleaner/pipeline.py</a> <span class="phase-label p1">P2</span><br><span class="desc">Modular cleaner functions (cast, dedup, filter, nulls, outliers) with SQLAlchemy writer.</span></li>
<li><a href="18-mock-data-py.html">src/cleaner/mock_data.py</a> <span class="phase-label p1">P2</span><br><span class="desc">Fake DataFrames/databases engineered with real-world defects for testing.</span></li>
<li><a href="19-check-db-py.html">src/cleaner/check_db.py</a> <span class="phase-label p1">P2</span><br><span class="desc">Diagnostics: raw vs cleaned counts, outliers, nulls, fare summary.</span></li>
<li><a href="20-test-run-py.html">src/cleaner/test_run.py</a> <span class="phase-label p1">P2</span><br><span class="desc">Runs the pipeline on mock data and prints a validation summary.</span></li>
</ol>
</div>

<div class="card">
<h2>Phase 3 - The Index Builder (Files 14-15, 22-29)</h2>
<ol start="14">
<li><a href="14-run-index-py.html">src/indexer/run_index.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Entry point: reads cleaned flights, builds daily/weekly/monthly indices, writes to SQLite.</span></li>
<li><a href="15-api-index-py.html">src/indexer/api_index.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Laspeyres-style weighted basket math for route + aggregate indices.</span></li>
<li><a href="22-test-indexer-py.html">tests/test_indexer.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Offline pytest suite for the index math using a CSV fixture.</span></li>
<li><a href="23-estimators-py.html">src/indexer/estimators.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Pluggable aggregation estimators: weighted mean, trimmed mean, weighted median.</span></li>
<li><a href="24-synthetic-py.html">src/indexer/synthetic.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Deterministic synthetic cleaned-flights generator for estimator research.</span></li>
<li><a href="25-metrics-py.html">src/indexer/metrics.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Stability metrics: day-to-day volatility, route sensitivity, weight elasticity.</span></li>
<li><a href="26-report-py.html">src/indexer/report.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Empirical estimator comparison report: aggregation, rolling, route sensitivity.</span></li>
<li><a href="27-test-estimators-py.html">tests/test_estimators.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Unit tests for the weighted-mean, trimmed-mean, and weighted-median estimators.</span></li>
<li><a href="28-test-metrics-py.html">tests/test_metrics.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Unit tests for stability stats, synthetic data, and estimator comparison.</span></li>
<li><a href="29-price-predictor-py.html">src/models/price_predictor.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Standalone TensorFlow fare-direction classifier (Phase 2 model, not in MVP).</span></li>
</ol>
</div>

<div class="card" style="border-left-color:var(--green);">
<h2 style="color:var(--green);">How to Use These Walkthroughs</h2>
<p>Open any file above. Each walkthrough shows every line of code with a plain-English explanation beneath it. Read them in order (1-29) for the best learning experience.</p>
<p style="margin-top:10px;">Files 1-8 are Phase 0 (setup). Files 9-12, 16, 21 are Phase 1 (scraper). Files 13, 17-20 are Phase 2 (cleaning). Files 14-15, 22-29 are Phase 3 (the APIx index).</p>
</div>
</div>
</body>
</html>"""


def main() -> None:
    print(f"Building {len(FILES)} walkthroughs in {OUT_DIR}")
    for spec in FILES:
        build_one(spec)
    (OUT_DIR / "index.html").write_text(INDEX_TEMPLATE, encoding="utf-8")
    print(f"index.html written ({len(FILES)} entries)")
    print("Done.")


if __name__ == "__main__":
    main()