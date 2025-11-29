#!/usr/bin/env python3
"""
Wannasurf scraper
=================

This module defines a set of functions for scraping surfing information from
``https://www.wannasurf.com``.  The site organises information hierarchically
by continents, countries, zones (regions) and individual surf spots.  Each
country or zone page contains meta‑information (about text, seasonal data,
maps) and lists of sub‑regions or surf spots.  Surf spot pages provide
detailed descriptions, access information, environmental conditions and
geographical coordinates.

The scraper implements the extraction rules outlined in the ``הוראות
לסקרייפינג.docx`` document supplied by the user.  The core tasks are:

* Enumerate all continents and their countries from the homepage.
* For each country, fetch the “About”, “At a glance” and “Seasons” sections
  and detect when these are empty.
* Discover zones and surf spots within a country; some countries skip zones
  entirely and list surf spots directly.  Some countries have two nested
  levels of zones.
* For each zone, fetch the same meta‑information as for countries and
  recursively enumerate sub‑zones and surf spots.
* For each surf spot, extract the following fields:

    - surf spot name
    - Distance
    - Walk
    - Easy to find?
    - Public access?
    - Special access
    - Wave quality
    - Experience
    - Frequency
    - Type
    - Direction
    - Bottom
    - Power
    - Normal length
    - Good day length
    - Good swell direction
    - Good wind direction
    - Swell size
    - Best tide position
    - Best tide movement
    - Additional Information
    - Latitude
    - Longitude

Where a field is missing on the page the scraper returns an empty string.

The script can produce individual CSV files per zone (or country when there
are no zones) and a multi‑sheet Excel workbook summarising the data by
continent, country and zone.  See the ``main`` function at the bottom of
this file for an example of how to drive the scraper.

Note: Scraping the entire site (eight continents, 181 countries, ~310
zones and roughly 9,500 surf spots) will take a significant amount of
time and bandwidth.  The code is written to be modular; if you only need
data for a subset of the hierarchy, adjust the logic in ``main``
accordingly.
"""

import csv
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


BASE_URL = "https://www.wannasurf.com"

# Toggle verbose debugging output.  When True, the scraper will print
# additional information about each page it processes (URLs being
# fetched, section headings found, extracted fields, etc.).  This is
# useful when diagnosing why certain fields are empty in the output.
DEBUG = True


def fetch(url: str, *, delay: float = 0.5) -> str:
    """Fetch a URL and return its text content.

    A small delay is enforced between requests to avoid overwhelming the
    remote server.  Raises an exception if the request fails.

    Args:
        url: Absolute or relative URL to fetch.
        delay: Seconds to wait before the request.  Defaults to 0.5 seconds.

    Returns:
        The response body decoded as text.
    """
    time.sleep(delay)
    # Support both relative and absolute paths
    if not url.startswith("http"):
        url = urljoin(BASE_URL, url)
    # Use a realistic desktop user‑agent to reduce the chance of being blocked
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/96.0.4664.110 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    if DEBUG:
        print(f"[fetch] Fetched {url} (length={len(resp.text)})")
    return resp.text


def clean_text(text: str) -> str:
    """Collapse whitespace and unescape special characters.

    Args:
        text: Raw text extracted from the HTML.

    Returns:
        A cleaned string with consecutive whitespace collapsed into single
        spaces and leading/trailing whitespace removed.
    """
    if not text:
        return ""
    # Replace non‑breaking spaces and other whitespace with regular spaces
    text = text.replace("\xa0", " ")
    # Collapse whitespace
    return re.sub(r"\s+", " ", text).strip()


