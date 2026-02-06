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
<title>ScalaWatch - Volné kanceláře</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=Spectral:wght@400;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root {{
  --ink: #1b1e27;
  --muted: #566074;
  --accent: #e4572e;
  --accent-soft: rgba(228, 87, 46, 0.12);
  --jade: #2d936c;
  --sky: #3a7ca5;
  --panel: rgba(255, 255, 255, 0.85);
  --border: rgba(27, 30, 39, 0.08);
  --shadow: 0 18px 50px rgba(19, 27, 45, 0.12);
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: "Space Grotesk", system-ui, sans-serif;
  background:
    radial-gradient(1200px 500px at 10% -10%, rgba(58, 124, 165, 0.25), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(45, 147, 108, 0.2), transparent 55%),
    linear-gradient(180deg, #f6f2ea 0%, #f1f5f7 100%);
  color: var(--ink);
  padding: 28px 18px 40px;
}}
main {{
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 22px;
}}
header {{
  background: var(--panel);
  border-radius: 18px;
  padding: 28px 30px;
  box-shadow: var(--shadow);
  border: 1px solid var(--border);
  position: relative;
  overflow: hidden;
}}
header::after {{
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(130deg, rgba(228, 87, 46, 0.12), transparent 45%);
  pointer-events: none;
}}
h1 {{
  font-family: "Spectral", serif;
  font-size: clamp(2rem, 3vw, 2.6rem);
  margin-bottom: 6px;
}}
.subtitle {{
  color: var(--muted);
  font-size: 1rem;
  max-width: 720px;
}}
.date-pill {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 8px 14px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--ink);
  font-weight: 600;
  font-size: 0.95rem;
}}
.date-pill span {{
  color: var(--accent);
}}
.cards {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 16px;
}}
.card {{
  background: var(--panel);
  border-radius: 16px;
  padding: 18px 20px;
  border: 1px solid var(--border);
  box-shadow: 0 14px 30px rgba(27, 30, 39, 0.08);
  position: relative;
  overflow: hidden;
}}
.card::before {{
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.7), transparent 45%);
  pointer-events: none;
}}
.card h3 {{
  font-size: 1.05rem;
  color: var(--muted);
  margin-bottom: 12px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}}
.metric {{
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 6px;
}}
.metric .value {{
  font-size: 2.2rem;
  font-weight: 700;
}}
.metric .unit {{
  color: var(--muted);
  font-size: 0.95rem;
}}
.card .hint {{
  color: var(--muted);
  font-size: 0.9rem;
}}
.panel {{
  background: var(--panel);
  border-radius: 18px;
  padding: 20px 22px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
}}
.panel h2 {{
  font-size: 1.2rem;
  margin-bottom: 10px;
}}
.grid {{
  display: grid;
  gap: 18px;
}}
.grid.two {{
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
}}
details {{
  background: var(--panel);
  border-radius: 18px;
  padding: 18px 22px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
}}
summary {{
  cursor: pointer;
  font-weight: 600;
  font-size: 1.05rem;
  color: var(--ink);
  margin-bottom: 10px;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}}
