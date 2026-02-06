#!/usr/bin/env python3
"""ScalaWatch - scrape office availability from dumscala.cz and generate report."""

import csv
import os
import re
from collections import defaultdict
from datetime import date

import requests
from bs4 import BeautifulSoup

URL = "https://www.dumscala.cz/cs/"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
CSV_PATH = os.path.join(DATA_DIR, "offices.csv")
HTML_PATH = os.path.join(DOCS_DIR, "index.html")
CSV_HEADER = ["date", "building", "offices", "m2"]

# Building names in order they appear on the page
BUILDINGS = ["SCALA", "JAKUB"]


def scrape():
    """Scrape summary boxes and return list of dicts."""
    today = date.today().isoformat()
    try:
        resp = requests.get(URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"Fetch failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Each building has a link <a href="/cs/dum-scala/"> (or dum-jakub) immediately
    # before a <p class="text-red"> summary with office count and m².
    # We match each summary to its building via the nearest preceding link's href.
    # Mapping from href slug to building name
    slug_to_building = {"dum-scala": "SCALA", "dum-jakub": "JAKUB"}

    found = {}
    for p in soup.find_all("p", class_="text-red"):
        link = p.find_previous("a", href=True)
        if not link:
            continue
        href = link["href"]
        building = None
        for slug, name in slug_to_building.items():
            if slug in href:
                building = name
                break
        if not building:
            continue
        spans = p.find_all("span")
        if len(spans) >= 2:
            found[building] = {
                "offices": int(re.sub(r"[^\d]", "", spans[0].get_text())),
                "m2": int(re.sub(r"[^\d]", "", spans[1].get_text())),
            }

    rows = []
    for building in BUILDINGS:
        data = found.get(building, {"offices": 0, "m2": 0})
        rows.append({"date": today, "building": building, **data})

    return rows


def save_csv(rows):
    """Save rows to CSV, replacing any existing rows for the same date."""
    os.makedirs(DATA_DIR, exist_ok=True)
    today = rows[0]["date"] if rows else None

    existing = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="") as f:
            existing = [r for r in csv.DictReader(f) if r["date"] != today]

    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in existing:
            writer.writerow(row)
        for row in rows:
            writer.writerow(row)


def read_csv():
    """Read all CSV data, return list of dicts."""
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, newline="") as f:
        return list(csv.DictReader(f))


def generate_report(all_data):
    """Generate docs/index.html with Chart.js charts."""
    os.makedirs(DOCS_DIR, exist_ok=True)

    # Group by date
    daily = defaultdict(dict)
    for row in all_data:
        daily[row["date"]][row["building"]] = {
            "offices": int(row["offices"]),
            "m2": int(row["m2"]),
        }

    dates = sorted(daily.keys())

    zero = {"offices": 0, "m2": 0}
    scala_m2 = [daily[d].get("SCALA", zero)["m2"] for d in dates]
    jakub_m2 = [daily[d].get("JAKUB", zero)["m2"] for d in dates]
    total_m2 = [s + j for s, j in zip(scala_m2, jakub_m2)]
    scala_count = [daily[d].get("SCALA", zero)["offices"] for d in dates]
    jakub_count = [daily[d].get("JAKUB", zero)["offices"] for d in dates]
    total_count = [s + j for s, j in zip(scala_count, jakub_count)]

    latest = dates[-1] if dates else None
    current_scala = daily[latest].get("SCALA", zero) if latest else zero
    current_jakub = daily[latest].get("JAKUB", zero) if latest else zero

    # History table rows
    history_rows = ""
    for d in reversed(dates):
        sc = daily[d].get("SCALA", zero)
        jk = daily[d].get("JAKUB", zero)
        history_rows += f"""<tr>
            <td>{d}</td>
            <td>{sc['offices']}</td><td>{sc['m2']}</td>
            <td>{jk['offices']}</td><td>{jk['m2']}</td>
            <td>{sc['offices'] + jk['offices']}</td><td>{sc['m2'] + jk['m2']}</td>
        </tr>\n"""

    dates_js = str(dates)
    today_str = latest or "\u2014"

    html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ScalaWatch - Monitor volných kanceláří</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 20px; max-width: 1100px; margin: 0 auto; }}
