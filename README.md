# 🏄 Wannasurf Scraper - Installation & Usage Guide

A Python-based scraper that extracts structured surfing data from 🌐 **[Wannasurf.com](https://www.wannasurf.com/)**, including:
- Continents and countries
- Regions and sub-regions
- Surf spots with environmental conditions, access type, wave quality, swell/wind directions, seasonal data, temperatures, coordinates, and more

📦 Output formats:
- CSV files per region/country
- Excel files per continent with predefined worksheets: `Country`, `Zones`, `Spots`

---

## ⚠ Legal & Ethical Notice

This tool is intended **strictly for educational and research purposes**.

Before using it:
- You **must ensure compliance with Wannasurf’s Terms of Service**.
- **Do not use data commercially**, redistribute it, or build competing services without explicit written permission from Wannasurf.
- Start with **sample mode**, keep the request rate low, and avoid overloading the site.

---

## 📁 Project structure

```
.
├── wannasurf_scraper.py         # Main scraper script
└── (generated during runtime)
    ├── output_csv/              # CSV files by region/country
    └── excel_output/            # Excel files by continent
````

---

## 🔧 Requirements

- **Python 3.10+**
- **pip**
- Stable **internet connection**
- Recommended: **WSL + VS Code**
- Works on **Linux / Mac / Windows**

---

## 🚀 Installation & Usage

### 1️⃣ Clone the repository

```bash
git clone https://github.com/dan-maliano/wannasurf_scraper.git
cd wannasurf-scraper
````

---

### 2️⃣ Create virtual environment & install dependencies

#### ▶ Linux / WSL

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install requests beautifulsoup4 xlsxwriter
# Optional:
# pip install pandas
```

#### 🪟 Windows (PowerShell / CMD)

```bash
python -m venv .venv
.\.venv\Scripts\activate

pip install requests beautifulsoup4 xlsxwriter
```

---

## ▶ Running the Scraper

### 🔹 Sample Mode (default & recommended first run)

```python
if __name__ == "__main__":
    # When run as a script perform a sampled scrape.
    # Set sample=False for a full scrape.
    main(sample=True)
```

**Run:**

```bash
python3 wannasurf_scraper.py
# Or on Windows:
# python wannasurf_scraper.py
```

✔ This will:

* Run a limited extraction (safe mode)
* Create **sample CSVs** under `output_csv/`
* Create **sample Excel** under `excel_output/`

---

### 🔸 Full Scrape Mode

⚠️ **Use only after testing sample mode**
⚠️ May generate high traffic + large number of files

#### Option A — modify script

```python
if __name__ == "__main__":
    main(sample=False)
```

#### Option B — run without modifying:

```bash
python3 -c "from wannasurf_scraper import main; main(sample=False)"
```

---

## 📊 Output Format

### 📂 `output_csv/`

```
USA_California.csv
USA_Hawaii.csv
Israel.csv
...
```

### 📑 `excel_output/`

```
North_America.xlsx
Europe.xlsx
Africa.xlsx
...
```

| Worksheet   | Description                                                         |
| ----------- | ------------------------------------------------------------------- |
| **Country** | One row per country with summary + seasonal values                  |
| **Zones**   | One row per region — spot count, subzones, seasonal data            |
| **Spots**   | One row per surf spot, with full wave/access/environment parameters |

📌 **Seasons format example:**

```
Jan/Feb - ...
Mar/Apr - ...
...
Nov/Dec - ...
```

---

## ⚙ Configuration

| Parameter      | Location     | Description                                                    |
| -------------- | ------------ | -------------------------------------------------------------- |
| `delay`        | `fetch()`    | Request rate limit (default: `0.5s`) → Recommended: `1.0–1.5s` |
| `sample`       | `main()`     | `True` = safe mode / `False` = full scrape                     |
| Error handling | `try/except` | Errors per region are **logged**, not blocking                 |

---

## ⏳ Usage Best Practices

✔ Add delay of **1–2 seconds per request**
✔ Do **not** run scraper repeatedly in short intervals
✔ Avoid bypassing anti-scraping protections
✔ Use realistic **User-Agent headers**

---

## 📄 License

**MIT License**

```
This software is provided "as is", without warranty of any kind.
```

> ⚠️ **IMPORTANT NOTICE**
> This license applies **only to the code**.
> Any data retrieved from **Wannasurf.com** using this tool is **not covered by this license**
> and must comply with **Wannasurf’s Terms of Service** and **local laws**.

---