def parse_seasons_table(table: Tag, *, months_format: str = "bi") -> Dict[str, Dict[str, str]]:
    """Parse a seasons table and return a mapping of month groups to values.

    The table structure differs slightly between country and zone pages:

    * Country pages group months in pairs: Jan/Feb, Mar/Apr, ...
    * Zone pages list each month individually.

    Each row of the table corresponds to a different metric (e.g. Best
    Surfing Season, Typical Swell Size, Surf Equipment, etc.).  For the
    first two rows the cells contain images whose filenames encode a rating
    (number of stars or swell blocks).  For the remaining rows the cells
    contain plain text.

    Args:
        table: A BeautifulSoup Tag representing the <table> element.
        months_format: Either "bi" for bi‑monthly pairs or "single" for
            individual months.

    Returns:
        A nested dictionary keyed first by the metric name (lowercase
        underscored), then by the month key (e.g. "jan_feb" or "jan").  The
        values are strings; missing values are returned as "" or "0" (for
        missing images).
    """
    result: Dict[str, Dict[str, str]] = {}

    # Extract header titles to determine month keys
    header_cells = table.find("thead").find_all("th")
    # Skip the first header cell (empty) and the first row's grouped cell
    # The relevant month headers start from the second row of the header
    month_headers: List[str] = []
    thead_rows = table.find("thead").find_all("tr")
    if months_format == "bi":
        # On country pages the second header row contains month pairs (Jan/Feb)
        if len(thead_rows) > 1:
            month_cells = thead_rows[1].find_all("th")
            for cell in month_cells:
                # Use lowercase with underscore
                month_key = cell.get_text(strip=True).lower().replace("/", "_")
                month_key = month_key.replace(" ", "_")
                month_headers.append(month_key)
    else:
        # On zone pages the months appear in the first header row after an
        # initial empty cell
        if len(thead_rows) >= 1:
            # there may be two header rows depending on implementation
            # search for the row that contains month names (e.g. Jan)
            for row in thead_rows:
                cells = [c.get_text(strip=True) for c in row.find_all("th")]
                # If at least one cell matches a month name (Jan, Feb, Mar...), use this row
                months = []
                for c in cells:
                    if re.match(r"[A-Za-z]{3}$", c):
                        months.append(c)
                if months:
                    month_headers = [m.lower() for m in months]
                    break

    # Build result dict for each metric row
    body_rows = table.find("tbody").find_all("tr")
    for row in body_rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        metric_name = clean_text(cells[0].get_text()).lower().replace(" ", "_").replace(".", "")
        values: Dict[str, str] = {}
        # Iterate over month cells
        for idx, month_key in enumerate(month_headers):
            # Some tables include header cells in the first column; adjust index
            cell_index = idx + 1  # offset because cells[0] is metric name
            if cell_index >= len(cells):
                values[month_key] = ""
                continue
            cell = cells[cell_index]
            # For rating rows the cell may contain an <img>
            img = cell.find("img")
            if img:
                src = img.get("src", "")
                filename = os.path.basename(urlparse(src).path)
                # 'wanna-empty-1x1.gif' denotes a missing value
                if filename.lower().startswith("wanna-empty"):
                    values[month_key] = "0"
                else:
                    values[month_key] = filename
            else:
                text = clean_text(cell.get_text())
                values[month_key] = text
        if DEBUG:
            # Print a snapshot of the seasons row for debugging
            print(f"[parse_seasons_table] metric '{metric_name}' values: {values}")
        result[metric_name] = values
    return result


@dataclass
class Spot:
    """Representation of a surf spot with all extracted fields."""
    name: str
    distance: str = ""
    walk: str = ""
    easy_to_find: str = ""
    public_access: str = ""
    special_access: str = ""
    wave_quality: str = ""
    experience: str = ""
    frequency: str = ""
    type: str = ""
    direction: str = ""
    bottom: str = ""
    power: str = ""
    normal_length: str = ""
    good_day_length: str = ""
    good_swell_direction: str = ""
    good_wind_direction: str = ""
    swell_size: str = ""
    best_tide_position: str = ""
    best_tide_movement: str = ""
    additional_information: str = ""
    latitude: str = ""
    longitude: str = ""

    def to_row(self) -> List[str]:
        """Convert the spot into a CSV row following the specified order."""
        return [
            self.name,
            self.distance,
            self.walk,
            self.easy_to_find,
            self.public_access,
            self.special_access,
            self.wave_quality,
            self.experience,
            self.frequency,
            self.type,
            self.direction,
            self.bottom,
            self.power,
            self.normal_length,
            self.good_day_length,
            self.good_swell_direction,
            self.good_wind_direction,
            self.swell_size,
            self.best_tide_position,
            self.best_tide_movement,
            self.additional_information,
            self.latitude,
            self.longitude,
        ]


