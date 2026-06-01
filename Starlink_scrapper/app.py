from flask import Flask, render_template, request, jsonify, send_file
from bs4 import BeautifulSoup
from datetime import date, timedelta
import re, csv, os, io

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─────────────────────────────────────────
# CORE PARSER
# ─────────────────────────────────────────
def parse_usage_html(filepath, start_date, num_days):
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Read Y-axis ticks to calibrate GB scale
    ticks = []
    for tick in soup.select("g.MuiChartsAxis-directionY .MuiChartsAxis-tickContainer"):
        transform = tick.get("transform", "")
        match = re.search(r"translate\(0,\s*([\d.]+)\)", transform)
        label_el = tick.find("text")
        if match and label_el:
            y_pos = float(match.group(1))
            gb_match = re.search(r"([\d.]+)\s*GB", label_el.text)
            if gb_match:
                ticks.append((y_pos, float(gb_match.group(1))))

    if len(ticks) < 2:
        return [], "Could not read Y-axis ticks"

    y_zero = ticks[0][0]
    y_top  = ticks[-1][0]
    gb_max = ticks[-1][1]

    def y_to_gb(y, h):
        if h == 0:
            return 0.0
        return round(((y_zero - y) / (y_zero - y_top)) * gb_max, 2)

    bars = soup.select("g[data-series='y_0'] rect")
    results = []
    for i, bar in enumerate(bars[:num_days]):
        y = float(bar.get("y", y_zero))
        h = float(bar.get("height", 0))
        d = start_date + timedelta(days=i)
        results.append({
            "date": str(d),
            "month": d.strftime("%B %Y"),
            "usage_gb": y_to_gb(y, h)
        })

    return results, None


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/parse", methods=["POST"])
def parse():
    results = []
    errors  = []

    files = request.files.getlist("html_files")
    if not files or files[0].filename == "":
        return jsonify({"error": "No files uploaded"}), 400

    for file in files:
        filename  = file.filename
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)

        # Determine start date and num_days from filename
        start_date, num_days = guess_date_range(filename)
        if start_date is None:
            errors.append(f"{filename}: Could not determine date range — skipped.")
            continue

        daily, err = parse_usage_html(save_path, start_date, num_days)
        if err:
            errors.append(f"{filename}: {err}")
        else:
            results.extend(daily)

    # Sort by date, deduplicate (keep last)
    seen = {}
    for row in results:
        seen[row["date"]] = row
    results = sorted(seen.values(), key=lambda x: x["date"])

    # Summary stats
    total_gb   = round(sum(r["usage_gb"] for r in results), 2)
    peak_day   = max(results, key=lambda x: x["usage_gb"]) if results else None
    avg_gb     = round(total_gb / len(results), 2) if results else 0

    # Monthly totals
    monthly = {}
    for r in results:
        m = r["month"]
        monthly[m] = round(monthly.get(m, 0) + r["usage_gb"], 2)

    return jsonify({
        "daily":   results,
        "summary": {
            "total_gb":  total_gb,
            "avg_gb":    avg_gb,
            "peak_day":  peak_day,
            "num_days":  len(results),
        },
        "monthly": [{"month": k, "usage_gb": v} for k, v in monthly.items()],
        "errors":  errors
    })


@app.route("/export", methods=["POST"])
def export():
    data = request.json.get("daily", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Month", "Usage_GB"])
    for row in data:
        writer.writerow([row["date"], row["month"], row["usage_gb"]])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="daily_usage.csv"
    )


# ─────────────────────────────────────────
# HELPER: guess date range from filename
# ─────────────────────────────────────────
MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

DAYS_IN_MONTH = {
    1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
}

def guess_date_range(filename):
    """Extract start month from filename like 'Nov-December.html', 'Jan-Feb.html'"""
    name = filename.lower().replace(".html", "")
    parts = re.split(r"[-_]", name)
    for part in parts:
        for key, month_num in MONTH_MAP.items():
            if part.startswith(key):
                # Determine year: Nov/Dec = 2025, rest = 2026
                year = 2025 if month_num >= 11 else 2026
                num_days = DAYS_IN_MONTH[month_num]
                return date(year, month_num, 17), num_days
    return None, None


if __name__ == "__main__":
    app.run(debug=True, port=5000)
