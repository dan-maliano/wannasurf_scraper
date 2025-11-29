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