def parse_spot_page(url: str) -> Spot:
    """Parse a surf spot page and return a Spot instance.

    Args:
        url: Absolute or relative URL of the surf spot page.

    Returns:
        A Spot populated with extracted data.  Any missing field is set
        to the empty string.
    """
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    # Spot name appears in the <title> tag before a hyphen
    title = soup.find("title").get_text(strip=True) if soup.find("title") else ""
    name = title.split(" - ")[0] if title else url.split("/")[-2]
    spot = Spot(name=name)

    if DEBUG:
        print(f"[parse_spot_page] Parsing spot page: {url}")
        print(f"[parse_spot_page] Spot name: {spot.name}")

    # Access section
    # The <h3> headers on spot pages often contain nested <a> tags and nbsp characters,
    # so .string is usually None.  Instead, iterate over all h3.wanna-item elements
    # and match on their full text.
    access_header = None
    for h in soup.find_all("h3", class_="wanna-item"):
        text = clean_text(h.get_text())
        if text.lower().endswith("access"):
            access_header = h
            break
    if access_header:
        access_table = access_header.find_next("table")
        if access_table:
            # Each <p> in the table contains a <span class="wanna-item-label"> for the label
            # followed by the value. Skip descriptive paragraphs without a label span.
            for p in access_table.find_all("p"):
                label_span = p.find("span", class_="wanna-item-label")
                if not label_span:
                    continue
                label = clean_text(label_span.get_text()).rstrip(":").lower()
                # Remove all label spans so that the remaining text is the value
                for span in p.find_all("span"):
                    span.extract()
                value = clean_text(p.get_text())
                if label == "distance":
                    spot.distance = value
                elif label == "walk":
                    spot.walk = value
                elif label == "easy to find?":
                    spot.easy_to_find = value
                elif label == "public access?":
                    spot.public_access = value
                elif label == "special access":
                    spot.special_access = value
        if DEBUG:
            print(f"[parse_spot_page] Access parsed for {spot.name}: distance='{spot.distance}', walk='{spot.walk}', easy='{spot.easy_to_find}', public='{spot.public_access}', special='{spot.special_access}'")

    # Surf Spot Characteristics section
    characteristics_header = None
    for h in soup.find_all("h3", class_="wanna-item"):
        text = clean_text(h.get_text())
        if "surf spot characteristics" in text.lower():
            characteristics_header = h
            break
    if characteristics_header:
        # There are two columns: left and right.  We'll parse both by looking for
        # <h5> headings followed by multiple <p> lines.
        left_col = soup.find(id="wanna-item-specific-2columns-left")
        right_col = soup.find(id="wanna-item-specific-2columns-right")
        for col in [left_col, right_col]:
            if not col:
                continue
            current_section = None
            for child in col.children:
                if isinstance(child, Tag):
                    if child.name == "h5":
                        current_section = clean_text(child.get_text()).lower()
                    elif child.name == "p":
                        label_span = child.find("span", class_="wanna-item-label")
                        if not label_span:
                            continue
                        label = clean_text(label_span.get_text()).rstrip(":").lower()
                        for span in child.find_all("span"):
                            span.extract()
                        value = clean_text(child.get_text())
                        # Map labels to Spot fields
                        if label == "wave quality":
                            spot.wave_quality = value
                        elif label == "experience":
                            spot.experience = value
                        elif label == "frequency":
                            spot.frequency = value
                        elif label == "type":
                            spot.type = value
                        elif label == "direction":
                            spot.direction = value
                        elif label == "bottom":
                            spot.bottom = value
                        elif label == "power":
                            spot.power = value
                        elif label == "normal length":
                            spot.normal_length = value
                        elif label == "good day length":
                            spot.good_day_length = value
                        elif label == "good swell direction":
                            spot.good_swell_direction = value
                        elif label == "good wind direction":
                            spot.good_wind_direction = value
                        elif label == "swell size":
                            spot.swell_size = value
                        elif label == "best tide position":
                            spot.best_tide_position = value
                        elif label == "best tide movement":
                            spot.best_tide_movement = value
        if DEBUG:
            print(f"[parse_spot_page] Characteristics parsed for {spot.name}: wave_quality='{spot.wave_quality}', experience='{spot.experience}', frequency='{spot.frequency}', type='{spot.type}', direction='{spot.direction}', bottom='{spot.bottom}', power='{spot.power}', normal_length='{spot.normal_length}', good_day_length='{spot.good_day_length}', good_swell_direction='{spot.good_swell_direction}', good_wind_direction='{spot.good_wind_direction}', swell_size='{spot.swell_size}', best_tide_position='{spot.best_tide_position}', best_tide_movement='{spot.best_tide_movement}'")

    # Additional Information section
    # Additional Information section
    additional_header = None
    for h in soup.find_all("h3", class_="wanna-item"):
        text = clean_text(h.get_text())
        if text.lower().startswith("additional information"):
            additional_header = h
            break
    if additional_header:
        # First <p style="display:inline"> holds the general additional info
        p_inline = additional_header.find_next("p", attrs={"style": lambda x: x and "display:inline" in x})
        if p_inline:
            spot.additional_information = clean_text(p_inline.get_text())

    if DEBUG:
        print(f"[parse_spot_page] Additional info for {spot.name}: '{spot.additional_information}'")
    # Coordinates (Latitude and Longitude)
    # Some pages list GPS coordinates in a <p> with two spans labelled "Latitude" and "Longitude".
    # Instead of relying on a regex that may miss the values, we directly fetch the sibling text after each label.
    lat_span = soup.find("span", class_="wanna-item-label-gps", string=lambda x: x and "Latitude" in x)
    lon_span = soup.find("span", class_="wanna-item-label-gps", string=lambda x: x and "Longitude" in x)
    if lat_span:
        # The value is the next sibling (text node) after the span.  Clean it and strip trailing/leading whitespace.
        lat_text = lat_span.next_sibling
        if lat_text:
            spot.latitude = clean_text(BeautifulSoup(str(lat_text), "html.parser").get_text())
    if lon_span:
        lon_text = lon_span.next_sibling
        if lon_text:
            spot.longitude = clean_text(BeautifulSoup(str(lon_text), "html.parser").get_text())

    if DEBUG:
        print(f"[parse_spot_page] Coordinates for {spot.name}: lat='{spot.latitude}', lon='{spot.longitude}'")

    # Normalize missing values: if any of the fields are empty after parsing, set them to "empty" to
    # explicitly record absence of information.
    for field_name in [
        "distance",
        "walk",
        "easy_to_find",
        "public_access",
        "special_access",
        "wave_quality",
        "experience",
        "frequency",
        "type",
        "direction",
        "bottom",
        "power",
        "normal_length",
        "good_day_length",
        "good_swell_direction",
        "good_wind_direction",
        "swell_size",
        "best_tide_position",
        "best_tide_movement",
        "latitude",
        "longitude",
        "additional_information",
    ]:
        val = getattr(spot, field_name)
        if not val:
            setattr(spot, field_name, "empty")

    return spot