th, td {{
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid rgba(27, 30, 39, 0.08);
}}
th {{
  color: var(--muted);
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}}
tbody tr:hover {{
  background: rgba(58, 124, 165, 0.06);
}}
footer {{
  text-align: center;
  color: var(--muted);
  font-size: 0.9rem;
  margin-top: 12px;
}}
footer a {{
  color: var(--ink);
  text-decoration: none;
  border-bottom: 1px solid rgba(27, 30, 39, 0.3);
}}
@media (max-width: 720px) {{
  header {{
    padding: 22px;
  }}
  .panel {{
    padding: 18px;
  }}
}}
.fade-in {{
  animation: fadeIn 0.8s ease both;
}}
@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(12px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
@media (prefers-reduced-motion: reduce) {{
  .fade-in {{ animation: none; }}
}}
</style>
</head>
<body>
<main>
  <header class="fade-in">
    <h1>ScalaWatch</h1>
    <p class="subtitle">Přehled volných kanceláří v domech Scala a Jakub v Brně.</p>
    <div class="date-pill">Poslední aktualizace <span>{today_str}</span></div>
  </header>

  <section class="cards fade-in">
    <div class="card">
      <h3>Dům SCALA</h3>
      <div class="metric">
        <span class="value">{current_scala['offices']}</span>
        <span class="unit">kanceláří</span>
      </div>
      <div class="metric">
        <span class="value">{current_scala['m2']}</span>
        <span class="unit">m²</span>
      </div>
      <div class="hint">Dostupná plocha dnes</div>
    </div>
    <div class="card">
      <h3>Dům JAKUB</h3>
      <div class="metric">
        <span class="value">{current_jakub['offices']}</span>
        <span class="unit">kanceláří</span>
      </div>
      <div class="metric">
        <span class="value">{current_jakub['m2']}</span>
        <span class="unit">m²</span>
      </div>
      <div class="hint">Dostupná plocha dnes</div>
    </div>
    <div class="card">
      <h3>Celkem</h3>
      <div class="metric">
        <span class="value">{current_scala['offices'] + current_jakub['offices']}</span>
        <span class="unit">kanceláří</span>
      </div>
      <div class="metric">
        <span class="value">{current_scala['m2'] + current_jakub['m2']}</span>
        <span class="unit">m²</span>
      </div>
      <div class="hint">Oba domy dohromady</div>
    </div>
  </section>

  <section class="grid two">
    <div class="panel fade-in">
      <h2>Dostupná plocha (m²) v čase</h2>
      <canvas id="chartM2"></canvas>
    </div>
    <div class="panel fade-in">
      <h2>Počet dostupných kanceláří v čase</h2>
      <canvas id="chartCount"></canvas>
    </div>
  </section>

  <details class="fade-in">
    <summary>Historie (všechny dny)</summary>
    <table>
    <thead><tr>
      <th>Datum</th>
      <th>SCALA kanceláří</th><th>SCALA m²</th>
      <th>JAKUB kanceláří</th><th>JAKUB m²</th>
      <th>Celkem kanceláří</th><th>Celkem m²</th>
    </tr></thead>
    <tbody>
    {history_rows}
    </tbody>
    </table>
  </details>

  <footer>
    ScalaWatch — data z <a href="https://www.dumscala.cz/cs/">dumscala.cz</a>
  </footer>
</main>

<script>
Chart.defaults.font.family = '"Space Grotesk", system-ui, sans-serif';
Chart.defaults.color = "#1b1e27";
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
      {{ label: 'SCALA m²', data: scalaM2, borderColor: '#e4572e', backgroundColor: 'rgba(228,87,46,0.12)', fill: true, tension: 0.2 }},
      {{ label: 'JAKUB m²', data: jakubM2, borderColor: '#3a7ca5', backgroundColor: 'rgba(58,124,165,0.12)', fill: true, tension: 0.2 }},
      {{ label: 'Celkem m²', data: totalM2, borderColor: '#2d936c', borderDash: [5, 5], fill: false, tension: 0.2 }},
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12 }} }} }},
    scales: {{
      y: {{ beginAtZero: true, grid: {{ color: 'rgba(27, 30, 39, 0.08)' }}, title: {{ display: true, text: 'm²' }} }},
      x: {{ grid: {{ display: false }} }}
    }}
  }}
}});

new Chart(document.getElementById('chartCount'), {{
  type: 'line',
  data: {{
    labels: dates,
    datasets: [
      {{ label: 'SCALA', data: scalaCount, borderColor: '#e4572e', backgroundColor: 'rgba(228,87,46,0.12)', fill: true, tension: 0.2 }},
      {{ label: 'JAKUB', data: jakubCount, borderColor: '#3a7ca5', backgroundColor: 'rgba(58,124,165,0.12)', fill: true, tension: 0.2 }},
      {{ label: 'Celkem', data: totalCount, borderColor: '#2d936c', borderDash: [5, 5], fill: false, tension: 0.2 }},
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12 }} }} }},
    scales: {{
      y: {{ beginAtZero: true, grid: {{ color: 'rgba(27, 30, 39, 0.08)' }}, title: {{ display: true, text: 'Počet kanceláří' }} }},
      x: {{ grid: {{ display: false }} }}
    }}
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


if __name__ == "__main__":
    main()