h1 {{ font-size: 1.8em; margin-bottom: 4px; }}
.subtitle {{ color: #888; margin-bottom: 24px; font-size: 0.95em; }}
.cards {{ display: flex; gap: 16px; margin-bottom: 32px; flex-wrap: wrap; }}
.card {{ background: #fff; border-radius: 8px; padding: 20px; flex: 1; min-width: 200px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.card h3 {{ margin-bottom: 8px; font-size: 1.1em; }}
.card .big {{ font-size: 2em; font-weight: bold; }}
.card .unit {{ color: #888; font-size: 0.9em; }}
.chart-container {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.chart-container h2 {{ margin-bottom: 12px; font-size: 1.2em; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 24px; }}
th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #eee; }}
th {{ background: #fafafa; font-weight: 600; font-size: 0.9em; }}
details {{ margin-bottom: 24px; }}
summary {{ cursor: pointer; font-weight: 600; font-size: 1.1em; margin-bottom: 8px; }}
footer {{ text-align: center; color: #aaa; font-size: 0.85em; margin-top: 32px; }}
</style>
</head>
<body>
<h1>ScalaWatch</h1>
<p class="subtitle">Monitor volných kanceláří v domech Scala a Jakub, Brno &mdash; aktualizace: {today_str}</p>

<div class="cards">
  <div class="card">
    <h3>Dům SCALA</h3>
    <span class="big">{current_scala['offices']}</span> <span class="unit">kanceláří</span><br>
    <span class="big">{current_scala['m2']}</span> <span class="unit">m\u00b2</span>
  </div>
  <div class="card">
    <h3>Dům JAKUB</h3>
    <span class="big">{current_jakub['offices']}</span> <span class="unit">kanceláří</span><br>
    <span class="big">{current_jakub['m2']}</span> <span class="unit">m\u00b2</span>
  </div>
  <div class="card">
    <h3>Celkem</h3>
    <span class="big">{current_scala['offices'] + current_jakub['offices']}</span> <span class="unit">kanceláří</span><br>
    <span class="big">{current_scala['m2'] + current_jakub['m2']}</span> <span class="unit">m\u00b2</span>
  </div>
</div>

<div class="chart-container">
  <h2>Dostupná plocha (m\u00b2) v čase</h2>
  <canvas id="chartM2"></canvas>
</div>

<div class="chart-container">
  <h2>Počet dostupných kanceláří v čase</h2>
  <canvas id="chartCount"></canvas>
</div>

<details>
  <summary>Historie (všechny dny)</summary>
  <table>
  <thead><tr>
    <th>Datum</th>
    <th>SCALA kanceláří</th><th>SCALA m\u00b2</th>
    <th>JAKUB kanceláří</th><th>JAKUB m\u00b2</th>
    <th>Celkem kanceláří</th><th>Celkem m\u00b2</th>
  </tr></thead>
  <tbody>
  {history_rows}
  </tbody>
  </table>
</details>

<footer>
  ScalaWatch &mdash; data z <a href="https://www.dumscala.cz/cs/">dumscala.cz</a>
</footer>

<script>
const dates = {dates_js};
const scalaM2 = {scala_m2};
const jakubM2 = {jakub_m2};
const totalM2 = {total_m2};
const scalaCount = {scala_count};
const jakubCount = {jakub_count};
const totalCount = {total_count};

new Chart(document.getElementById('chartM2'), {{
  type: 'line',
  data: {{
    labels: dates,
    datasets: [
      {{ label: 'SCALA m\\u00b2', data: scalaM2, borderColor: '#e74c3c', backgroundColor: 'rgba(231,76,60,0.1)', fill: true, tension: 0.2 }},
      {{ label: 'JAKUB m\\u00b2', data: jakubM2, borderColor: '#3498db', backgroundColor: 'rgba(52,152,219,0.1)', fill: true, tension: 0.2 }},
      {{ label: 'Celkem m\\u00b2', data: totalM2, borderColor: '#2ecc71', borderDash: [5, 5], fill: false, tension: 0.2 }},
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom' }} }},
    scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'm\\u00b2' }} }} }}
  }}
}});

new Chart(document.getElementById('chartCount'), {{
  type: 'line',
  data: {{
    labels: dates,
    datasets: [
      {{ label: 'SCALA', data: scalaCount, borderColor: '#e74c3c', backgroundColor: 'rgba(231,76,60,0.1)', fill: true, tension: 0.2 }},
      {{ label: 'JAKUB', data: jakubCount, borderColor: '#3498db', backgroundColor: 'rgba(52,152,219,0.1)', fill: true, tension: 0.2 }},
      {{ label: 'Celkem', data: totalCount, borderColor: '#2ecc71', borderDash: [5, 5], fill: false, tension: 0.2 }},
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom' }} }},
    scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'Počet kanceláří' }} }} }}
  }}
}});
</script>
</body>
</html>"""

    with open(HTML_PATH, "w") as f:
        f.write(html)
    print(f"Report written to {HTML_PATH}")


def main():
    rows = scrape()
    if rows:
        for r in rows:
            print(f"  {r['building']}: {r['offices']} offices, {r['m2']} m2")
        save_csv(rows)
        print(f"Saved to {CSV_PATH}")
    else:
        print("Scrape failed; leaving existing data unchanged")

    all_data = read_csv()
    generate_report(all_data)


if __name__ == "__main__":
    main()