@dataclass
class Zone:
    """Representation of a zone (or country when there are no zones)."""
    name: str
    url: str
    about: str = ""
    at_a_glance: str = ""  # Only populated for countries
    seasons: Dict[str, Dict[str, str]] = field(default_factory=dict)
    additional_map: Optional[str] = None
    surf_spots: List[Spot] = field(default_factory=list)
    sub_zones: List['Zone'] = field(default_factory=list)

    def is_leaf(self) -> bool:
        """Return True if the zone has no sub‑zones (contains only surf spots)."""
        return not self.sub_zones

    def to_csv(self, directory: str) -> str:
        """Write the surf spots of this zone to a CSV file.

        If the zone contains no surf spots, an empty CSV will be created with
        only the header row.  Returns the path to the CSV file.
        """
        safe_name = re.sub(r"[^A-Za-z0-9_]+", "_", self.name)[:50]
        filename = f"{safe_name}.csv"
        path = os.path.join(directory, filename)
        os.makedirs(directory, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "surf spot name", "Distance", "Walk", "Easy to find?",
                "Public access?", "Special access", "Wave quality", "Experience",
                "Frequency", "Type", "Direction", "Bottom", "Power",
                "Normal length", "Good day length", "Good swell direction",
                "Good wind direction", "Swell size", "Best tide position",
                "Best tide movement", "Additional Information", "Latitude", "Longitude",
            ])
            for spot in self.surf_spots:
                writer.writerow(spot.to_row())
        return path


