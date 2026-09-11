"""Generate line-by-line HTML walkthrough for each project file."""
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "walkthroughs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Shared CSS template ──────────────────────────────────────────────────
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

def make_html(title, file_path, lines_with_explanations, prev_file=None, next_file=None):
    """Build one walkthrough HTML file."""
    body_lines = []
    for i, (code, explanation) in enumerate(lines_with_explanations, 1):
        code_escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        body_lines.append(f'''<div class="line-block">
<div class="line-header">Line {i}</div>
<div class="line-code">{code_escaped}</div>
<div class="line-explain">{explanation}</div>
</div>''')

    nav_html = '<div class="nav">'
    if prev_file:
        nav_html += f'<a href="{prev_file}">&larr; Previous</a>'
    else:
        nav_html += '<span></span>'
    if next_file:
        nav_html += f'<a href="{next_file}">Next &rarr;</a>'
    nav_html += '</div>'

    html = f"""<!DOCTYPE html>
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
<div class="sub">{file_path}</div>
</header>
{nav_html}
<div class="card">
<h2>File Overview</h2>
<p>Below is every line of this file with an explanation of what it does and why.</p>
</div>
{"".join(body_lines)}
<div class="card">
<h2>Summary</h2>
<p>This file has <strong>{len(lines_with_explanations)} lines</strong>.</p>
</div>
{nav_html}
</div>
</body>
</html>"""
    return html


# ══════════════════════════════════════════════════════════════════════════
# FILE 1: .env
# ══════════════════════════════════════════════════════════════════════════
env_lines = [
    ("# Playwright browser storage location", "A comment line. The <code>#</code> symbol means this line is ignored by the computer. It's just a note for humans reading the file."),
    ("PLAYWRIGHT_BROWSERS_PATH=0", "Tells Playwright where to store browser files. The value <code>0</code> means 'use the default location inside the project folder.' This way the browser files live with your project, not scattered across your system."),
    ("", "Empty line. Used to separate sections for readability."),
    ("# Logging level: DEBUG, INFO, WARNING, ERROR", "Comment explaining the possible values for the next setting. Logging level controls how much detail the program prints while running."),
    ("LOG_LEVEL=INFO", "Sets the program to print <strong>Info-level</strong> messages: things like 'scrape started,' '120 flights saved.' <code>DEBUG</code> would be much more verbose. <code>WARNING</code> would only show problems."),
    ("", "Empty line separating sections."),
    ("# Scraper settings", "Comment labeling the scraper configuration section."),
    ("MAX_REQUESTS_PER_HOUR=60", "Speed limit: the scraper will make <strong>at most 60 requests per hour</strong> to Google Flights. That's one every minute. This prevents Google from blocking us."),
    ("REQUEST_DELAY_MIN=3", "Minimum wait time (in seconds) between consecutive requests. The scraper will wait at least 3 seconds."),
    ("REQUEST_DELAY_MAX=8", "Maximum wait time between requests. The scraper picks a <strong>random</strong> delay between 3 and 8 seconds to look like a human."),
    ("MAX_RETRIES=3", "If a request fails (page doesn't load), the scraper will try up to <strong>3 times</strong> before giving up on that route."),
]

