````markdown
# Wannasurf Scraper

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

```text
.
├── wannasurf_scraper.py         # Main scraper script
└── (generated during runtime)
    ├── output_csv/              # CSV files by region/country
    └── excel_output/            # Excel files by continent
````

---

## 🔧 Requirements

* Python 3.10+
* pip
* Stable internet connection
* Recommended: **WSL + VS Code**
* Can also work on native Linux/Mac/Windows

---

## 🚀 Installation & Usage

### 1️⃣ Clone the repository

```bash
git clone <YOUR-REPO-URL> wannasurf-scraper
cd wannasurf-scraper
```

### 2️⃣ Create virtual environment and install dependencies

#### Linux / WSL

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install requests beautifulsoup4 xlsxwriter
# Optional:
# pip install pandas
```

#### Windows (PowerShell / CMD)

```bash
python -m venv .venv
.\.venv\Scripts\activate

pip install requests beautifulsoup4 xlsxwriter
```

---

## ▶ Running the scraper

### 🔹 Sample Mode (default)

```python
if __name__ == "__main__":
    # When run as a script perform a sampled scrape.
    # Set sample=False for a full scrape.
    main(sample=True)
```

Run:

```bash
python3 wannasurf_scraper.py
# Or on Windows:
# python wannasurf_scraper.py
```

✔ This will:

* Run a limited extraction (safe mode)
* Create sample CSVs under `output_csv/`
* Create an example Excel file under `excel_output/`

---

### 🔸 Full Scrape Mode

> ⚠ Not recommended unless sample mode was successfully tested
> ⚠ May generate high traffic and many files

Change script:

```python
if __name__ == "__main__":
    main(sample=False)
```

Or run without modifying:

```bash
python3 -c "from wannasurf_scraper import main; main(sample=False)"
```

---

## 📊 Output Format

### 📂 `output_csv/`

```text
USA_California.csv
USA_Hawaii.csv
Israel.csv
...
```

### 📑 `excel_output/`

```text
North_America.xlsx
Europe.xlsx
Africa.xlsx
...
```

Each Excel file contains:

| Worksheet | Description                                                             |
| --------- | ----------------------------------------------------------------------- |
| `Country` | One row per country, including summary data and seasonal values         |
| `Zones`   | One row per region, with surf spot count, subzones, seasonal conditions |
| `Spots`   | One row per surf spot, including all extracted parameters               |

📌 Seasons are formatted per two-month period:

```
Jan/Feb - ...
Mar/Apr - ...
...
Nov/Dec - ...
```

---

## ⚙ Configuration

| Parameter      | Location          | Description                                                        |
| -------------- | ----------------- | ------------------------------------------------------------------ |
| `delay`        | fetch()           | Request rate limit (default: `0.5s`). Recommended: `1.0–1.5s`.     |
| `sample`       | main()            | Set to `True` for safe mode, `False` full data                     |
| Error handling | try/except blocks | Exceptions per country/region are logged but do not stop execution |

---

## ⏳ Usage Best Practices

✔ Add delay of **1–2 seconds per request**
✔ Do **not** run the scraper repeatedly in short intervals
✔ Avoid bypassing anti-scraping protections
✔ Use realistic User-Agent headers

---

## 📄 License

```
MIT License

This software is provided "as is", without warranty of any kind.

IMPORTANT NOTICE:
This license applies ONLY to the software/code.
Any data retrieved using this tool from Wannasurf.com is NOT covered by this license
and must comply with Wannasurf’s Terms of Service and any applicable laws.
```

📌 **License summary in README:**

> 📝 **License:** Code is licensed under MIT.
> ⚠️ Data retrieved using this tool from Wannasurf.com is subject to the website’s Terms of Service and is **not covered** by this license.

---

## 💡 Optional – `requirements.txt`

```
requests
beautifulsoup4
xlsxwriter
# pandas  # optional
```

Install via:

```bash
pip install -r requirements.txt
```

---

## 🏁 Final Notes

* First run recommended:

```bash
python3 wannasurf_scraper.py
```

* After validation → switch to:

```bash
main(sample=False)
```

If you plan to use collected data in any form of publication or external project, contact Wannasurf.com to request permission.


```