def parse_country_or_zone_page(url: str, *, is_country: bool) -> Zone:
    """Parse a country or zone page.

    The HTML structure of country and zone pages on Wannasurf is very
    similar; both use the same tab identifiers (e.g. ``wanna-country-tab-about``)
    even when the page represents a zone.  This function consolidates the
    parsing logic for both.

    Args:
        url: Absolute or relative URL of the country or zone page.
        is_country: Set to True when parsing a country page.  If False
            the parser treats the page as a zone and does not attempt to
            parse an "At a glance" section.

    Returns:
        A populated ``Zone`` instance.  The ``sub_zones`` and ``surf_spots``
        lists may be empty depending on the page contents.
    """
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    # Determine display name from the page title
    title = soup.find("title").get_text(strip=True) if soup.find("title") else url.split("/")[-2]
    name = title.split(" - ")[0] if title else url.split("/")[-2]
    zone = Zone(name=name, url=url)

    if DEBUG:
        print(f"[parse_country_or_zone_page] Parsing {'country' if is_country else 'zone'} page: {url}")
        print(f"[parse_country_or_zone_page] Name detected: {zone.name}")

    # About text
    about_div = soup.find(id="wanna-country-tab-about")
    if about_div:
        p_inline = about_div.find("p", attrs={"style": lambda x: x and "display:inline" in x})
        # Fallback: some pages use <p> without inline style for about
        if not p_inline:
            p_inline = about_div.find("p")
        about_text = clean_text(p_inline.get_text()) if p_inline else ""
        # Detect empty placeholder
        if about_text and not about_text.lower().startswith("wanna add some info"):
            zone.about = about_text
        else:
            if DEBUG:
                print(f"[parse_country_or_zone_page] About is empty for {zone.name}")

    # At a glance (only for countries)
    if is_country:
        infos_div = soup.find(id="wanna-country-tab-infos")
        if infos_div:
            info_text = clean_text(infos_div.get_text(" ", strip=True))
            if info_text and "automatic build" not in info_text.lower():
                zone.at_a_glance = info_text
            else:
                if DEBUG:
                    print(f"[parse_country_or_zone_page] 'At a glance' empty or automatic for {zone.name}")

    # Seasons table
    additional_div = soup.find(id="wanna-country-tab-additional-info")
    seasons_table = additional_div.find(id="wanna-season-table") if additional_div else None
    if seasons_table:
        months_format = "bi" if is_country else "bi"
        # Note: both country and zone pages often use bi‑monthly tables.  Some
        # zones may have single month tables; if single month headers are
        # detected ``parse_seasons_table`` will handle them automatically.
        zone.seasons = parse_seasons_table(seasons_table, months_format="bi")
        if DEBUG:
            print(f"[parse_country_or_zone_page] Seasons parsed for {zone.name}: keys={list(zone.seasons.keys())}")

    # Additional map (zone specific)
    # It appears under <div id="wanna-item-tab-additional-map">
    map_div = soup.find(id="wanna-item-tab-additional-map")
    if map_div:
        img_tag = map_div.find("img")
        if img_tag and img_tag.get("src"):
            zone.additional_map = urljoin(BASE_URL, img_tag["src"])
            if DEBUG:
                print(f"[parse_country_or_zone_page] Additional map for {zone.name}: {zone.additional_map}")

    # Discover sub‑zones and surf spots
    zones_list: List[Tuple[str, str]] = []
    spots_list: List[Tuple[str, str]] = []

    # Find the "Zones" table
    zones_header = soup.find("h3", class_="wanna-item", string=lambda x: x and "Zones" in x)
    if zones_header:
        table = zones_header.find_next("table")
        if table:
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if not cells:
                    continue
                link = cells[0].find("a")
                if not link:
                    continue
                z_name = clean_text(link.get_text())
                z_url = urljoin(BASE_URL, link.get("href"))
                # Add the sub-zone to the list of zones
                zones_list.append((z_name, z_url))
                # Debug: log each discovered sub-zone
                if DEBUG:
                    print(f"[parse_country_or_zone_page] Found sub-zone: {z_name} -> {z_url}")

    # Find surf spots table (spots not associated with zones)
    spots_header = soup.find("h3", class_="wanna-item", string=lambda x: x and "Surf Spots" in x)
    if spots_header:
        table = spots_header.find_next("table")
        if table:
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if not cells:
                    continue
                link = cells[0].find("a")
                if not link:
                    continue
                s_name = clean_text(link.get_text())
                s_url = urljoin(BASE_URL, link.get("href"))
                # Add the spot to the list of spots not associated with any zone
                spots_list.append((s_name, s_url))
                # Debug: log each discovered spot in this category
                if DEBUG:
                    print(f"[parse_country_or_zone_page] Found spot: {s_name} -> {s_url}")

    # Populate surf spots list by parsing each spot page
    for s_name, s_url in spots_list:
        try:
            if DEBUG:
                print(f"[parse_country_or_zone_page] Parsing spot '{s_name}' at {s_url}")
            spot = parse_spot_page(s_url)
            zone.surf_spots.append(spot)
            if DEBUG:
                print(f"[parse_country_or_zone_page] Added spot: {spot.name}")
        except Exception as e:
            # If a spot fails to parse, continue with others
            print(f"Warning: failed to parse spot {s_name} at {s_url}: {e}")

    # Recursively parse sub‑zones
    for z_name, z_url in zones_list:
        try:
            if DEBUG:
                print(f"[parse_country_or_zone_page] Parsing sub-zone '{z_name}' at {z_url}")
            sub_zone = parse_country_or_zone_page(z_url, is_country=False)
            zone.sub_zones.append(sub_zone)
            if DEBUG:
                print(f"[parse_country_or_zone_page] Added sub-zone: {sub_zone.name} with {len(sub_zone.surf_spots)} spots and {len(sub_zone.sub_zones)} subzones")
        except Exception as e:
            print(f"Warning: failed to parse zone {z_name} at {z_url}: {e}")

    return zone


def parse_homepage() -> Dict[str, List[Tuple[str, str]]]:
    """Parse the Wannasurf homepage and return a mapping of continents to countries.

    Returns:
        A dictionary keyed by continent name.  Each value is a list of
        tuples ``(country_name, country_url)``.
    """
    html = fetch(BASE_URL + "/")
    soup = BeautifulSoup(html, "html.parser")
    continents: Dict[str, List[Tuple[str, str]]] = {}

    # Continents are indicated by <h2 class="wanna-title-continent">
    for h2 in soup.find_all("h2", class_=re.compile("wanna-title-continent")):
        continent_link = h2.find("a")
        continent_name = clean_text(continent_link.get_text()) if continent_link else clean_text(h2.get_text())
        continent_countries: List[Tuple[str, str]] = []
        # The following <table> contains countries as <a> tags
        table = h2.find_next("table")
        if table:
            for a in table.find_all("a", class_=re.compile("wanna-main-menu-static-tabbar-submenu")):
                c_name = clean_text(a.get_text())
                c_url = urljoin(BASE_URL, a.get("href"))
                continent_countries.append((c_name, c_url))
        continents[continent_name] = continent_countries
    return continents