html = make_html("Walkthrough 1: .env", ".env", env_lines, next_file="02-gitignore.html")
(OUT_DIR / "01-env.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 2: .gitignore
# ══════════════════════════════════════════════════════════════════════════
gitignore_lines = [
    ("# Python", "Section header comment: these patterns relate to Python artifacts."),
    ("__pycache__/", "Python automatically creates a folder called <code>__pycache__</code> to store compiled versions of your .py files. This speeds up imports but the files are computer-generated, so we don't want them in version control."),
    ("*.py[cod]", "The <code>*</code> is a wildcard. This matches any file ending in <code>.pyc</code>, <code>.pyo</code>, or <code>.pyd</code> - all Python compiled files."),
    ("*.pyo", "Catches Python optimized files specifically (redundant with above but explicit)."),
    ("*.egg-info/", "If you ever package this project for distribution, Python creates an <code>.egg-info</code> folder. It's auto-generated metadata."),
    ("dist/", "The <code>dist</code> folder holds distributable packages. Auto-generated when you build the project."),
    ("build/", "Similar to dist - temporary build artifacts go here."),
    ("*.egg", "Egg files are an older Python packaging format. Rarely seen now but safe to ignore."),
    ("", "Empty line separating sections."),
    ("# Environment", "Section: environment and secrets files."),
    (".env", "Our secrets file! It contains settings we don't want to share publicly. If someone puts this on GitHub, anyone can see our configuration."),
    ("venv/", "The <code>venv</code> folder is where Python installs packages locally for this project. It can be huge (hundreds of MB) and is recreated with <code>pip install</code>."),
    (".venv/", "Alternative name some people use for the virtual environment folder."),
    ("", "Empty line."),
    ("# Database", "Section: database files."),
    ("data/*.db", "Any <code>.db</code> file inside the <code>data/</code> folder. Our SQLite database will be at <code>data/apix.db</code>. It's generated data that can be recreated by running the scraper."),
    ("", "Empty line."),
    ("# IDE", "Section: code editor files."),
    (".vscode/", "VS Code creates this folder to store workspace-specific settings. Different developers use different settings, so we don't share it."),
    (".idea/", "JetBrains IDEs (PyCharm) create this folder. Same reason as .vscode."),
    ("*.swp", "Vim editor creates .swp files when you have a file open. They're temporary."),
    ("", "Empty line."),
    ("# OS", "Section: operating system junk files."),
    ("Thumbs.db", "Windows creates this file in every folder to cache thumbnail images. It's useless to others."),
    ("Desktop.ini", "Windows stores folder display settings here. Auto-generated by Windows."),
    (".DS_Store", "macOS creates this in every folder to remember icon positions. Useless to others."),
    ("", "Empty line."),
    ("# Secrets", "Section: security-sensitive files."),
    ("*.pem", "PEM files often contain SSL certificates or private keys. Never share these."),
    ("*.key", "Private key files. Sharing these would let others impersonate your server."),
]

html = make_html("Walkthrough 2: .gitignore", ".gitignore", gitignore_lines,
                 prev_file="01-env.html", next_file="03-requirements.html")
(OUT_DIR / "02-gitignore.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 3: requirements.txt
# ══════════════════════════════════════════════════════════════════════════
req_lines = [
    ("playwright>=1.40.0", "<strong>Playwright</strong> - the browser automation library. It lets our Python code control a real Chrome browser: open pages, click buttons, read text. The <code>>=1.40.0</code> means 'version 1.40.0 or newer.'"),
    ("pandas>=2.1.0", "<strong>Pandas</strong> - the data cleaning and analysis library. Think of it as Excel for Python. We'll use it to clean scraped flight data, remove duplicates, handle missing values."),
    ("numpy>=1.26.0", "<strong>NumPy</strong> - math library for numerical operations. Pandas is built on top of NumPy. We'll use it for statistical calculations like outlier detection."),
    ("pydantic>=2.5.0", "<strong>Pydantic</strong> - data validation library. It defines 'schemas' (templates) that our data must match. If a scraped flight record is missing the price, Pydantic rejects it before it enters our database."),
    ("pyyaml>=6.0", "<strong>PyYAML</strong> - reads YAML config files. Our <code>routes.yaml</code>, <code>scraper.yaml</code>, and <code>indexer.yaml</code> are all YAML files that this library parses into Python dictionaries."),
    ("apscheduler>=3.10.0", "<strong>APScheduler</strong> - runs code on a schedule. We'll use it to trigger the scraper automatically every day at a set time (like 6 AM)."),
    ("streamlit>=1.29.0", "<strong>Streamlit</strong> - creates web dashboards using only Python. No HTML/CSS/JS needed. We'll use it to display charts of flight price trends."),
    ("plotly>=5.18.0", "<strong>Plotly</strong> - makes interactive charts (zoom, hover, click). Streamlit uses Plotly for its graphing. We'll make line charts, heatmaps, and bar charts."),
    ("python-dotenv>=1.0.0", "<strong>python-dotenv</strong> - reads our <code>.env</code> file and loads the settings into Python. Without this, our <code>.env</code> values wouldn't be accessible in code."),
    ("pytest>=7.4.0", "<strong>pytest</strong> - the testing framework. We write test functions that verify our code works correctly. <code>pytest</code> runs them all and reports which passed/failed."),
    ("pytest-cov>=4.1.0", "<strong>pytest-cov</strong> - a pytest plugin that measures <strong>code coverage</strong>: what percentage of our code was exercised by tests. Helps ensure we're testing enough."),
]

html = make_html("Walkthrough 3: requirements.txt", "requirements.txt", req_lines,
                 prev_file="02-gitignore.html", next_file="04-routes-yaml.html")
(OUT_DIR / "03-requirements.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 4: config/routes.yaml
# ══════════════════════════════════════════════════════════════════════════
routes_lines = [
    ("# -- City Definitions --", "Comment: this section defines the cities we'll track."),
    ("# weight = DGCA passenger traffic share (approximate)", "Explains that 'weight' represents what percentage of India's air traffic each city handles, based on DGCA data."),
    ("cities:", "Top-level YAML key. Everything below this (indented) defines our cities."),
    ("  DEL:", "Defines the first city: Delhi (IATA code DEL). Indentation matters in YAML - this is a child of 'cities.'"),
    ('    name: "New Delhi"', "Human-readable name for display on charts and the dashboard."),
    ('    code: "DEL"', "The 3-letter IATA airport code. Used in route names like 'DEL-BOM.'"),
    ("    weight: 0.30", "Delhi handles ~30% of our basket's air traffic. This weight is used when calculating the overall airfare index."),
    ("  BOM:", "Second city: Mumbai."),
    ('    name: "Mumbai"', "Full name."),
    ('    code: "BOM"', "IATA code for Mumbai (Chhatrapati Shivaji Maharaj airport)."),
    ("    weight: 0.25", "Mumbai gets 25% weight."),
    ("  BLR:", "Third city: Bengaluru."),
    ('    name: "Bengaluru"', "Full name."),
    ('    code: "BLR"', "IATA code for Bengaluru (Kempegowda airport)."),
    ("    weight: 0.25", "Bengaluru gets 25% weight."),
    ("  MAA:", "Fourth city: Chennai."),
    ('    name: "Chennai"', "Full name."),
    ('    code: "MAA"', "IATA code for Chennai (Meenambakkam airport)."),
    ("    weight: 0.20", "Chennai gets 20% weight. Total weights sum to 1.00."),
    ("", "Empty line."),
    ("# -- Route Basket --", "Comment: these are the flight routes we'll scrape."),
    ("# 12 directional routes (6 pairs x 2 directions)", "We have 6 city pairs, each in both directions (DEL->BOM and BOM->DEL), giving 12 routes total."),
    ("routes:", "Top-level key listing all routes."),
    ("  - origin: DEL", "First route starts from Delhi. The dash (-) means this is an item in a list."),
    ("    dest: BOM", "Destination is Mumbai. Together: Delhi to Mumbai."),
    ("  - origin: BOM", "Second route: Mumbai to Delhi (reverse direction)."),
    ("    dest: DEL", "Destination Delhi."),
    ("  - origin: DEL", "Third route: Delhi to Bengaluru."),
    ("    dest: BLR", "Destination Bengaluru."),
    ("  - origin: BLR", "Fourth: Bengaluru to Delhi."),
    ("    dest: DEL", ""),
    ("  - origin: DEL", "Fifth: Delhi to Chennai."),
    ("    dest: MAA", ""),
    ("  - origin: MAA", "Sixth: Chennai to Delhi."),
    ("    dest: DEL", ""),
    ("  - origin: BOM", "Seventh: Mumbai to Bengaluru."),
    ("    dest: BLR", ""),
    ("  - origin: BLR", "Eighth: Bengaluru to Mumbai."),
    ("    dest: BOM", ""),
    ("  - origin: BOM", "Ninth: Mumbai to Chennai."),
    ("    dest: MAA", ""),
    ("  - origin: MAA", "Tenth: Chennai to Mumbai."),
    ("    dest: BOM", ""),
    ("  - origin: BLR", "Eleventh: Bengaluru to Chennai."),
    ("    dest: MAA", ""),
    ("  - origin: MAA", "Twelfth: Chennai to Bengaluru."),
    ("    dest: BLR", ""),
    ("", "Empty line."),
    ("# -- Advance-Purchase Windows --", "Comment: how far ahead of travel date to search."),
    ("# Number of days before departure to search", "Clarification of what the numbers mean."),
    ("lead_windows:", "List of lead-time windows."),
    ("  - 1     # T+1  (last-minute)", "Search for flights departing <strong>1 day from now</strong>. These are expensive last-minute fares."),
    ("  - 7     # T+7  (one week out)", "Search for flights departing <strong>7 days from now</strong>. A common booking window."),
    ("  - 30    # T+30 (one month out)", "Search for flights departing <strong>30 days from now</strong>. Usually cheaper advance-purchase fares."),
    ("", "Empty line."),
    ("# -- Index Settings --", "Comment: settings for the airfare index calculation."),
    ("index:", "Top-level key for index configuration."),
    ('  base_period: "first_available"', "The index starts at 100 on the first day we have data. All future days are compared to this baseline."),
    ("  round_to: 2", "Round index values to 2 decimal places (e.g., 111.04)."),
]

html = make_html("Walkthrough 4: config/routes.yaml", "config/routes.yaml", routes_lines,
                 prev_file="03-requirements.html", next_file="05-scraper-yaml.html")
(OUT_DIR / "04-routes-yaml.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 5: config/scraper.yaml
# ══════════════════════════════════════════════════════════════════════════
scraper_yaml_lines = [
    ("# -- Scraper Settings --", "Comment: all settings that control how the web scraper behaves."),
    ("scraper:", "Top-level YAML key. All scraper settings are children of this."),
    ("  # Rate limiting", "Comment: speed limits to avoid being blocked."),
    ("  max_requests_per_hour: 60", "Hard limit: at most <strong>60 HTTP requests per hour</strong>. One request per minute on average."),
    ("  delay_between_requests:", "Sub-section defining the random delay range."),
    ("    min_seconds: 3", "Wait at least <strong>3 seconds</strong> between requests."),
    ("    max_seconds: 8", "Wait at most <strong>8 seconds</strong>. A random value between 3-8 is picked each time."),
    ("", "Empty line."),
    ("  # Retry policy", "Comment: what happens when requests fail."),
    ("  max_retries: 3", "If a page fails to load, try <strong>up to 3 times</strong> before giving up."),
    ("  backoff_multiplier: 2     # 3s, 6s, 12s", "Each retry waits <strong>twice as long</strong> as the previous one. 1st retry: 3s. 2nd: 6s. 3rd: 12s. This is called 'exponential backoff.'"),
    ("", "Empty line."),
    ("  # Browser settings", "Comment: how the invisible browser should behave."),
    ("  headless: true", "Run the browser <strong>without a visible window</strong>. The browser runs in the background. Set to false to watch the scraper work (useful for debugging)."),
    ("  viewport_width: 1280", "Browser window width in pixels. 1280 is a standard desktop width."),
    ("  viewport_height: 900", "Browser window height in pixels. Together with width, this simulates a typical monitor."),
    ('  user_agent: "Mozilla/5.0 ..."', "The browser identifies itself to websites using a 'user agent' string. This one mimics Chrome on Windows. Some websites block requests that don't look like real browsers."),
    ("", "Empty line."),
    ("  # Timeouts (seconds)", "Comment: how long to wait before giving up."),
    ("  page_load_timeout: 30", "If a page doesn't fully load within <strong>30 seconds</strong>, consider it failed."),
    ("  element_wait_timeout: 15", "If a specific element (like a flight card) doesn't appear within <strong>15 seconds</strong>, stop waiting."),
]

html = make_html("Walkthrough 5: config/scraper.yaml", "config/scraper.yaml", scraper_yaml_lines,
                 prev_file="04-routes-yaml.html", next_file="06-indexer-yaml.html")
(OUT_DIR / "05-scraper-yaml.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 6: config/indexer.yaml
# ══════════════════════════════════════════════════════════════════════════
indexer_lines = [
    ("# -- Index Builder Settings --", "Comment: settings for how the airfare index number is calculated."),
    ("index:", "Top-level key for index-related settings."),
    ('  base_period: "first_available"', "The index = 100 on the first day with valid data. All other days are expressed relative to this baseline. If day 1 average fare is Rs.5000 and day 5 is Rs.5500, day 5 index = (5500/5000)*100 = 110."),
    ("  round_to: 2", "Round the final index number to <strong>2 decimal places</strong>. So you'd see 111.04, not 111.04392817..."),
    ("  min_data_points: 1", "The index is written from the <strong>first day</strong> with data. Set to 1 during development so values appear immediately; the original PRD wanted 30 days before the index is 'statistically valid'."),
    ("", "Empty line."),
    ("  # -- Route basket weights (DGCA traffic share approximation) --", "Comment: each directional route gets a weight proportional to real passenger traffic. 12 weights, one per direction."),
    ("  weights:", "Nested key: the weight map the index builder reads and normalises to sum 1.0."),
    ("    DEL-BOM: 0.10", "Delhi -> Mumbai carries 10% of the basket's passenger traffic."),
    ("    BOM-DEL: 0.10", "Mumbai -> Delhi (reverse direction), also 10%."),
    ("    DEL-BLR: 0.09", "Delhi -> Bengaluru, 9%."),
    ("    BLR-DEL: 0.09", "Bengaluru -> Delhi, 9%."),
    ("    DEL-MAA: 0.06", "Delhi -> Chennai, 6%."),
    ("    MAA-DEL: 0.06", "Chennai -> Delhi, 6%."),
    ("    BOM-BLR: 0.10", "Mumbai -> Bengaluru, 10%."),
    ("    BLR-BOM: 0.10", "Bengaluru -> Mumbai, 10%."),
    ("    BOM-MAA: 0.08", "Mumbai -> Chennai, 8%."),
    ("    MAA-BOM: 0.08", "Chennai -> Mumbai, 8%."),
    ("    BLR-MAA: 0.07", "Bengaluru -> Chennai, 7%."),
    ("    MAA-BLR: 0.07", "Chennai -> Bengaluru, 7%. All 12 weights sum to 1.00."),
    ("", "Empty line."),
    ("# -- Outlier Detection --", "Comment: how to identify and handle bad data points."),
    ("cleaning:", "Top-level key for data cleaning settings."),
    ('  outlier_method: "iqr"', "Use the <strong>IQR method</strong> to detect outliers. IQR = Interquartile Range. Points beyond 1.5x the IQR from Q1 or Q3 are flagged as outliers. Alternative: 'zscore'."),
    ("  iqr_multiplier: 1.5", "The standard multiplier. A fare is an outlier if it's below Q1-1.5*IQR or above Q3+1.5*IQR. Using 3.0 would be more lenient."),
    ("  zscore_threshold: 3.0", "Only used if method='zscore'. A fare is an outlier if its Z-score is above 3.0 (i.e., more than 3 standard deviations from the mean)."),
    ('  null_fare_action: "drop"', "If a flight record has <strong>no fare value</strong>, simply remove it. Alternative: 'forward_fill' would use the previous flight's fare as an estimate."),
]

html = make_html("Walkthrough 6: config/indexer.yaml", "config/indexer.yaml", indexer_lines,
                 prev_file="05-scraper-yaml.html", next_file="07-schemas-py.html")
(OUT_DIR / "06-indexer-yaml.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 7: src/models/schemas.py
# ══════════════════════════════════════════════════════════════════════════
schemas_lines = [
    ("from datetime import datetime", "Imports Python's <code>datetime</code> class, which handles dates and times. We'll use it for departure/arrival times and scrape timestamps."),
    ("from pydantic import BaseModel, Field", "<code>BaseModel</code> is the parent class for all our data models. <code>Field</code> lets us add validation rules to each field (like 'must be positive')."),
    ("", "Empty line."),
    ("", "Empty line."),
    ("class FlightRecord(BaseModel):", "Defines a new class called <code>FlightRecord</code> that inherits from Pydantic's <code>BaseModel</code>. Every scraped flight must match this shape."),
    ('    """One scraped flight - the raw unit of data we collect."""', "A docstring: explains what this class represents. Triple quotes <code>\"\"\"</code> denote multi-line comments in Python."),
    ("", "Empty line."),
    ("    route: str = Field(..., description=\"e.g. DEL-BOM\")", "<code>route</code> is a string like 'DEL-BOM'. The <code>...</code> means it's <strong>required</strong> (no default value)."),
    ("    origin: str = Field(..., min_length=3, max_length=3)", "Origin airport code. Must be exactly 3 characters (like 'DEL'). Pydantic enforces this automatically."),
    ("    dest: str = Field(..., min_length=3, max_length=3)", "Destination airport code. Same 3-character validation."),
    ("    carrier: str = Field(..., description=\"e.g. IndiGo\")", "Airline name. Required string."),
    ("    flight_no: str = Field(..., description=\"e.g. 6E-201\")", "Flight number. Required string."),
    ("    depart_time: datetime", "Departure time. Required datetime value."),
    ("    arrive_time: datetime", "Arrival time. Required datetime value."),
    ("    duration_mins: int = Field(..., ge=0)", "Flight duration in minutes. Must be an integer >= 0 (can't be negative)."),
    ("    stops: int = Field(..., ge=0, le=5)", "Number of stops. Must be between 0 and 5. A flight can't have negative stops or more than 5."),
    ("    base_fare: float = Field(default=0.0, ge=0)", "Base fare before taxes. Defaults to 0.0 if not available. Must be >= 0."),
    ("    taxes: float = Field(default=0.0, ge=0)", "Tax amount. Defaults to 0.0. Must be >= 0."),
    ("    total_fare: float = Field(..., gt=0)", "Total price the passenger pays. Required and must be <strong>greater than 0</strong> (a free flight doesn't make sense for our index)."),
    ('    currency: str = Field(default="INR", max_length=3)', "Currency code. Defaults to 'INR' (Indian Rupee). Max 3 characters per ISO standard."),
    ("    lead_window_days: int = Field(..., ge=1, le=90)", "How many days before departure this fare is for. Must be between 1 and 90 days."),
    ("    scrape_timestamp: datetime = Field(default_factory=datetime.now)", "When this record was scraped. <code>default_factory=datetime.now</code> means: if not provided, automatically use the current time."),
    ("", "Empty line."),
    ("", "Empty line."),
    ("class RouteConfig(BaseModel):", "A simpler model representing one flight route."),
    ('    """One route from routes.yaml."""', "Docstring."),
    ("", "Empty line."),
    ("    origin: str", "Origin city code."),
    ("    dest: str", "Destination city code."),
    ("", "Empty line."),
    ("", "Empty line."),
    ("class CityConfig(BaseModel):", "Model for a city entry from routes.yaml."),
    ('    """One city from routes.yaml."""', "Docstring."),
    ("", "Empty line."),
    ("    name: str", "City's full name (e.g., 'New Delhi')."),
    ("    code: str", "Airport code (e.g., 'DEL')."),
    ("    weight: float = Field(..., ge=0, le=1)", "Traffic weight. Required. Must be between 0 and 1 (representing a percentage)."),
    ("", "Empty line."),
    ("", "Empty line."),
    ("class IndexEntry(BaseModel):", "Model for one row in the daily/weekly/monthly index tables."),
    ('    """One row in the daily_index / weekly_index / monthly_index tables."""', "Docstring."),
    ("", "Empty line."),
    ("    index_date: str", "The date of this index value (e.g., '2026-09-04')."),
    ("    lead_window_days: int", "Which advance-purchase window this entry belongs to (1, 7, or 30). Added in Phase 3 so each lead window gets its own index."),
    ("    route: str", "Which route this index entry is for."),
    ("    weight: float", "This route's weight in the basket."),
    ("    route_price: float", "Lowest fare on this route on this date."),
    ("    route_index: float", "This route's index value (route_price / base_price * 100)."),
    ("    aggregate_index: float", "The overall weighted index across all routes."),
    ("    base_period: str", "Which date was used as the base period (index=100)."),
]

html = make_html("Walkthrough 7: src/models/schemas.py", "src/models/schemas.py", schemas_lines,
                 prev_file="06-indexer-yaml.html", next_file="08-database-py.html")
(OUT_DIR / "07-schemas-py.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 8: src/storage/database.py
# ══════════════════════════════════════════════════════════════════════════
db_lines = [
    ("import sqlite3", "Imports Python's built-in SQLite module. SQLite is a database that stores everything in a single file — no server needed."),
    ("from pathlib import Path", "Imports <code>Path</code>, a modern way to handle file paths that works on Windows, Mac, and Linux."),
    ("", "Empty line."),
    ("DB_PATH = Path(__file__).resolve().parent.parent.parent / \"data\" / \"apix.db\"", "Calculates the full path to our database file. <code>__file__</code> is this file's location. <code>.parent.parent.parent</code> goes up 3 folders to the project root. Then we go into <code>data/apix.db</code>."),
    ("", "Empty line."),
    ("RAW_FLIGHTS = \"\"\"", "Starts a multi-line string that contains the SQL command to create the raw_flights table."),
    ("CREATE TABLE IF NOT EXISTS raw_flights (", "<code>CREATE TABLE IF NOT EXISTS</code> means: create this table only if it doesn't already exist. Prevents errors on re-runs."),
    ("    id INTEGER PRIMARY KEY AUTOINCREMENT,", "Unique ID for each row. Auto-increments: 1, 2, 3... No two rows share an ID."),
    ("    scrape_date TEXT NOT NULL,", "The date when this data was scraped (e.g., '2026-09-04'). Required (<code>NOT NULL</code>)."),
    ("    route TEXT NOT NULL,", "Route code like 'DEL-BOM'. Required."),
    ("    origin TEXT NOT NULL,", "Origin airport code. Required."),
    ("    dest TEXT NOT NULL,", "Destination airport code. Required."),
    ("    carrier TEXT,", "Airline name. Optional (could be unknown)."),
    ("    flight_no TEXT,", "Flight number. Optional."),
    ("    depart_time TEXT,", "Departure time as text (ISO format)."),
    ("    arrive_time TEXT,", "Arrival time as text."),
    ("    duration_mins INTEGER,", "Flight duration in minutes."),
    ("    stops INTEGER,", "Number of stops."),
    ("    base_fare REAL,", "Base fare as a decimal number. <code>REAL</code> = floating point."),
    ("    taxes REAL,", "Tax amount."),
    ("    total_fare REAL,", "Total fare paid."),
    ("    currency TEXT DEFAULT 'INR',", "Currency. Defaults to 'INR' if not specified."),
    ("    lead_window_days INTEGER NOT NULL,", "How many days before departure. Required."),
    ("    scrape_timestamp TEXT NOT NULL", "Exact timestamp of when this row was created. Required."),
    (");", "Closes the CREATE TABLE statement."),
    ("\"\"\"", "Ends the multi-line string."),
    ("", "Empty line."),
    ("CLEANED_FLIGHTS = \"\"\"", "SQL for the cleaned_flights table. Same as raw_flights but with 4 extra columns:"),
    ("CREATE TABLE IF NOT EXISTS cleaned_flights (", "..."),
    ("    ...same columns as raw_flights...", "(All the same columns as raw_flights above)"),
    ("    quality_score REAL,", "A number (0-1) indicating data quality. Higher = better."),
    ("    is_outlier INTEGER DEFAULT 0,", "0 = normal fare. 1 = flagged as outlier. Defaults to 0."),
    ("    dedup_hash TEXT,", "A hash (fingerprint) used to detect duplicate entries."),
    ("    extraction_batch_id TEXT", "Identifies which scraping run produced this row."),
    (");", ""),
    ("\"\"\"", ""),
    ("", "Empty line."),
    ("DAILY_INDEX = \"\"\"", "SQL for the daily_index table."),
    ("CREATE TABLE IF NOT EXISTS daily_index (", "..."),
    ("    id INTEGER PRIMARY KEY AUTOINCREMENT,", "Auto-incrementing ID."),
    ("    index_date TEXT NOT NULL,", "The date this index was calculated."),
    ("    lead_window_days INTEGER NOT NULL,", "The advance-purchase window (1, 7, or 30) this index row is for. Added in Phase 3 so we keep a separate index per lead window."),
    ("    route TEXT NOT NULL,", "Which route."),
    ("    weight REAL,", "Route weight."),
    ("    route_price REAL,", "Lowest fare on this route."),
    ("    route_index REAL,", "Route's individual index value."),
    ("    aggregate_index REAL,", "Overall weighted index."),
    ("    base_period TEXT", "Base period date."),
    (");", ""),
    ("\"\"\"", ""),
    ("", "WEEKLY_INDEX and MONTHLY_INDEX are identical in structure to DAILY_INDEX (including lead_window_days) — just different table names for 7-day and 30-day rolling indices."),
    ("", "Empty lines separating the table definitions."),
    ("", ""),
    ("", ""),
    ("def init_db(db_path: Path | str | None = None) -> None:", "Defines a function that initializes the database. <code>db_path</code> can be a Path, a string, or None (uses default)."),
    ('    """Create all tables if they don\'t exist."""', "Docstring explaining the function."),
    ("    path = Path(db_path) if db_path else DB_PATH", "If a custom path was provided, use it. Otherwise, use the default DB_PATH."),
    ("    path.parent.mkdir(parents=True, exist_ok=True)", "Create the <code>data/</code> folder if it doesn't exist. <code>exist_ok=True</code> means don't error if it already exists."),
    ("", "Empty line."),
    ("    conn = sqlite3.connect(str(path))", "Open a connection to the SQLite database file. If the file doesn't exist, SQLite creates it."),
    ("    try:", "Start a try block: ensure we close the connection even if an error occurs."),
    ("        for ddl in [RAW_FLIGHTS, CLEANED_FLIGHTS, DAILY_INDEX, WEEKLY_INDEX, MONTHLY_INDEX]:", "Loop through all 5 table creation SQL statements."),
    ("            conn.execute(ddl)", "Execute each SQL statement against the database."),
    ("        conn.commit()", "Save all changes. Without this, the table creations would be lost."),
    ("    finally:", "The 'finally' block always runs, whether or not an error occurred."),
    ("        conn.close()", "Close the database connection. Important to avoid file locks."),
    ("", "Empty line."),
    ("", "Empty line."),
    ("def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:", "Returns an open database connection for other code to use."),
    ('    """Return a live connection to the database."""', "Docstring."),
    ("    path = Path(db_path) if db_path else DB_PATH", "Same path resolution logic as init_db."),
    ("    path.parent.mkdir(parents=True, exist_ok=True)", "Ensure folder exists."),
    ("    return sqlite3.connect(str(path))", "Return the open connection. Caller is responsible for closing it."),
    ("", "Empty line."),
    ("", "Empty line."),
    ('if __name__ == "__main__":', "This code only runs if you execute this file directly (e.g., <code>python database.py</code>). Not when it's imported by other files."),
    ("    init_db()", "Create all tables."),
    ('    print(f"Database created at: {DB_PATH}")', "Print confirmation with the full file path."),
]

html = make_html("Walkthrough 8: src/storage/database.py", "src/storage/database.py", db_lines,
                 prev_file="07-schemas-py.html", next_file="09-base-py.html")
(OUT_DIR / "08-database-py.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 9: src/scraper/base.py
# ══════════════════════════════════════════════════════════════════════════
base_lines = [
    ("from abc import ABC, abstractmethod", "<code>ABC</code> stands for Abstract Base Class. <code>abstractmethod</code> marks methods that <strong>must</strong> be implemented by any class that inherits from this one. It's a contract."),
    ("from datetime import date", "Imports the <code>date</code> class for representing calendar dates (without time)."),
    ("", "Empty line."),
    ("from src.models.schemas import FlightRecord", "Imports our <code>FlightRecord</code> model. This tells us what the return type should look like."),
    ("", "Empty line."),
    ("", "Empty line."),
    ("class BaseScraper(ABC):", "Defines <code>BaseScraper</code> as an abstract class. You can't create a <code>BaseScraper()</code> directly — you must subclass it and implement its methods."),
    ('    """Every scraper must implement these methods."""', "Docstring: this class defines the interface that all scrapers follow."),
    ("", "Empty line."),
    ("    @abstractmethod", "Decorator that marks the next method as <strong>abstract</strong>: it has no implementation here, and any child class <strong>must</strong> provide its own version."),
    ("    async def fetch_flights(", "An <strong>async</strong> function (runs asynchronously, allowing other code to run while waiting for the network)."),
    ("        self, origin: str, dest: str, travel_date: date, lead_window_days: int", "Parameters: origin city code, destination code, travel date, and how many days ahead."),
    ("    ) -> list[FlightRecord]:", "Return type: a list of FlightRecord objects. Every scraper must return data in this format."),
    ('        """Scrape flights for one route on one date. Return validated records."""', "Docstring explaining what the method does."),
    ("        ...", "The <code>...</code> (ellipsis) means 'no implementation here.' The child class must fill this in."),
]

html = make_html("Walkthrough 9: src/scraper/base.py", "src/scraper/base.py", base_lines,
                 prev_file="08-database-py.html", next_file="10-driver-py.html")
(OUT_DIR / "09-base-py.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 10: src/scraper/driver.py
# ══════════════════════════════════════════════════════════════════════════
driver_lines = [
    ("import asyncio", "Python's built-in library for asynchronous programming. Lets us do network requests without blocking other operations."),
    ("import logging", "Python's logging module. Used to print status messages, warnings, and errors in a structured way."),
    ("from contextlib import asynccontextmanager", "Imports a decorator that creates <strong>async context managers</strong> — a pattern that guarantees setup and cleanup code run properly."),
    ("from pathlib import Path", "Modern file path handling."),
    ("", "Empty line."),
    ("import yaml", "Imports PyYAML for reading .yaml config files."),
    ("from playwright.async_api import async_playwright, Browser, BrowserContext, Page", "Imports Playwright's async API: <code>async_playwright</code> launches browsers, <code>Browser</code>/<code>BrowserContext</code>/<code>Page</code> are type hints."),
    ("", "Empty line."),
    ("CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / \"config\" / \"scraper.yaml\"", "Calculates the path to <code>config/scraper.yaml</code>. <code>__file__</code> is this file, go up 3 levels to project root, then into config/."),
    ("log = logging.getLogger(__name__)", "Creates a logger named after this module. Log messages will show 'src.scraper.driver' as the source."),
    ("", "Empty line."),
    ("", "Empty line."),
    ("def load_scraper_config() -> dict:", "A regular function (not async) that reads the scraper YAML config."),
    ("    with open(CONFIG_PATH) as f:", "Opens the config file. <code>with</code> ensures the file is closed even if an error occurs."),
    ('        return yaml.safe_load(f)["scraper"]', "<code>yaml.safe_load</code> parses YAML into a Python dictionary. <code>[\"scraper\"]</code> extracts the 'scraper' section."),
    ("", "Empty line."),
    ("", "Empty line."),
    ("@asynccontextmanager", "Decorator that turns this function into an async context manager. This enables the <code>async with</code> pattern."),
    ("async def create_browser_context(config: dict | None = None):", "Async function that launches a browser and yields a context. <code>config</code> is optional."),
    ('    """Launch headless Chromium and yield a fresh browser context.', "Docstring with usage example."),
    ("", "Empty line."),
    ("    Usage:", ""),
    ("        async with create_browser_context() as context:", ""),
    ("            page = await context.new_page()", ""),
    ('            await page.goto("https://google.com")', ""),
    ('    """', ""),
    ("    cfg = config or load_scraper_config()", "If no config was passed, load it from the YAML file."),
    ("", "Empty line."),
    ("    async with async_playwright() as pw:", "Starts Playwright. <code>pw</code> is the Playwright instance. The <code>async with</code> ensures Playwright is properly shut down when done."),
    ("        browser: Browser = await pw.chromium.launch(", "Launches a Chromium browser. Returns a Browser object."),
    ('            headless=cfg.get("headless", True),', "Run without a visible window (default: True)."),
    ("        )", ""),
    ("        context: BrowserContext = await browser.new_context(", "Creates an isolated browser session (like an incognito window)."),
    ("            viewport={", "Sets the browser window size."),
    ('                "width": cfg.get("viewport_width", 1280),', "Width: 1280 pixels."),
    ('                "height": cfg.get("viewport_height", 900),', "Height: 900 pixels."),
    ("            },", ""),
    ('            user_agent=cfg.get("user_agent"),', "Sets the user agent string so we look like a real browser."),
    ("        )", ""),
    ('        context.set_default_timeout(cfg.get("page_load_timeout", 30) * 1000)', "Default timeout for all page operations: 30 seconds (converted to milliseconds)."),
    ('        log.info("Browser context created")', "Log that the browser is ready."),
    ("        try:", "Start try block for cleanup."),
    ("            yield context", "This is the magic line: it gives the caller the browser context to use. Code pauses here until the caller is done."),
    ("        finally:", "Cleanup code that runs no matter what."),
    ("            await context.close()", "Close the browser context (all tabs)."),
    ("            await browser.close()", "Close the browser entirely."),
    ('            log.info("Browser closed")', "Log that cleanup is complete."),
]

html = make_html("Walkthrough 10: src/scraper/driver.py", "src/scraper/driver.py", driver_lines,
                 prev_file="09-base-py.html", next_file="11-google-flights-py.html")
(OUT_DIR / "10-driver-py.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 11: src/scraper/google_flights.py (largest file - 302 lines)
# ══════════════════════════════════════════════════════════════════════════
gf_lines = [
    ('"""Google Flights scraper using Playwright.', "Module docstring explaining the overall strategy."),
    ("", ""),
    ("Strategy: Google Flights embeds structured aria-label text on each flight card", ""),
    ("that contains price, carrier, times, duration, and stops in plain English.", ""),
    ("We parse this aria-label instead of hunting for fragile CSS class names.", ""),
    ('"""', ""),
    ("import asyncio", "Async programming support."),
    ("import logging", "For log messages."),
    ("import random", "For random delays between requests."),
    ("import re", "Regular expressions — pattern matching in text. Used to extract prices, times, etc."),
    ("from datetime import date, datetime, timedelta", "Date/time classes."),
    ("from pathlib import Path", "File path handling."),
    ("from urllib.parse import quote", "URL-encodes text for safe inclusion in URLs."),
    ("", ""),
    ("import yaml", "For reading YAML config."),
    ("from playwright.async_api import Page, TimeoutError as PwTimeout", "Playwright types. <code>PwTimeout</code> is the error raised when something takes too long."),
    ("", ""),
    ("from src.scraper.base import BaseScraper", "Our abstract scraper interface."),
    ("from src.scraper.driver import create_browser_context, load_scraper_config", "Browser launcher and config reader."),
    ("from src.models.schemas import FlightRecord", "Data model for a flight record."),
    ("", ""),
    ("log = logging.getLogger(__name__)", "Logger for this module."),
    ("", ""),
    ("ROUTES_PATH = Path(__file__).resolve().parent.parent.parent / \"config\" / \"routes.yaml\"", "Path to the routes config file."),
    ("", ""),
    ("CITY_NAMES = {", "Maps IATA codes to full city names for building Google Flights search URLs."),
    ('    "DEL": "New Delhi",', ""),
    ('    "BOM": "Mumbai",', ""),
    ('    "BLR": "Bengaluru",', ""),
    ('    "MAA": "Chennai",', ""),
    ("}", ""),
    ("", ""),
    ("", ""),
    ("def _load_routes() -> dict:", "Loads the routes.yaml file and returns it as a Python dictionary."),
    ("    with open(ROUTES_PATH) as f:", "Opens the file safely."),
    ("        return yaml.safe_load(f)", "Parses YAML into a dict."),
    ("", ""),
    ("", ""),
    ("class GoogleFlightsScraper(BaseScraper):", "The main scraper class. Inherits from BaseScraper, which means it <strong>must</strong> implement <code>fetch_flights()</code>."),
    ('    """Scrapes one-way flight results from Google Flights via aria-label parsing."""', "Docstring."),
    ("", ""),
    ("    def __init__(self, config: dict | None = None):", "Constructor: runs when you create a <code>GoogleFlightsScraper()</code>. Loads settings from config."),
    ("        self.cfg = config or load_scraper_config()", "Use provided config or load from YAML."),
    ('        self.max_retries = self.cfg.get("max_retries", 3)', "How many times to retry failed requests."),
    ('        self.backoff = self.cfg.get("backoff_multiplier", 2)', "Multiply wait time by this on each retry."),
    ('        self.delay_min = self.cfg["delay_between_requests"]["min_seconds"]', "Min delay between requests."),
    ('        self.delay_max = self.cfg["delay_between_requests"]["max_seconds"]', "Max delay between requests."),
    ("        self._hourly_count = 0", "Track how many requests made this hour."),
    ('        self._hour_limit = self.cfg.get("max_requests_per_hour", 60)', "Hard limit per hour."),
    ("", ""),
    ("    # -- Public API --", "Section divider comment."),
    ("", ""),
    ("    async def fetch_flights(", "The main public method (required by BaseScraper)."),
    ("        self,", ""),
    ("        origin: str,", "Origin city code."),
    ("        dest: str,", "Destination city code."),
    ("        travel_date: date,", "Date of travel."),
    ("        lead_window_days: int,", "How many days ahead."),
    ("    ) -> list[FlightRecord]:", "Returns a list of FlightRecord objects."),
    ("        base_delay = self.delay_min", "Starting delay for retries."),
    ("        last_err: Exception | None = None", "Track the last error for re-raising."),
    ("", ""),
    ("        for attempt in range(1, self.max_retries + 1):", "Loop: try up to 3 times."),
    ("            try:", "Attempt the scrape."),
    ("                await self._respect_rate_limit()", "Wait if we've hit our hourly limit."),
    ("                result = await self._scrape(origin, dest, travel_date, lead_window_days)", "Do the actual scraping."),
    ("                self._hourly_count += 1", "Count this request."),
    ("                return result", "Success! Return the flights."),
    ("            except PwTimeout as exc:", "If the page timed out..."),
    ("                last_err = exc", "Save the error."),
    ("                wait = base_delay * (self.backoff ** (attempt - 1))", "Calculate wait: 3s, 6s, 12s (exponential backoff)."),
    ('                log.warning(', "Log the timeout with details."),
    ('                    "Timeout on %s->%s (attempt %d/%d) - retrying in %.1fs",', ""),
    ("                    origin, dest, attempt, self.max_retries, wait,", ""),
    ("                )", ""),
    ("                await asyncio.sleep(wait)", "Wait before retrying."),
    ("            except Exception as exc:", "Any other error..."),
    ("                last_err = exc", "Save it."),
    ("                wait = base_delay * (self.backoff ** (attempt - 1))", "Same backoff logic."),
    ('                log.warning(', "Log it."),
    ('                    "Error on %s->%s (attempt %d/%d): %s - retrying in %.1fs",', ""),
    ("                    origin, dest, attempt, self.max_retries, exc, wait,", ""),
    ("                )", ""),
    ("                await asyncio.sleep(wait)", "Wait and retry."),
    ("", ""),
    ('        log.error("All %d attempts failed for %s->%s", self.max_retries, origin, dest)', "All retries exhausted. Log the failure."),
    ("        raise last_err  # type: ignore[misc]", "Re-raise the last error so the caller knows it failed."),
    ("", ""),
    ("    # -- Internal --", "Section divider."),
    ("", ""),
    ("    async def _respect_rate_limit(self) -> None:", "Checks if we've made too many requests and waits if needed."),
    ("        if self._hourly_count >= self._hour_limit:", "If we've hit the hourly cap..."),
    ('            log.warning("Rate limit reached (%d req/h). Waiting 60s.", self._hour_limit)', "Log a warning."),
    ("            await asyncio.sleep(60)", "Wait 60 seconds."),
    ("            self._hourly_count = 0", "Reset the counter."),
    ("        delay = random.uniform(self.delay_min, self.delay_max)", "Pick random delay between min and max seconds."),
    ("        await asyncio.sleep(delay)", "Wait that amount."),
    ("", ""),
    ("    async def _scrape(", "Internal method: does one complete scrape cycle."),
    ("        self, origin: str, dest: str, travel_date: date, lead_window_days: int,", ""),
    ("    ) -> list[FlightRecord]:", ""),
    ('        async with create_browser_context(self.cfg) as ctx:', "Open a browser. It will auto-close when done."),
    ("            page = await ctx.new_page()", "Open a new tab."),
    ("            url = self._build_url(origin, dest, travel_date)", "Build the Google Flights search URL."),
    ('            log.info("Navigating: %s", url)', "Log the URL."),
    ('            await page.goto(url, wait_until="domcontentloaded")', "Navigate. Wait until the HTML is loaded (but not necessarily all JavaScript)."),
    ("            await self._wait_for_results(page)", "Wait for flight cards to appear."),
    ("            await self._random_delay(3.0, 6.0)", "Extra wait for JavaScript to finish rendering."),
    ("", ""),
    ("            labels = await self._collect_aria_labels(page)", "Extract all flight description texts from the page."),
    ('            log.info("Collected %d aria-labels from page", len(labels))', "Log how many we found."),
    ("", ""),
    ("            records: list[FlightRecord] = []", "Empty list to collect parsed flights."),
    ("            for label in labels:", "For each flight description..."),
    ("                rec = self._parse_aria_label(", "Parse it into a FlightRecord."),
    ("                    label, origin, dest, travel_date, lead_window_days", ""),
    ("                )", ""),
    ("                if rec:", "If parsing succeeded..."),
    ("                    records.append(rec)", "Add to our results."),
    ("", ""),
    ('            log.info("Parsed %d valid flights for %s->%s", len(records), origin, dest)', "Log results."),
    ("            return records", "Return all parsed flights."),
    ("", ""),
    ("    # -- URL builder --", ""),
    ("", ""),
    ("    @staticmethod", "Static method: doesn't need 'self'. Called as <code>GoogleFlightsScraper._build_url(...)</code>."),
    ("    def _build_url(origin: str, dest: str, travel_date: date) -> str:", ""),
    ('        date_str = travel_date.strftime("%Y-%m-%d")', "Format date as '2026-09-11'."),
    ('        o_name = CITY_NAMES.get(origin, origin)', "Look up full city name. If not found, use the code as-is."),
    ('        d_name = CITY_NAMES.get(dest, dest)', "Same for destination."),
    ('        query = f"Flights from {o_name} to {d_name} on {date_str}"', "Build natural language query: 'Flights from New Delhi to Mumbai on 2026-09-11'."),
    ('        return f"https://www.google.com/travel/flights?q={quote(query)}&hl=en&curr=INR"', "URL-encode the query and build the full Google Flights URL."),
    ("", ""),
    ("    # -- Wait for results --", ""),
    ("", ""),
    ("    async def _wait_for_results(self, page: Page) -> None:", "Wait until flight result cards appear on the page."),
    ("        selectors = [", "Try multiple CSS selectors in case Google changes their class names."),
    ('            "li.pIav2d",', "Primary selector (matches the flight card list items)."),
    ('            \'div[role=link][aria-label*=flight]\',', "Fallback: any div with role=link that has 'flight' in its aria-label."),
    ('            \'li[class*=pIav2d]\',', "Partial class match (in case Google adds extra classes)."),
    ('            \'ul[role=list] > li\',', "Any list item inside a role=list element."),
    ("        ]", ""),
    ("        for sel in selectors:", "Try each selector."),
    ("            try:", ""),
    ("                await page.wait_for_selector(sel, timeout=15000)", "Wait up to 15 seconds for this selector to match."),
    ('                log.debug("Results loaded with: %s", sel)', "Log which selector worked."),
    ("                return", "Success — results are loaded."),
    ("            except PwTimeout:", "If this selector didn't match within 15s..."),
    ("                continue", "...try the next one."),
    ('        log.warning("No result selector matched after 15s - page may have no flights")', "None worked. Page might have no results or Google changed their HTML."),
    ("", ""),
    ("    # -- Collect aria-labels --", ""),
    ("", ""),
    ("    async def _collect_aria_labels(self, page: Page) -> list[str]:", "Extracts flight descriptions from the page."),
    ('        """Google Flights puts full flight descriptions in aria-label on', ""),
    ("        div.JMc5Xc elements (one per flight card).", ""),
    ("", ""),
    ("        Uses page.evaluate() for reliability - runs JS directly in the browser.", '"""'),
    ("        labels: list[str] = await page.evaluate(\"\"\"", "Runs JavaScript inside the browser. This is more reliable than Playwright's CSS selectors."),
    ("            () => {", "An anonymous JavaScript function."),
    ("                const results = [];", "Empty array to collect labels."),
    ("                document.querySelectorAll('[aria-label]').forEach(el => {", "Find every element on the page that has an aria-label attribute."),
    ("                    const label = el.getAttribute('aria-label');", "Read the aria-label text."),
    ("                    if (label && label.includes('rupees') && label.includes('flight')) {", "Only keep labels that mention both 'rupees' (price) and 'flight' — these are flight descriptions."),
    ("                        results.push(label);", "Add to our results array."),
    ("                    }", ""),
    ("                });", ""),
    ("                return results;", "Return the array to Python."),
    ("            }", ""),
    ('        """)', ""),
    ("        return labels", ""),
    ("", ""),
    ("    # -- Parse one aria-label --", ""),
    ("", ""),
    ("    def _parse_aria_label(", "Takes a raw aria-label string and turns it into a FlightRecord."),
    ("        self, label: str, origin: str, dest: str,", ""),
    ("        travel_date: date, lead_window_days: int,", ""),
    ("    ) -> FlightRecord | None:", "Returns a FlightRecord or None if parsing fails."),
    ("        try:", ""),
    ("            price = self._extract_price_from_label(label)", "Extract the price (e.g., 12882)."),
    ("            carrier = self._extract_carrier_from_label(label)", "Extract airline name (e.g., 'IndiGo')."),
    ("            stops = self._extract_stops_from_label(label)", "Extract stops (e.g., 0 for nonstop)."),
    ('            dep_time = self._extract_time_from_label(label, which="departure")', "Extract departure time."),
    ('            arr_time = self._extract_time_from_label(label, which="arrival")', "Extract arrival time."),
    ("            duration = self._extract_duration_from_label(label)", "Extract duration in minutes."),
    ("", ""),
    ("            if price is None or carrier is None:", "If we couldn't get the two most important fields..."),
    ('                log.debug("Missing price or carrier in label, skipping")', "...skip this flight."),
    ("                return None", ""),
    ("", ""),
    ("            dep_dt = self._to_datetime(dep_time, travel_date) if dep_time else datetime.combine(travel_date, datetime.min.time())", "Convert departure time string to a datetime object. Fallback: midnight."),
    ("            arr_dt = self._to_datetime(arr_time, travel_date, forward=True) if arr_time else dep_dt + timedelta(hours=2)", "Convert arrival time. <code>forward=True</code> means: if hour < 6, assume next day."),
    ("", ""),
    ("            return FlightRecord(", "Create and return a validated FlightRecord."),
    ('                route=f"{origin}-{dest}",', "e.g., 'DEL-BOM'."),
    ("                origin=origin, dest=dest,", ""),
    ("                carrier=carrier,", ""),
    ('                flight_no="N/A",', "Google Flights doesn't always show flight numbers in the aria-label."),
    ("                depart_time=dep_dt, arrive_time=arr_dt,", ""),
    ("                duration_mins=duration or 120,", "Default to 120 minutes if unknown."),
    ("                stops=stops,", ""),
    ("                base_fare=0.0, taxes=0.0,", "Google Flights shows total fare only; we don't have the split."),
    ("                total_fare=float(price),", "The actual price."),
    ('                currency="INR",', ""),
    ("                lead_window_days=lead_window_days,", ""),
    ("                scrape_timestamp=datetime.now(),", ""),
    ("            )", ""),
    ("        except Exception as exc:", "If anything goes wrong during parsing..."),
    ('            log.debug("Label parse failed: %s | label=%s", exc, label[:80])', "...log the error (with first 80 chars of label for debugging)."),
    ("            return None", "...and return None."),
    ("", ""),
    ("    # -- Extractors --", "Section: individual field extractors using regex."),
    ("", ""),
    ("    @staticmethod", "Static methods: no 'self' needed."),
    ("    def _extract_price_from_label(label: str) -> int | None:", ""),
    ('        """\'From 12882 Indian rupees\' -> 12882"""', ""),
    ('        m = re.search(r"From\\s+([\\d,]+)\\s+Indian\\s+rupees", label)', "Regex: find 'From' followed by digits/commas, followed by 'Indian rupees'."),
    ("        if m:", "If the pattern matched..."),
    ('            return int(m.group(1).replace(",", ""))', "Extract the number (group 1), remove commas, convert to integer."),
    ('        m = re.search(r"([\\d,]+)\\s*(?:Indian\\s+)?rupees?", label)', "Fallback pattern: any number before 'rupees'."),
    ("        if m:", ""),
    ('            return int(m.group(1).replace(",", ""))', ""),
    ("        return None", "No price found."),
    ("", ""),
    ("    @staticmethod", ""),
    ("    def _extract_carrier_from_label(label: str) -> str | None:", ""),
    ('        """\'Nonstop flight with IndiGo\' -> \'IndiGo\'"""', ""),
    ('        m = re.search(r"with\\s+(.+?)(?:\\.|Leaves|$)", label)', "Regex: 'with' followed by the airline name, ending at a period, 'Leaves', or end of string."),
    ("        if m:", ""),
    ("            return m.group(1).strip()", "Return the captured airline name, trimmed of whitespace."),
    ("        return None", ""),
    ("", ""),
    ("    @staticmethod", ""),
    ("    def _extract_stops_from_label(label: str) -> int:", ""),
    ('        """\'Nonstop flight\' -> 0, \'1 stop flight\' -> 1"""', ""),
    ("        low = label.lower()", "Convert to lowercase for case-insensitive matching."),
    ('        if "nonstop" in low or "non-stop" in low:', "Check for nonstop variations."),
    ("            return 0", "Zero stops."),
    ('        m = re.search(r"(\\d+)\\s+stop", low)', "Look for '1 stop', '2 stops', etc."),
    ("        if m:", ""),
    ("            return int(m.group(1))", "Return the number."),
    ("        return 0", "Default to 0 if nothing found."),
    ("", ""),
    ("    @staticmethod", ""),
    ("    def _extract_time_from_label(label: str, which: str) -> str | None:", ""),
    ('        """Extract departure or arrival time."""', ""),
    ('        times = re.findall(r"at\\s+(\\d{1,2}:\\d{2}\\s*[AP]M)", label, re.IGNORECASE)', "Find all times matching 'at 8:45 AM' pattern."),
    ("        if not times:", "If no 'at' prefix times found..."),
    ('            times = re.findall(r"(\\d{1,2}:\\d{2}\\s*[AP]M)", label, re.IGNORECASE)', "...try without the 'at' prefix."),
    ("        if len(times) >= 2:", "If we found at least 2 times..."),
    ('            return times[0] if which == "departure" else times[1]', "First = departure, second = arrival."),
    ("        if len(times) == 1:", "Only one time found..."),
    ("            return times[0]", "Return it for both departure and arrival."),
    ("        return None", "No times found."),
    ("", ""),
    ("    @staticmethod", ""),
    ("    def _extract_duration_from_label(label: str) -> int | None:", ""),
    ('        """\'Total duration 2 hr 15 min\' -> 135"""', ""),
    ('        m = re.search(r"Total duration\\s+(\\d+)\\s*hr?\\s*(\\d*)\\s*min?", label, re.IGNORECASE)', "Regex: find 'Total duration 2 hr 15 min'."),
    ("        if m:", ""),
    ("            hours = int(m.group(1))", "Extract hours (e.g., 2)."),
    ("            mins = int(m.group(2)) if m.group(2) else 0", "Extract minutes (e.g., 15). Empty = 0."),
    ("            return hours * 60 + mins", "Convert to total minutes."),
    ('        m = re.search(r"(\\d+)\\s*hr?\\s*(\\d*)\\s*min?", label, re.IGNORECASE)', "Fallback: any 'X hr Y min' pattern."),
    ("        if m:", ""),
    ("            hours = int(m.group(1))", ""),
    ("            mins = int(m.group(2)) if m.group(2) else 0", ""),
    ("            return hours * 60 + mins", ""),
    ("        return None", ""),
    ("", ""),
    ("    # -- Helpers --", ""),
    ("", ""),
    ("    @staticmethod", ""),
    ("    def _to_datetime(time_str: str, d: date, forward: bool = False) -> datetime:", "Converts '8:45 AM' into a full datetime object."),
    ('        t = time_str.strip().replace(".", ":")', "Clean the string: trim spaces, replace dots with colons."),
    ('        for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):', "Try multiple time formats."),
    ("            try:", ""),
    ("                parsed = datetime.strptime(t, fmt)", "Attempt to parse with this format."),
    ("                result = datetime.combine(d, parsed.time())", "Combine with the travel date."),
    ("                if forward and result.hour < 6:", "For arrival times: if hour < 6 AM, it's probably next day."),
    ("                    result += timedelta(days=1)", "Add one day."),
    ("                return result", ""),
    ("            except ValueError:", "Format didn't match."),
    ("                continue", "Try the next format."),
    ('        return datetime.combine(d, datetime.min.time())', "No format matched: default to midnight."),
    ("", ""),
    ("    @staticmethod", ""),
    ("    async def _random_delay(lo: float, hi: float) -> None:", "Wait a random amount of time between lo and hi seconds."),
    ("        await asyncio.sleep(random.uniform(lo, hi))", "<code>random.uniform</code> picks a random float between lo and hi."),
]

html = make_html("Walkthrough 11: src/scraper/google_flights.py", "src/scraper/google_flights.py", gf_lines,
                 prev_file="10-driver-py.html", next_file="12-run-scrape-py.html")
(OUT_DIR / "11-google-flights-py.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 12: src/scraper/run_scrape.py
# ══════════════════════════════════════════════════════════════════════════
run_lines = [
    ('"""Scrape all configured routes -> write to raw_flights table.', "Module docstring with usage instructions."),
    ("", ""),
    ("Usage:", ""),
    ("    python -m src.scraper.run_scrape              # scrape all routes for today", ""),
    ("    python -m src.scraper.run_scrape --date 2026-09-15", ""),
    ('"""', ""),
    ("import argparse", "For parsing command-line arguments (like <code>--date</code>)."),
    ("import asyncio", "Async programming support."),
    ("import logging", "For structured log output."),
    ("import sys", "System-specific functions (e.g., stdout)."),
    ("from datetime import date, datetime, timedelta", "Date/time classes."),
    ("from pathlib import Path", "File path handling."),
    ("", ""),
    ("import yaml", "YAML config reader."),
    ("", ""),
    ("from src.scraper.google_flights import GoogleFlightsScraper, _load_routes", "Import the scraper class and route loader."),
    ("from src.models.schemas import FlightRecord", "Data model."),
    ("from src.storage.database import get_connection, init_db", "Database functions."),
    ("", ""),
    ("log = logging.getLogger(__name__)", "Module-level logger."),
    ("", ""),
    ("", ""),
    ("def _setup_logging() -> None:", "Configures how log messages are formatted and displayed."),
    ("    logging.basicConfig(", "Sets up the root logger."),
    ("        level=logging.INFO,", "Show INFO-level and above (INFO, WARNING, ERROR)."),
    ('        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",', "Format: time | level | module | message."),
    ('        datefmt="%H:%M:%S",', "Time format: hours:minutes:seconds."),
    ("        handlers=[logging.StreamHandler(sys.stdout)],", "Print to standard output (the terminal)."),
    ("    )", ""),
    ("", ""),
    ("", ""),
    ("def _insert_records(records: list[FlightRecord], scrape_date: str) -> int:", "Inserts a batch of FlightRecord objects into the raw_flights table."),
    ('    """Batch-insert FlightRecords into raw_flights. Returns row count."""', "Docstring."),
    ("    if not records:", "If the list is empty..."),
    ("        return 0", "...nothing to insert."),
    ("", ""),
    ("    conn = get_connection()", "Open a database connection."),
    ("    try:", "Ensure we close the connection."),
    ("        sql = \"\"\"", "The SQL INSERT statement with 16 placeholders (?)."),
    ("            INSERT INTO raw_flights", "Add a new row to raw_flights."),
    ("            (scrape_date, route, origin, dest, carrier, flight_no,", "Column names."),
    ("             depart_time, arrive_time, duration_mins, stops,", ""),
    ("             base_fare, taxes, total_fare, currency, lead_window_days,", ""),
    ("             scrape_timestamp)", ""),
    ("            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", "16 question marks = 16 values to insert."),
    ("        \"\"\"", ""),
    ("        rows = [", "Build a list of tuples, one per flight record."),
    ("            (", "Each tuple contains the 16 values in the same order as the columns."),
    ("                scrape_date,", "Date this data was scraped."),
    ("                r.route, r.origin, r.dest,", "Route info."),
    ("                r.carrier, r.flight_no,", "Airline info."),
    ("                r.depart_time.isoformat(),", "Convert datetime to string like '2026-09-11T08:45:00'."),
    ("                r.arrive_time.isoformat(),", ""),
    ("                r.duration_mins, r.stops,", ""),
    ("                r.base_fare, r.taxes, r.total_fare,", ""),
    ("                r.currency, r.lead_window_days,", ""),
    ("                r.scrape_timestamp.isoformat(),", ""),
    ("            )", ""),
    ("            for r in records", "Do this for every FlightRecord in the list."),
    ("        ]", ""),
    ("        conn.executemany(sql, rows)", "Execute the INSERT for all rows at once (much faster than one-by-one)."),
    ("        conn.commit()", "Save all changes to the database file."),
    ("        return len(rows)", "Return how many rows were inserted."),
    ("    finally:", "Always run this, even if an error occurred."),
    ("        conn.close()", "Close the database connection."),
    ("", ""),
    ("", ""),
    ("async def run_scrape(target_date: date | None = None) -> None:", "The main async function that runs the entire scrape pipeline."),
    ('    """Main scrape loop: every route x every lead window."""', "Docstring."),
    ("    _setup_logging()", "Set up log formatting."),
    ("    _setup_logging()", "(Duplicate call - harmless)."),
    ("    init_db()", "Ensure the database tables exist."),
    ("", ""),
    ("    cfg = _load_routes()", "Load routes.yaml."),
    ('    routes = cfg["routes"]', "Get the list of 12 routes."),
    ('    windows = cfg["lead_windows"]', "Get the list of lead windows [1, 7, 30]."),
    ("    scrape_date_str = (target_date or date.today()).isoformat()", "Format today's date as 'YYYY-MM-DD'."),
    ("", ""),
    ('    log.info("=== Scrape run: %s ===", scrape_date_str)', "Log the start of the run."),
    ('    log.info("Routes: %d | Windows: %s", len(routes), windows)', "Log how many routes and windows."),
    ("", ""),
    ("    scraper = GoogleFlightsScraper()", "Create the scraper (loads config automatically)."),
    ("    total_inserted = 0", "Counter for total flights saved."),
    ("    total_failed = 0", "Counter for failed route/window combinations."),
    ("", ""),
    ("    for route in routes:", "Loop through all 12 routes."),
    ('        origin, dest = route["origin"], route["dest"]', "Extract origin and destination."),
    ("        for lead in windows:", "For each lead window (1, 7, 30 days)..."),
    ("            travel = (target_date or date.today()) + timedelta(days=lead)", "Calculate the actual travel date."),
    ('            log.info("-- %s->%s  T+%d  (travel: %s) --", origin, dest, lead, travel)', "Log which route/window we're scraping."),
    ("", ""),
    ("            try:", "Attempt to scrape this route."),
    ("                records = await scraper.fetch_flights(origin, dest, travel, lead)", "Call the scraper."),
    ("                count = _insert_records(records, scrape_date_str)", "Save to database."),
    ("                total_inserted += count", "Add to running total."),
    ('                log.info("  OK %d flights saved", count)', "Log success."),
    ("            except Exception as exc:", "If scraping failed..."),
    ("                total_failed += 1", "Count the failure."),
    ('                log.error("  FAILED: %s", exc)', "Log the error."),
    ("", ""),
    ('    log.info(', "Log the final summary."),
    ('        "=== Run complete: %d flights saved, %d route x window failures ===",', ""),
    ("        total_inserted, total_failed,", ""),
    ("    )", ""),
    ("", ""),
    ("", ""),
    ("def main() -> None:", "Entry point for command-line execution."),
    ('    parser = argparse.ArgumentParser(description="Run flight scrape")', "Create a command-line argument parser."),
    ('    parser.add_argument("--date", type=str, default=None,', "Add an optional --date argument."),
    ('                        help="Scrape date as YYYY-MM-DD (default: today)")', "Help text shown with --help."),
    ("    args = parser.parse_args()", "Parse the command-line arguments."),
    ("", ""),
    ("    target = date.fromisoformat(args.date) if args.date else None", "Convert the date string to a date object, or None if not provided."),
    ("    asyncio.run(run_scrape(target))", "Run the async scrape function. <code>asyncio.run</code> handles the event loop."),
    ("", ""),
    ("", ""),
    ('if __name__ == "__main__":', "Only runs when this file is executed directly."),
    ("    main()", "Call the main function."),
]

html = make_html("Walkthrough 12: src/scraper/run_scrape.py", "src/scraper/run_scrape.py", run_lines,
                 prev_file="11-google-flights-py.html", next_file="13-clean-py.html")
(OUT_DIR / "12-run-scrape-py.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# 13. src/cleaner/clean.py
# ══════════════════════════════════════════════════════════════════════════
clean_lines = [
    ("import hashlib", "For generating unique fingerprint hashes to detect duplicate rows."),
    ("import logging", "For printing status messages (INFO, WARNING, ERROR) to the terminal."),
    ("import sys", "For accessing system features like the Python path."),
    ("from pathlib import Path", "For working with file/folder paths in a cross-platform way (Windows, Mac, Linux)."),
    ("", ""),
    ("import pandas as pd", "Import the Pandas library — Python's tool for working with tables of data (like Excel, but in code)."),
    ("import yaml", "For reading YAML config files (like indexer.yaml)."),
    ("", ""),
    ("log = logging.getLogger(__name__)", "Create a logger that prints messages with this module's name."),
    ("", ""),
    ("CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / \"config\" / \"indexer.yaml\"", "Build the full path to the indexer config file. Goes up 3 folders from this file, then into config/."),
    ("", ""),
    ("", ""),
    ("def _load_cleaning_config(cfg_path: Path | None = None) -> dict:", "Load cleaning settings from indexer.yaml. Returns a dictionary like {'outlier_method': 'iqr', 'iqr_multiplier': 1.5, ...}."),
    ("    path = cfg_path or CONFIG_PATH", "Use the provided path, or fall back to the default CONFIG_PATH."),
    ("    with open(path) as f:", "Open and read the YAML file."),
    ("        cfg = yaml.safe_load(f)", "Parse the YAML into a Python dictionary."),
    ("    return cfg.get(\"cleaning\", {})", "Return just the 'cleaning' section. If it doesn't exist, return an empty dict."),
    ("", ""),
    ("", ""),
    ("def _compute_hash(row: pd.Series) -> str:", "Create a unique fingerprint for each flight row. Used to detect duplicates."),
    ("    key = f\"{row['route']}|{row['carrier']}|{row['depart_time']}|{row['total_fare']}|{row['lead_window_days']}\"", "Combine the key fields into one string: 'DEL-BOM|IndiGo|2026-09-11 08:45|5500|7'."),
    ("    return hashlib.md5(key.encode()).hexdigest()", "Hash that string into a fixed-length fingerprint like 'a1b2c3d4e5f6...'. Identical rows produce identical hashes."),
    ("", ""),
    ("", ""),
    ("def _flag_outliers_iqr(group: pd.Series, multiplier: float = 1.5) -> pd.Series:", "Detect outlier fares using the IQR method. Takes a group of fares and returns 0 (normal) or 1 (outlier) for each."),
    ("    q1 = group.quantile(0.25)", "Q1 = the 25th percentile. 25% of fares are below this value."),
    ("    q3 = group.quantile(0.75)", "Q3 = the 75th percentile. 75% of fares are below this value."),
    ("    iqr = q3 - q1", "IQR = the range of the middle 50% of fares."),
    ("    lower = q1 - multiplier * iqr", "Lower bound. Anything below this is an outlier. Default: Q1 - 1.5×IQR."),
    ("    upper = q3 + multiplier * iqr", "Upper bound. Anything above this is an outlier. Default: Q3 + 1.5×IQR."),
    ("    return group.apply(lambda x: 1 if x < lower or x > upper else 0)", "Mark each fare: 1 if outside bounds, 0 if inside."),
    ("", ""),
    ("", ""),
    ("def _compute_quality_score(df: pd.DataFrame) -> pd.Series:", "Calculate a quality score (0.0 to 1.0) for each row. More complete data = higher score."),
    ("    score = pd.Series(1.0, index=df.index)", "Start every row at 1.0 (perfect)."),
    ("    for col in [\"carrier\", \"depart_time\", \"arrive_time\", \"duration_mins\", \"total_fare\"]:", "Check each critical column."),
    ("        score = score.where(df[col].notna(), score - 0.2)", "If a column is null/missing, subtract 0.2 from the score."),
    ("    score = score.where(df[\"stops\"].isin([0, 1, 2]), score - 0.1)", "If stops is not 0, 1, or 2 (unusual), subtract 0.1."),
    ("    return score.clip(lower=0, upper=1)", "Clamp the score between 0.0 and 1.0 (never negative, never above 1)."),
    ("", ""),
    ("", ""),
    ("def clean_raw_data(", "Main cleaning function. Reads raw flights, cleans them, writes cleaned flights."),
    ("    db_path: str | Path | None = None,", "Optional: path to a specific database file."),
    ("    cfg_path: Path | None = None,", "Optional: path to a specific indexer config file."),
    (") -> dict:", "Returns a dictionary with cleaning statistics."),
    ("    from src.storage.database import DB_PATH, get_connection", "Import database functions. Using local import to avoid circular imports."),
    ("", ""),
    ("    path = Path(db_path) if db_path else DB_PATH", "Use the provided path, or the default database path."),
    ("    cfg = _load_cleaning_config(cfg_path)", "Load cleaning settings from indexer.yaml."),
    ("", ""),
    ("    multiplier = cfg.get(\"iqr_multiplier\", 1.5)", "IQR multiplier for outlier detection. Default 1.5."),
    ("    null_action = cfg.get(\"null_fare_action\", \"drop\")", "What to do with null fares: 'drop' removes them, 'forward_fill' fills from previous."),
    ("", ""),
    ("    log.info(\"Reading raw_flights from %s\", path)", "Log which database we're reading from."),
    ("    conn = get_connection(path)", "Open a database connection."),
    ("    df = pd.read_sql(\"SELECT * FROM raw_flights\", conn)", "Load the entire raw_flights table into a Pandas DataFrame (a table object)."),
    ("    conn.close()", "Close the database connection."),
    ("", ""),
    ("    if df.empty:", "If there are no raw rows..."),
    ("        log.warning(\"raw_flights is empty — nothing to clean\")", "...log a warning."),
    ("        return {\"raw\": 0, \"cleaned\": 0, \"duplicates\": 0, \"outliers\": 0, \"nulls\": 0}", "...and return empty stats."),
    ("", ""),
    ("    raw_count = len(df)", "Count how many raw rows we started with."),
    ("    log.info(\"Loaded %d raw rows\", raw_count)", "Log the count."),
    ("", ""),
    ("", ""),
    ("    # Step 1: Deduplication", "Remove exact duplicate rows."),
    ("    df[\"dedup_hash\"] = df.apply(_compute_hash, axis=1)", "Add a 'dedup_hash' column: each row gets a unique fingerprint."),
    ("    before_dedup = len(df)", "Count rows before removing duplicates."),
    ("    df = df.drop_duplicates(subset=[\"dedup_hash\"], keep=\"first\")", "Keep only the first occurrence of each hash. Remove the rest."),
    ("    duplicates = before_dedup - len(df)", "Calculate how many were removed."),
    ("    log.info(\"Removed %d duplicates\", duplicates)", "Log the dedup count."),
    ("", ""),
    ("", ""),
    ("    # Step 2: Handle null fares", "Remove or fill rows where total_fare is missing."),
    ("    if null_action == \"drop\":", "If configured to drop null fares..."),
    ("        before_null = len(df)", "Count before."),
    ("        df = df.dropna(subset=[\"total_fare\"])", "Remove any row where total_fare is NaN/null."),
    ("        nulls = before_null - len(df)", "Count how many were removed."),
    ("        log.info(\"Dropped %d rows with null fare\", nulls)", "Log it."),
    ("    else:", "If configured to forward-fill..."),
    ("        df = df.sort_values([\"route\", \"lead_window_days\", \"scrape_timestamp\"])", "Sort rows so the same route+window are grouped together."),
    ("        df[\"total_fare\"] = df.groupby([\"route\", \"lead_window_days\"])[\"total_fare\"].transform(", "For each route+window group..."),
    ("            lambda x: x.ffill()", "...fill null fares with the previous non-null value (forward fill)."),
    ("        )", ""),
    ("        nulls = int(df[\"total_fare\"].isna().sum())", "Count any remaining nulls that couldn't be filled."),
    ("        df = df.dropna(subset=[\"total_fare\"])", "Drop any still-null rows."),
    ("        log.info(\"Forward-filled null fares, dropped %d remaining\", nulls)", "Log it."),
    ("", ""),
    ("", ""),
    ("    # Step 3: Outlier detection", "Flag rows with unusually high or low fares."),
    ("    df[\"is_outlier\"] = (", "Add a new column 'is_outlier'."),
    ("        df.groupby([\"route\", \"lead_window_days\"])[\"total_fare\"]", "For each route+window group..."),
    ("        .transform(lambda x: _flag_outliers_iqr(x, multiplier))", "...run IQR outlier detection on the fares."),
    ("    )", ""),
    ("    outlier_count = int(df[\"is_outlier\"].sum())", "Count total outliers (sum of 1s)."),
    ("    log.info(\"Flagged %d outliers via IQR (×%.1f)\", outlier_count, multiplier)", "Log the outlier count."),
    ("", ""),
    ("", ""),
    ("    # Step 4: Quality scores", "Assign a quality score to each row."),
    ("    df[\"quality_score\"] = _compute_quality_score(df)", "Calculate how complete/reliable each row is (0.0 to 1.0)."),
    ("", ""),
    ("", ""),
    ("    # Step 5: Format dates", "Convert datetime objects to consistent string format."),
    ("    df[\"scrape_date\"] = pd.to_datetime(df[\"scrape_timestamp\"]).dt.date.astype(str)", "Extract just the date part (YYYY-MM-DD) from the timestamp."),
    ("    df[\"scrape_timestamp\"] = pd.to_datetime(df[\"scrape_timestamp\"]).dt.strftime(\"%Y-%m-%d %H:%M:%S\")", "Format timestamp as '2026-09-04 15:30:00'."),
    ("    df[\"depart_time\"] = pd.to_datetime(df[\"depart_time\"], errors=\"coerce\").dt.strftime(\"%Y-%m-%d %H:%M:%S\")", "Format departure time. If parsing fails, set to NaT (then null)."),
    ("    df[\"arrive_time\"] = pd.to_datetime(df[\"arrive_time\"], errors=\"coerce\").dt.strftime(\"%Y-%m-%d %H:%M:%S\")", "Format arrival time same way."),
    ("", ""),
    ("", ""),
    ("    # Step 6: Select columns", "Keep only the columns the cleaned_flights table expects."),
    ("    keep_cols = [", "List of columns to keep."),
    ("        \"scrape_date\", \"route\", \"origin\", \"dest\", \"carrier\", \"flight_no\",", ""),
    ("        \"depart_time\", \"arrive_time\", \"duration_mins\", \"stops\",", ""),
    ("        \"base_fare\", \"taxes\", \"total_fare\", \"currency\", \"lead_window_days\",", ""),
    ("        \"scrape_timestamp\", \"quality_score\", \"is_outlier\", \"dedup_hash\",", ""),
    ("    ]", ""),
    ("    df = df[keep_cols]", "Keep only these columns, drop everything else (like 'id' from raw_flights)."),
    ("", ""),
    ("", ""),
    ("    # Step 7: Write to cleaned_flights", "Save the cleaned data to the database."),
    ("    log.info(\"Writing %d cleaned rows to cleaned_flights\", len(df))", "Log how many cleaned rows we're writing."),
    ("    conn = get_connection(path)", "Open a database connection."),
    ("    df.to_sql(\"cleaned_flights\", conn, if_exists=\"append\", index=False)", "Write the DataFrame to the cleaned_flights table. append = add to existing rows."),
    ("    conn.close()", "Close the connection."),
    ("", ""),
    ("", ""),
    ("    stats = {", "Build a summary dictionary."),
    ("        \"raw\": raw_count, \"cleaned\": len(df),", "Raw count and cleaned count."),
    ("        \"duplicates\": duplicates, \"outliers\": outlier_count, \"nulls\": nulls,", "How many duplicates, outliers, and nulls."),
    ("    }", ""),
    ("    log.info(\"Cleaning complete: %s\", stats)", "Log the final stats."),
    ("    return stats", "Return the stats dictionary."),
    ("", ""),
    ("", ""),
    ("if __name__ == \"__main__\":", "Only runs when this file is executed directly."),
    ("    logging.basicConfig(", "Configure the logging system."),
    ("        level=logging.INFO,", "Show INFO-level and above."),
    ("        format=\"%(asctime)s | %(levelname)-7s | %(message)s\",", "Format: time | level | message."),
    ("        datefmt=\"%H:%M:%S\",", "Time format: HH:MM:SS."),
    ("        handlers=[logging.StreamHandler(sys.stdout)],", "Print to terminal."),
    ("    )", ""),
    ("    result = clean_raw_data()", "Run the cleaning pipeline."),
    ("    print(f\"\\nResults: {result}\")", "Print the final stats."),
]

html = make_html("Walkthrough 13: src/cleaner/clean.py", "src/cleaner/clean.py", clean_lines,
                 prev_file="12-run-scrape-py.html", next_file="14-run-index-py.html")
(OUT_DIR / "13-clean-py.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 14: src/indexer/run_index.py
# ══════════════════════════════════════════════════════════════════════════
run_index_lines = [
    ('"""Compute daily / weekly / monthly APIx from cleaned_flights.', "Module docstring: this is the Phase 3 entry point. It reads cleaned data, builds all three indices, and writes them back."),
    ("", ""),
    ("Reads the full cleaned_flights table, builds the weighted basket index, and", ""),
    ("writes the result to daily_index, weekly_index, and monthly_index.", ""),
    ("", ""),
    ("Usage:", ""),
    ("    python -m src.indexer.run_index                  # rebuild all indices", ""),
    ("    python -m src.indexer.run_index --db data/custom.db", ""),
    ('"""', ""),
    ("import argparse", "For parsing command-line arguments like <code>--db</code>."),
    ("import logging", "Structured status and error messages."),
    ("import sys", "Lets logging write to the terminal (stdout)."),
    ("from pathlib import Path", "Cross-platform file paths."),
    ("", ""),
    ("from src.indexer.api_index import (", "Import the pure index-building functions from the sibling module."),
    ("    compute_daily_index,", "The daily index builder (route + aggregate per lead window)."),
    ("    compute_rolling_index,", "The weekly/monthly rolling builder."),
    ("    load_index_config,", "Reads the <code>index:</code> section of indexer.yaml."),
    ("    load_route_weights,", "Reads and normalises the 12 route weights."),
    ("    read_cleaned_flights,", "Loads the cleaned_flights table as a DataFrame."),
    ("    route_price_per_day,", "Collapses cleaned rows to one min fare per route/window/date."),
    ("    write_index,", "Writes rows to a *_index table (overwriting the same date)."),
    (")", ""),
    ("from src.storage.database import get_connection, init_db", "Database setup helpers."),
    ("", ""),
    ("log = logging.getLogger(__name__)", "Module-level logger."),
    ("", ""),
    ("", ""),
    ("def _setup_logging() -> None:", "Configures how log messages are formatted and printed."),
    ("    logging.basicConfig(", "Set up the root logger."),
    ("        level=logging.INFO,", "Show INFO and above (skips DEBUG noise)."),
    ('        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",', "Format: time | level | module | message."),
    ('        datefmt="%H:%M:%S",', "Clock format."),
    ("        handlers=[logging.StreamHandler(sys.stdout)],", "Print to the terminal."),
    ("    )", ""),
    ("", ""),
    ("", ""),
    ("def run_index(db_path: Path | str | None = None, cfg_path: Path | str | None = None) -> dict:", "Main function: run the whole indexing pipeline and return row-count stats."),
    ("    init_db(db_path)", "Ensure all tables (including the *_index tables) exist."),
    ("", ""),
    ("    cleaned = read_cleaned_flights(db_path)", "Load cleaned_flights into a DataFrame."),
    ("    if cleaned.empty:", "If there is no cleaned data yet..."),
    ('        log.warning("cleaned_flights is empty — nothing to index")', "...warn and stop."),
    ('        return {"daily": 0, "weekly": 0, "monthly": 0}', "Return zeroed stats."),
    ("", ""),
    ("    weights = load_route_weights(cfg_path)", "Load and normalise the route weights from indexer.yaml."),
    ("    round_to = load_index_config(cfg_path).get(\"round_to\", 2)", "Read the decimal precision setting (default 2)."),
    ("", ""),
    ('    log.info("═══ Index run ═══")', "Log the run header."),
    ('    log.info("Weights: %d routes (normalised to %s)", len(weights), round(sum(weights.values()), 4))', "Log how many routes and confirm weights sum to ~1.0."),
    ("", ""),
    ("    prices = route_price_per_day(cleaned)", "Fold the cleaned rows into one lowest fare per route/window/date (outliers excluded)."),
    ("    if prices.empty:", "If nothing survived the folding..."),
    ('        log.warning("No price rows after cleaning filter — nothing to index")', "...warn and stop."),
    ('        return {"daily": 0, "weekly": 0, "monthly": 0}', "Zeroed stats again."),
    ('    log.info("Price rows: %d (route × window × date)", len(prices))', "Log how many price points feed the index."),
    ("", ""),
    ("    daily = compute_daily_index(prices, weights, round_to)", "Step 1: daily route + aggregate index, per lead window."),
    ("    weekly = compute_rolling_index(daily, 7, round_to)", "Step 2: 7-day rolling means of the daily values."),
    ("    monthly = compute_rolling_index(daily, 30, round_to)", "Step 3: 30-day rolling means of the daily values."),
    ("", ""),
    ("    n_daily = write_index(daily, \"daily_index\", db_path)", "Write daily rows (overwrite if that date+window already exists)."),
    ("    n_weekly = write_index(weekly, \"weekly_index\", db_path)", "Write weekly rows."),
    ("    n_monthly = write_index(monthly, \"monthly_index\", db_path)", "Write monthly rows."),
    ("", ""),
    ('    log.info("═══ Complete: daily=%d | weekly=%d | monthly=%d ═══", n_daily, n_weekly, n_monthly)', "Log the final row counts."),
    ('    return {"daily": n_daily, "weekly": n_weekly, "monthly": n_monthly}', "Return stats for callers."),
    ("", ""),
    ("", ""),
    ("def main() -> None:", "Command-line entry point."),
    ('    parser = argparse.ArgumentParser(description="Build APIx indices from cleaned_flights")', "Create a CLI parser."),
    ('    parser.add_argument("--db", type=str, default=None, help="Path to SQLite db (default: data/apix.db)")', "Optional custom database path."),
    ("    args = parser.parse_args()", "Parse the arguments."),
    ("", ""),
    ("    _setup_logging()", "Enable logging."),
    ("    run_index(db_path=args.db)", "Run the pipeline."),
    ("", ""),
    ('if __name__ == "__main__":', "Runs only when executed directly (not on import)."),
    ("    main()", "Call main."),
]

html = make_html("Walkthrough 14: src/indexer/run_index.py", "src/indexer/run_index.py", run_index_lines,
                 prev_file="13-clean-py.html", next_file="15-api-index-py.html")
(OUT_DIR / "14-run-index-py.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# FILE 15: src/indexer/api_index.py (the actual index math)
# ══════════════════════════════════════════════════════════════════════════
api_lines = [
    ('"""APIx index builder — Laspeyres-style weighted basket index.', "Module docstring ending right here explains the math."),
    ("", ""),
    ("Core math (per lead window):", ""),
    ("    APIx(t) = Σ [ P_i(t) / P_i(0) × w_i ] × 100", ""),
    ("", ""),
    ("Where P_i(t) = lowest fare on route i on date t, P_i(0) = lowest fare on the", "Key terms: today's fare vs the base-day fare, weighted by traffic share."),
    ("base date, and w_i are route weights (sum ≈ 1.0). Missing routes are omitted", ""),
    ("and their weight contributes 0 (weights are never re-normalised per day).", "Fixed-weights design: a missing route drops out entirely."),
    ("", ""),
    ("Design: the core functions operate on pandas DataFrames so they are trivially", "DataFrames in, DataFrames out → easy to unit-test offline (constraint TC-T1)."),
    ("unit-testable off-line; thin wrappers read from / write to SQLite.", ""),
    ('"""', ""),
    ("import logging", "For log messages."),
    ("from pathlib import Path", "File path handling."),
    ("", ""),
    ("import pandas as pd", "Tabular data processing."),
    ("import yaml", "Reads YAML config."),
    ("", ""),
    ("from src.storage.database import get_connection", "SQLite connection helper."),
    ("", ""),
    ("log = logging.getLogger(__name__)", "Module logger."),
    ("", ""),
    ('CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "indexer.yaml"', "Resolve the path to config/indexer.yaml (up 3 folders from this file)."),
    ("", ""),
    ("INDEX_COLUMNS = [", "The exact column order of every *_index table / DataFrame."),
    ('    "index_date",', "The date the index is anchored to."),
    ('    "lead_window_days",', "The advance-purchase window (1, 7, or 30)."),
    ('    "route",', "Directional route code like DEL-BOM."),
    ('    "weight",', "This route's basket weight."),
    ('    "route_price",', "Lowest fare used for this route/window/date."),
    ('    "route_index",', "route_price / base_price × 100."),
    ('    "aggregate_index",', "Weighted sum across routes for that day."),
    ('    "base_period",', "The date whose price = 100 for this window."),
    ("]", ""),
    ('INDEX_TABLES = {"daily_index", "weekly_index", "monthly_index"}', "Whitelist of tables write_index may touch (safety)."),
    ("", ""),
    ('INSERT_SQL = """', "SQL template with a {table} placeholder."),
    ("INSERT INTO {table}", "Insert into the chosen table."),
    ("(index_date, lead_window_days, route, weight, route_price, route_index,", "Column list."),
    (" aggregate_index, base_period)", ""),
    ("VALUES (?, ?, ?, ?, ?, ?, ?, ?)", "Eight values, one per column."),
    ('"""', ""),
    ("", ""),
    ("", ""),
    ("def load_index_config(cfg_path: Path | str | None = None) -> dict:", "Read the <code>index:</code> section of indexer.yaml."),
    ("    path = Path(cfg_path) if cfg_path else CONFIG_PATH", "Use the given path or the default."),
    ("    with open(path) as f:", "Open the file safely."),
    ('        return yaml.safe_load(f).get("index", {})', "Parse YAML and return the index section (or {})."),
    ("", ""),
    ("", ""),
    ("def load_route_weights(cfg_path: Path | str | None = None) -> dict[str, float]:", "Read the weights map and normalise it to sum 1.0."),
    ("    raw = load_index_config(cfg_path).get(\"weights\", {})", "Grab the weights dictionary."),
    ("    total = sum(raw.values())", "Add up all raw weights."),
    ('    if not raw or total <= 0:', "Guard: no weights or all zeros is a config error."),
    ('        raise ValueError("No route weights found in indexer.yaml under \'index.weights\'")', "Raise so the pipeline fails loudly, not silently."),
    ("    return {route: weight / total for route, weight in raw.items()}", "Divide each weight by the total so they sum to exactly 1.0."),
    ("", ""),
    ("", ""),
    ("def read_cleaned_flights(db_path: Path | str | None = None) -> pd.DataFrame:", "Load the cleaned_flights table into a DataFrame."),
    ("    conn = get_connection(db_path)", "Open a connection."),
    ("    try:", "Ensure the connection is closed even on error."),
    ('        return pd.read_sql("SELECT * FROM cleaned_flights", conn)', "Read the entire table."),
    ("    finally:", ""),
    ("        conn.close()", "Close the connection."),
    ("", ""),
    ("", ""),
    ("def route_price_per_day(cleaned: pd.DataFrame) -> pd.DataFrame:", "Fold cleaned rows into one lowest fare per route/window/date."),
    ('    """Collapse cleaned rows to one min fare per (route, window, date).', "Docstring."),
    ("", ""),
    ("    Rows flagged as outliers (is_outlier == 1) are excluded from the price.", "Outliers are flagged (not removed) by the cleaner; the index ignores them."),
    ('    """', ""),
    ("    df = cleaned.copy()", "Work on a copy so callers' DataFrames aren't mutated."),
    ('    df = df[df["total_fare"].notna()]', "Drop rows with no fare."),
    ('    if "is_outlier" in df.columns:', "Only filter outliers if the column exists."),
    ('        df = df[df["is_outlier"] != 1]', "Drop rows flagged as outliers."),
    ("", ""),
    ("    prices = (", "Start the group-by chain."),
    ('        df.groupby(["route", "lead_window_days", "scrape_date"])["total_fare"]', "Group by route, lead window, and date; pick the fare column."),
    ("        .min()", "Take the minimum fare in each group — the cheapest offer."),
    ("        .reset_index()", "Turn the group keys back into columns."),
    ('        .rename(columns={"total_fare": "route_price"})', "Rename the min column to route_price for clarity."),
    ("    )", ""),
    ("    return prices", "Return the folded price table."),
    ("", ""),
    ("", ""),
    ("def compute_daily_index(", "Phase 3 core: the Laspeyres daily index."),
    ("    prices: pd.DataFrame, weights: dict[str, float], round_to: int = 2", "Prices from route_price_per_day + the normalised weights."),
    (") -> pd.DataFrame:", "Returns a DataFrame conforming to INDEX_COLUMNS."),
    ("""    '''Compute route-level and aggregate daily index per lead window.""", "Docstring."),
    ("", ""),
    ("    Base period is the first date with data, independently per lead window.", ""),
    ("    Routes without data on a given day are omitted (weights stay fixed).", ""),
    ("    '''", ""),
    ("    if prices is None or prices.empty:", "Guard: nothing to compute."),
    ("        return pd.DataFrame(columns=INDEX_COLUMNS)", "Return an empty, correctly-shaped DataFrame."),
    ("", ""),
    ("    rows: list[dict] = []", "Collector for output rows."),
    ('    for window, wg in prices.groupby("lead_window_days"):', "Loop over each lead window separately (T+1, T+7, T+30)."),
    ('        wg = wg.sort_values("scrape_date")', "Sort chronologically so the first row is the base day."),
    ('        base_date = wg["scrape_date"].iloc[0]', "Base period = earliest date with data for this window."),
    ('        base_prices = wg.loc[wg["scrape_date"] == base_date].set_index("route")["route_price"]', "Map route → base-day price. This is P_i(0)."),
    ("", ""),
    ('        for day_date, day in wg.groupby("scrape_date"):', "Loop over every date for this window."),
    ('            by_route = day.set_index("route")["route_price"]', "Map route → today's price. This is P_i(t)."),
    ("            agg = 0.0", "Running weighted sum for the aggregate index."),
    ("            date_rows: list[dict] = []", "Rows produced for this date."),
    ("            for route, weight in weights.items():", "Iterate routes in weight order (stable output)."),
    ("                if route not in by_route.index or route not in base_prices.index:", "Skip routes missing today OR on the base day."),
    ("                    continue", ""),
    ("                p_base = base_prices[route]", "Route's base-day price."),
    ("                if p_base <= 0:", "Guard against divide-by-zero."),
    ("                    continue", ""),
    ("                route_index = (by_route[route] / p_base) * 100.0", "Route ratio × 100 → this route's index."),
    ("                agg += route_index * weight", "Accumulate the weighted contribution into the aggregate."),
    ("                date_rows.append(", "Record this route's row."),
    ('                    {"index_date": day_date,', ""),
    ('                     "lead_window_days": int(window),', ""),
    ('                     "route": route,', ""),
    ('                     "weight": weight,', ""),
    ('                     "route_price": float(by_route[route]),', ""),
    ('                     "route_index": round(route_index, round_to),', "Round route index to the configured precision."),
    ('                     "aggregate_index": None,', "Filled in below once agg is final."),
    ('                     "base_period": base_date,}', ""),
    ("                )", ""),
    ("            agg_value = round(agg, round_to)", "Round the aggregate once. Note: missing routes contribute 0 — weights are NOT re-normalised."),
    ("            for r in date_rows:", "Now that agg is known, apply it to every route row for this date."),
    ('                r["aggregate_index"] = agg_value', ""),
    ("            rows.extend(date_rows)", "Add this date's rows to the global collector."),
    ("", ""),
    ("    return pd.DataFrame(rows, columns=INDEX_COLUMNS)", "Build the final DataFrame with the canonical column order."),
    ("", ""),
    ("", ""),
    ("def compute_rolling_index(", "Weekly/monthly builder."),
    ("    daily: pd.DataFrame, window_days: int, round_to: int = 2", "Daily index + the window length (7 or 30)."),
    (") -> pd.DataFrame:", "Returns a DataFrame with the same shape as daily."),
    ("""    '''Weekly / monthly rollups: rolling mean of daily values per route and""", "Docstring."),
    ("    per aggregate, anchored at each index_date (min_periods=1 so early data", ""),
    ("    still yields a value).'''", ""),
    ("    if daily is None or daily.empty:", "Guard for empty input."),
    ("        return pd.DataFrame(columns=INDEX_COLUMNS)", ""),
    ("", ""),
    ('    df = daily.sort_values(["lead_window_days", "route", "index_date"])', "Sort so each route/window's values are in date order (rolling needs order)."),
    ('    df["route_price_roll"] = (', "New column: rolling mean of route price."),
    ('        df.groupby(["lead_window_days", "route"])["route_price"]', "Per window + route."),
    ("        .transform(lambda s: s.rolling(window_days, min_periods=1).mean())", "Trailing window mean; min_periods=1 means early dates still produce a value."),
    ("    )", ""),
    ('    df["route_index_roll"] = (', "Same rolling treatment for route index."),
    ('        df.groupby(["lead_window_days", "route"])["route_index"]', ""),
    ("        .transform(lambda s: s.rolling(window_days, min_periods=1).mean())", ""),
    ("    )", ""),
    ('    df["agg_roll"] = (', "And for the aggregate index."),
    ('        df.groupby("lead_window_days")["aggregate_index"]', "Aggregate is per date (not per route), so group by window only."),
    ("        .transform(lambda s: s.rolling(window_days, min_periods=1).mean())", ""),
    ("    )", ""),
    ("", ""),
    ("    out = pd.DataFrame(", "Assemble the output DataFrame."),
    ('        {"index_date": df["index_date"],', ""),
    ('         "lead_window_days": df["lead_window_days"],', ""),
    ('         "route": df["route"],', ""),
    ('         "weight": df["weight"],', ""),
    ('         "route_price": df["route_price_roll"].round(round_to),', "Rounded rolling price."),
    ('         "route_index": df["route_index_roll"].round(round_to),', "Rounded rolling route index."),
    ('         "aggregate_index": df["agg_roll"].round(round_to),', "Rounded rolling aggregate."),
    ('         "base_period": df["base_period"],}', ""),
    ("    )", ""),
    ("    return out.reset_index(drop=True)", "Reset the index (range 0..n-1) and return."),
    ("", ""),
    ("", ""),
    ("def write_index(", "Persist an index DataFrame to a *_index table."),
    ("    index_df: pd.DataFrame, table: str, db_path: Path | str | None = None", "The DataFrame, target table, optional DB path."),
    (") -> int:", "Returns the number of rows written."),
    ("""    '''Overwrite *_index rows for each (index_date, lead_window_days).""", "Docstring."),
    ("", ""),
    ("    Re-running for the same date re-computes rather than duplicating rows.", "Idempotency: DELETE then INSERT per date+window."),
    ("    '''", ""),
    ('    if table not in INDEX_TABLES:', "Safety check against the table whitelist."),
    ('        raise ValueError(f"Unknown index table: {table}")', "Reject anything unexpected (prevents SQL mistakes)."),
    ("", ""),
    ("    if index_df is None or index_df.empty:", "Nothing to write."),
    ('        log.info("No rows to write to %s", table)', ""),
    ("        return 0", ""),
    ("", ""),
    ('    index_df = index_df[INDEX_COLUMNS]', "Enforce canonical column order."),
    ("    conn = get_connection(db_path)", "Open a connection."),
    ("    try:", "Ensure we close on the way out."),
    ('        for (day, window), _ in index_df.groupby(["index_date", "lead_window_days"]):', "One delete-reinsert pass per date + window."),
    ("            conn.execute(", "Delete the old rows for this date+window."),
    ('                f"DELETE FROM {table} WHERE index_date = ? AND lead_window_days = ?",', ""),
    ("                (day, int(window)),", ""),
    ("            )", ""),
    ('        rows = [tuple(r) for r in index_df.itertuples(index=False, name=None)]', "Convert each row to a plain tuple for executemany."),
    ('        conn.executemany(INSERT_SQL.format(table=table), rows)', "Bulk insert all rows."),
    ("        conn.commit()", "Persist the transaction."),
    ("        return len(rows)", "Return how many rows were written."),
    ("    finally:", ""),
    ("        conn.close()", "Always close the connection."),
]

html = make_html("Walkthrough 15: src/indexer/api_index.py", "src/indexer/api_index.py", api_lines,
                 prev_file="14-run-index-py.html")
(OUT_DIR / "15-api-index-py.html").write_text(html, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# MASTER INDEX
# ══════════════════════════════════════════════════════════════════════════
index_html = """<!DOCTYPE html>
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
<p>15 files, explained line by line. Read them in order.</p>
</header>

<div class="card">
<h2>Phase 0 - Environment & Setup (Files 1-8)</h2>
<ol>
<li><a href="01-env.html">.env</a> <span class="phase-label p0">P0</span><br><span class="desc">Secret settings file: browser path, speed limits, retry count.</span></li>
<li><a href="02-gitignore.html">.gitignore</a> <span class="phase-label p0">P0</span><br><span class="desc">What NOT to upload to GitHub: secrets, database, cache files.</span></li>
<li><a href="03-requirements.html">requirements.txt</a> <span class="phase-label p0">P0</span><br><span class="desc">Shopping list of Python libraries the project needs.</span></li>
<li><a href="04-routes-yaml.html">config/routes.yaml</a> <span class="phase-label p0">P0</span><br><span class="desc">4 cities, 12 routes, 3 lead windows, index weights.</span></li>
<li><a href="05-scraper-yaml.html">config/scraper.yaml</a> <span class="phase-label p0">P0</span><br><span class="desc">Rate limits, retry policy, browser settings, timeouts.</span></li>
<li><a href="06-indexer-yaml.html">config/indexer.yaml</a> <span class="phase-label p0">P0</span><br><span class="desc">Index formula settings, outlier detection rules.</span></li>
<li><a href="07-schemas-py.html">src/models/schemas.py</a> <span class="phase-label p0">P0</span><br><span class="desc">Pydantic data models: FlightRecord, RouteConfig, IndexEntry.</span></li>
<li><a href="08-database-py.html">src/storage/database.py</a> <span class="phase-label p0">P0</span><br><span class="desc">SQLite setup: 5 table definitions, init and connection functions.</span></li>
</ol>
</div>

<div class="card">
<h2>Phase 1 - The Scraper (Files 9-12)</h2>
<ol start="9">
<li><a href="09-base-py.html">src/scraper/base.py</a> <span class="phase-label p1">P1</span><br><span class="desc">Abstract interface: the contract every scraper must follow.</span></li>
<li><a href="10-driver-py.html">src/scraper/driver.py</a> <span class="phase-label p1">P1</span><br><span class="desc">Playwright browser launcher with auto-cleanup.</span></li>
<li><a href="11-google-flights-py.html">src/scraper/google_flights.py</a> <span class="phase-label p1">P1</span><br><span class="desc">Core scraper: URL builder, aria-label parser, retry logic. (302 lines)</span></li>
<li><a href="12-run-scrape-py.html">src/scraper/run_scrape.py</a> <span class="phase-label p1">P1</span><br><span class="desc">Orchestrator: loops all routes, saves to database.</span></li>
</ol>
</div>

<div class="card">
<h2>Phase 2 - Data Cleaning (File 13)</h2>
<ol start="13">
<li><a href="13-clean-py.html">src/cleaner/clean.py</a> <span class="phase-label p1">P2</span><br><span class="desc">Pandas pipeline: dedup, outlier detection (IQR), quality scoring.</span></li>
</ol>
</div>

<div class="card">
<h2>Phase 3 - The Index Builder (Files 14-15)</h2>
<ol start="14">
<li><a href="14-run-index-py.html">src/indexer/run_index.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Phase 3 entry point: reads cleaned data, builds daily + weekly + monthly indices, writes to SQLite.</span></li>
<li><a href="15-api-index-py.html">src/indexer/api_index.py</a> <span class="phase-label p1">P3</span><br><span class="desc">Laspeyres-style weighted basket math, per lead window. The core of APIx.</span></li>
</ol>
</div>

<div class="card" style="border-left-color:var(--green);">
<h2 style="color:var(--green);">How to Use These Walkthroughs</h2>
<p>Open any file above. Each walkthrough shows every line of code with a plain-English explanation beneath it. Read them in order (1-15) for the best learning experience.</p>
<p style="margin-top:10px;">Files 1-8 are Phase 0 (setup). Files 9-12 are Phase 1 (the scraper). File 13 is Phase 2 (cleaning). Files 14-15 are Phase 3 (the APIx index).</p>
</div>
</div>
</body>
</html>"""

(OUT_DIR / "index.html").write_text(index_html, encoding="utf-8")

print(f"Generated {len(list(OUT_DIR.glob('*.html')))} HTML files in {OUT_DIR}")