def build_excel_workbook(continents_data: Dict[str, Dict[str, Zone]], *, output_dir: str) -> None:
    """
    Construct detailed Excel workbooks for each continent.

    This function produces one Excel file per continent.  Within each
    workbook the sheets mirror the structure of the example provided by
    the user:

    * The first sheet ("Country") lists all countries in the continent and
      includes the "about" text, "at a glance" text and a multi‑column
      summary of seasonal information (best surfing season, typical swell
      size, surf equipment, water temperature and air temperature).  When
      a country is missing a particular field or seasonal value the cell
      contains the string "empty".

    * The second sheet ("Zones") lists all top‑level zones for each
      country.  Each row contains the parent country name, the zone name,
      the number of surf spots and sub‑zones, the zone's "about" text and
      seasonal data formatted in the same way as in the country sheet.
      Countries without zones are omitted from this sheet.

    * For any zone that itself contains sub‑zones a third sheet is
      created.  The sheet name is derived from the zone name (sanitised
      for Excel) and lists all of its sub‑zones along with the same
      columns as the "Zones" sheet.

    * For each leaf zone (a zone with no further sub‑zones) a final
      sheet is created containing a table of its surf spots.  Columns
      include all of the fields specified in the scraping instructions: the
      surf spot name, access details, wave and tide characteristics and
      coordinates.

    Args:
        continents_data: Mapping from continent name to a mapping of
            country name -> ``Zone`` object (representing the country).
        output_dir: Directory where the per‑continent XLSX files will be
            saved.  The directory will be created if it does not exist.
    """
    import xlsxwriter

    os.makedirs(output_dir, exist_ok=True)

    # Helper to convert seasons dict to newline separated strings for each metric
    def format_seasons(seasons: Dict[str, Dict[str, str]], metric_key: str) -> str:
        """Format seasonal data for a single metric.

        ``seasons`` is a nested dict returned from ``parse_seasons_table`` and
        ``metric_key`` is one of ``best_surfing_season``, ``typical_swell_size``,
        ``surf_equipment``, ``water_temp`` or ``air_temp``.  The values are
        returned as a string containing one line per month or month pair in
        the form "Jan/Feb - value".  Missing or zero values are replaced by
        the word "empty".
        """
        # Default months for bi‑monthly tables
        default_months = [
            "jan_feb", "mar_apr", "may_jun", "jul_aug", "sep_oct", "nov_dec"
        ]
        # If the seasons dict is empty or the metric is missing, return all months as empty
        if not seasons or metric_key not in seasons:
            return "\n".join(
                [f"{m.replace('_', '/').title()} - empty" for m in default_months]
            )
        # Otherwise build rows, filling in missing months as empty
        rows = []
        for month in default_months:
            val = seasons[metric_key].get(month, "")
            month_label = month.replace("_", "/").title()
            if not val or val == "0":
                rows.append(f"{month_label} - empty")
            else:
                rows.append(f"{month_label} - {val}")
        return "\n".join(rows)

    # Define the order of seasonal metrics and their display names
    season_metrics = [
        ("best_surfing_season", "best surfing"),
        ("typical_swell_size", "Typical Swell Size"),
        ("surf_equipment", "Surf Equipment"),
        ("water_temp", "Water temp."),
        ("air_temp", "Air temp."),
    ]

    for continent, countries in continents_data.items():
        # Build file path for this continent
        safe_continent = re.sub(r"[^A-Za-z0-9_]+", "_", continent)[:50]
        workbook_path = os.path.join(output_dir, f"{safe_continent}.xlsx")
        workbook = xlsxwriter.Workbook(workbook_path)
        # Track created sheet names to avoid collisions
        created_sheets = set()

        # COUNTRY SHEET
        country_sheet = workbook.add_worksheet("Country")
        created_sheets.add("Country")
        # Write header rows
        # Row 0: high level headers
        headers_lvl0 = ["country", "continent", "about", "at a glance", "seasons", "", "", "", ""]
        for col, val in enumerate(headers_lvl0):
            country_sheet.write(0, col, val)
        # Row 1: second level headers for seasonal metrics
        headers_lvl1 = ["", "", "", "", season_metrics[0][1], season_metrics[1][1], season_metrics[2][1], season_metrics[3][1], season_metrics[4][1]]
        for col, val in enumerate(headers_lvl1):
            country_sheet.write(1, col, val)
        row_idx = 2
        for country_name, zone_obj in countries.items():
            # Country row values
            country_sheet.write(row_idx, 0, country_name)
            country_sheet.write(row_idx, 1, continent)
            country_sheet.write(row_idx, 2, zone_obj.about if zone_obj.about else "empty")
            country_sheet.write(row_idx, 3, zone_obj.at_a_glance if zone_obj.at_a_glance else "empty")
            # Seasonal metrics
            for i, (metric_key, _) in enumerate(season_metrics):
                val = format_seasons(zone_obj.seasons, metric_key)
                country_sheet.write(row_idx, 4 + i, val)
            row_idx += 1

        # ZONES SHEET
        zones_sheet = workbook.add_worksheet("Zones")
        created_sheets.add("Zones")
        # Row 0
        zones_headers_lvl0 = ["country", "Zones (count)", "Surf Spots", "Sub zones", "about", "at a glance", "seasons", "", "", "", ""]
        for col, val in enumerate(zones_headers_lvl0):
            zones_sheet.write(0, col, val)
        zones_headers_lvl1 = ["", "", "", "", "", "", season_metrics[0][1], season_metrics[1][1], season_metrics[2][1], season_metrics[3][1], season_metrics[4][1]]
        for col, val in enumerate(zones_headers_lvl1):
            zones_sheet.write(1, col, val)
        z_row_idx = 2
        # Track zones that have sub‑zones to create further sheets
        nested_zones: List[Tuple[str, Zone]] = []
        for country_name, country_zone in countries.items():
            for zone_obj in country_zone.sub_zones:
                zones_sheet.write(z_row_idx, 0, country_name)
                zones_sheet.write(z_row_idx, 1, zone_obj.name)
                zones_sheet.write(z_row_idx, 2, len(zone_obj.surf_spots))
                zones_sheet.write(z_row_idx, 3, len(zone_obj.sub_zones))
                zones_sheet.write(z_row_idx, 4, zone_obj.about if zone_obj.about else "empty")
                # 'At a glance' is only defined for countries, not zones; leave empty
                zones_sheet.write(z_row_idx, 5, "empty")
                for i, (metric_key, _) in enumerate(season_metrics):
                    val = format_seasons(zone_obj.seasons, metric_key)
                    zones_sheet.write(z_row_idx, 6 + i, val)
                # If this zone has sub‑zones record it for creating a separate sheet later
                if zone_obj.sub_zones:
                    nested_zones.append((zone_obj.name, zone_obj))
                z_row_idx += 1
        # SUB‑ZONES sheets
        for z_name, z_obj in nested_zones:
            # Sanitize sheet name
            sheet_name = re.sub(r"[^A-Za-z0-9_]+", "_", z_name)[:31]
            # Ensure unique sheet name
            suffix = 1
            base_name = sheet_name
            while sheet_name in created_sheets:
                sheet_name = f"{base_name[:28]}_{suffix}"
                suffix += 1
            sub_sheet = workbook.add_worksheet(sheet_name)
            created_sheets.add(sheet_name)
            # Headers similar to zones sheet but first column is parent zone
            sub_headers_lvl0 = ["Zone", "Zones (count)", "Surf Spots", "Sub zones", "about", "seasons", "", "", "", ""]
            for col, val in enumerate(sub_headers_lvl0):
                sub_sheet.write(0, col, val)
            sub_headers_lvl1 = ["", "", "", "", "", season_metrics[0][1], season_metrics[1][1], season_metrics[2][1], season_metrics[3][1], season_metrics[4][1]]
            for col, val in enumerate(sub_headers_lvl1):
                sub_sheet.write(1, col, val)
            s_row = 2
            for sub_zone in z_obj.sub_zones:
                sub_sheet.write(s_row, 0, z_obj.name)
                sub_sheet.write(s_row, 1, sub_zone.name)
                sub_sheet.write(s_row, 2, len(sub_zone.surf_spots))
                sub_sheet.write(s_row, 3, len(sub_zone.sub_zones))
                sub_sheet.write(s_row, 4, sub_zone.about if sub_zone.about else "empty")
                for i, (metric_key, _) in enumerate(season_metrics):
                    val = format_seasons(sub_zone.seasons, metric_key)
                    sub_sheet.write(s_row, 5 + i, val)
                s_row += 1
        # SURF SPOTS sheets for leaf zones
        for country_name, country_zone in countries.items():
            # If country has no zones, treat as a single zone for spots
            leaf_zones = []
            if not country_zone.sub_zones:
                leaf_zones.append((country_zone.name, country_zone))
            else:
                for z_obj in country_zone.sub_zones:
                    if not z_obj.sub_zones:
                        leaf_zones.append((z_obj.name, z_obj))
                    else:
                        for sub_z in z_obj.sub_zones:
                            if not sub_z.sub_zones:
                                leaf_zones.append((sub_z.name, sub_z))
            for zone_name, leaf_zone in leaf_zones:
                sheet_name = re.sub(r"[^A-Za-z0-9_]+", "_", zone_name)[:31]
                # Ensure sheet name unique
                count_suffix = 1
                base = sheet_name
                while sheet_name in created_sheets:
                    sheet_name = f"{base[:28]}_{count_suffix}"
                    count_suffix += 1
                created_sheets.add(sheet_name)
                sp_sheet = workbook.add_worksheet(sheet_name)
                # Write surf spots header
                spot_headers = [
                    "zone", "Surf Spots (count)", "Distance", "Walk", "Easy to find?",
                    "Public access?", "Special access", "Wave quality", "Experience",
                    "Frequency", "Type", "Direction", "Bottom", "Power", "Normal length",
                    "Good day length", "Good swell direction", "Good wind direction",
                    "Good swell direction", "Best tide position", "Best tide movement",
                    "Additional Information", "Latitude", "Longitude",
                ]
                for col, header in enumerate(spot_headers):
                    sp_sheet.write(0, col, header)
                # Write spot rows
                row_sp = 1
                for sp in leaf_zone.surf_spots:
                    sp_sheet.write(row_sp, 0, zone_name)
                    sp_sheet.write(row_sp, 1, sp.name)
                    sp_sheet.write(row_sp, 2, sp.distance)
                    sp_sheet.write(row_sp, 3, sp.walk)
                    sp_sheet.write(row_sp, 4, sp.easy_to_find)
                    sp_sheet.write(row_sp, 5, sp.public_access)
                    sp_sheet.write(row_sp, 6, sp.special_access)
                    sp_sheet.write(row_sp, 7, sp.wave_quality)
                    sp_sheet.write(row_sp, 8, sp.experience)
                    sp_sheet.write(row_sp, 9, sp.frequency)
                    sp_sheet.write(row_sp, 10, sp.type)
                    sp_sheet.write(row_sp, 11, sp.direction)
                    sp_sheet.write(row_sp, 12, sp.bottom)
                    sp_sheet.write(row_sp, 13, sp.power)
                    sp_sheet.write(row_sp, 14, sp.normal_length)
                    sp_sheet.write(row_sp, 15, sp.good_day_length)
                    sp_sheet.write(row_sp, 16, sp.good_swell_direction)
                    sp_sheet.write(row_sp, 17, sp.good_wind_direction)
                    sp_sheet.write(row_sp, 18, sp.swell_size)
                    sp_sheet.write(row_sp, 19, sp.best_tide_position)
                    sp_sheet.write(row_sp, 20, sp.best_tide_movement)
                    sp_sheet.write(row_sp, 21, sp.additional_information)
                    sp_sheet.write(row_sp, 22, sp.latitude)
                    sp_sheet.write(row_sp, 23, sp.longitude)
                    row_sp += 1
        workbook.close()
        print(f"Created workbook for continent {continent}: {workbook_path}")


def main(sample: bool = True) -> None:
    """Example driver that scrapes a subset of Wannasurf and writes output.

    By default this function performs a limited scrape to demonstrate the
    scraper without exhausting resources.  It fetches the list of
    continents and then only processes the first country in each continent.
    For each selected country it processes the first zone (if any) and up
    to five surf spots.

    If ``sample`` is set to False the function will attempt to scrape all
    countries, zones and surf spots.  Be aware that this may take a long
    time and generate significant network traffic.

    The function writes per‑zone CSV files into a ``output_csv``
    directory and compiles a single Excel workbook ``wannasurf_data.xlsx``
    into the current working directory.
    """
    continents_map = parse_homepage()
    continents_data: Dict[str, Dict[str, Zone]] = {}
    csv_output_dir = "output_csv"
    os.makedirs(csv_output_dir, exist_ok=True)

    if DEBUG:
        print(f"[main] Continents found: {list(continents_map.keys())}")

    for continent_name, countries in continents_map.items():
        continents_data[continent_name] = {}
        # Limit to one or two countries per continent when sampling
        country_iter = countries[:1] if sample else countries
        for country_name, country_url in country_iter:
            try:
                print(f"Processing country {country_name} ({country_url})")
                country_zone = parse_country_or_zone_page(country_url, is_country=True)
                continents_data[continent_name][country_name] = country_zone
                # Dump CSVs for zones within this country
                if country_zone.sub_zones:
                    # sample: only process first zone
                    zones_to_process = country_zone.sub_zones[:1] if sample else country_zone.sub_zones
                    for zone_obj in zones_to_process:
                        # sample: limit number of spots
                        if sample and len(zone_obj.surf_spots) > 5:
                            zone_obj.surf_spots = zone_obj.surf_spots[:5]
                        csv_path = zone_obj.to_csv(csv_output_dir)
                        print(f"  Wrote CSV for zone {zone_obj.name}: {csv_path}")
                else:
                    # Country without zones; treat as a zone for CSV
                    # sample: limit number of spots
                    if sample and len(country_zone.surf_spots) > 5:
                        country_zone.surf_spots = country_zone.surf_spots[:5]
                    csv_path = country_zone.to_csv(csv_output_dir)
                    print(f"  Wrote CSV for country {country_name}: {csv_path}")
            except Exception as e:
                print(f"Error processing country {country_name}: {e}")

    # Build detailed Excel workbooks per continent
    output_excel_dir = "excel_output"
    build_excel_workbook(continents_data, output_dir=output_excel_dir)
    print(f"Excel workbooks created in {output_excel_dir}/")


if __name__ == "__main__":
    # When run as a script perform a sampled scrape.  Set sample=False
    # for a full scrape.
    main(sample=True)