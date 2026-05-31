"""Crawlers for museum collections — each yields items with the standard 15 fields.

Standard fields (from request.md):
  object_id, title, period, type, material, description, dimensions,
  museum, location, detail_url, image_url, image_path, credit_line,
  accession_number, crawl_date

Extra fields beyond the 15 are prefixed with '_' to distinguish them.
"""

import json
import re
import time
import hashlib
from datetime import date
from typing import Iterable, Dict, Any
from bs4 import BeautifulSoup
import requests

from .base_crawler import BaseCrawler

MET_API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"
CHICAGO_API_BASE = "https://api.artic.edu/api/v1"
TODAY = date.today().isoformat()  # 2026-05-27


def _base(museum: str, location: str) -> dict:
    """Return a dict pre-filled with the 15 standard fields (empty strings)."""
    return {
        "object_id": "",
        "title": "",
        "period": "",
        "type": "",
        "material": "",
        "description": "",
        "dimensions": "",
        "museum": museum,
        "location": location,
        "detail_url": "",
        "image_url": "",
        "image_path": "",
        "credit_line": "",
        "accession_number": "",
        "crawl_date": TODAY,
    }


# ═══════════════════════════════════════════════════════════════════════
# 1. Met Museum  —  open REST API (no key)
# ═══════════════════════════════════════════════════════════════════════

class MetMuseumCrawler(BaseCrawler):
    """大都会博物馆 — 官方开放 REST API，搜索中国相关藏品"""

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)
        self._session = requests.Session()

    def _search(self, query: str = "China", has_images: bool = True) -> list[int]:
        params = {"q": query}
        if has_images:
            params["hasImages"] = "true"
        resp = self._session.get(f"{MET_API_BASE}/search", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json().get("objectIDs", []) or []

    def _get_object(self, oid: int) -> dict:
        resp = self._session.get(f"{MET_API_BASE}/objects/{oid}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def crawl(self) -> Iterable[Dict[str, Any]]:
        all_ids = self._search("China", has_images=True)
        for oid in all_ids[:50]:
            try:
                obj = self._get_object(oid)
            except Exception:
                continue
            if not obj or not obj.get("title"):
                continue
            item = _base("The Metropolitan Museum of Art", "New York, United States")
            item.update({
                "object_id": str(oid),
                "title": obj.get("title", ""),
                "period": obj.get("period", ""),
                "type": obj.get("objectName", ""),
                "material": obj.get("medium", ""),
                "description": "",
                "dimensions": obj.get("dimensions", ""),
                "detail_url": obj.get("objectURL", ""),
                "image_url": obj.get("primaryImage", ""),
                "credit_line": obj.get("creditLine", ""),
                "accession_number": obj.get("accessionNumber", ""),
                # Extra fields (beyond 15) — prefixed with _
                "_culture": obj.get("culture", ""),
                "_dynasty": obj.get("dynasty", ""),
                "_reign": obj.get("reign", ""),
                "_object_date": obj.get("objectDate", ""),
                "_department": obj.get("department", ""),
                "_country": obj.get("country", ""),
                "_region": obj.get("region", ""),
                "_artist": obj.get("artistDisplayName", ""),
                "_artist_bio": obj.get("artistDisplayBio", ""),
                "_artist_nationality": obj.get("artistNationality", ""),
                "_image_small": obj.get("primaryImageSmall", ""),
                "_accession_year": obj.get("accessionYear", ""),
                "_is_public_domain": obj.get("isPublicDomain", ""),
            })
            yield item


# ═══════════════════════════════════════════════════════════════════════
# 2. Guimet Museum  —  Drupal HTML scraping
# ═══════════════════════════════════════════════════════════════════════

class GuimetMuseumCrawler(BaseCrawler):
    """吉美博物馆 — 爬取 Drupal 静态页面"""

    BASE = "https://www.guimet.fr"

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)
        self.start_url = start_url

    def _abs(self, url: str) -> str:
        if not url:
            return ""
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            return f"{self.BASE}{url}"
        return url

    def _parse_detail(self, url: str) -> dict:
        info = {"period": "", "material": "", "description": "",
                "dimensions": "", "credit_line": "", "accession_number": "",
                "image_url": "", "type": ""}
        try:
            html = self.fetch(url)
        except Exception:
            return info
        soup = BeautifulSoup(html, "html.parser")

        for sel in (".field--name-field-teaser",):
            el = soup.select_one(sel)
            if el:
                info["description"] = el.get_text(strip=True)

        period = soup.select_one(".field--name-field-text-period")
        if period:
            info["period"] = period.get_text(strip=True)

        info_table = soup.select_one(".info-table")
        if info_table:
            for cell in info_table.find_all("div", class_="cell"):
                label = cell.select_one(".field__label")
                val = cell.select_one(".field__item")
                if label and val:
                    key = (
                        label.get_text(strip=True)
                        .lower().replace(" ", "_").replace("é", "e")
                    )
                    v = val.get_text(strip=True)
                    if "period" in key or "date" in key:
                        info["period"] = v
                    elif "material" in key or "medium" in key:
                        info["material"] = v
                    elif "dimension" in key:
                        info["dimensions"] = v
                    elif "type" in key:
                        info["type"] = v
                    elif "credit" in key or "acquisition" in key:
                        info["credit_line"] = v
                    elif "inventaire" in key or "number" in key:
                        info["accession_number"] = v

        full = soup.select_one(
            ".field--name-field-image img, div.field--type-image img"
        )
        if full:
            info["image_url"] = self._abs(full.get("src", ""))

        return info

    def crawl(self) -> Iterable[Dict[str, Any]]:
        html = self.fetch(f"{self.BASE}/en/collections/china")
        soup = BeautifulSoup(html, "html.parser")

        for card in soup.select(".node--type-art-work"):
            title_el = card.select_one(".field--name-title, h2, h3")
            title = title_el.get_text(strip=True) if title_el else ""

            cat_el = card.select_one(".field--name-field-object-type")
            category = cat_el.get_text(strip=True) if cat_el else ""

            link_el = card.select_one("a[href*='/our-collections/']")
            detail_url = self._abs(link_el["href"]) if link_el else None

            thumb_el = card.select_one("img")
            thumb = self._abs(thumb_el.get("src", "")) if thumb_el else ""

            item = _base("Musée Guimet", "Paris, France")
            item["title"] = title
            item["type"] = category
            item["detail_url"] = detail_url or ""
            item["image_url"] = thumb
            item["_category"] = category

            if detail_url:
                detail = self._parse_detail(detail_url)
                if detail.get("image_url"):
                    item["image_url"] = detail["image_url"]
                # Update standard fields from detail
                for f in ("period", "material", "description", "dimensions",
                          "credit_line", "accession_number", "type"):
                    if detail.get(f):
                        item[f] = detail[f]

            if item["title"]:
                yield item


# ═══════════════════════════════════════════════════════════════════════
# 3. Brooklyn Botanic Garden  —  HTML scraping (legacy, non-artifact)
# ═══════════════════════════════════════════════════════════════════════

class BrooklynBotanicCrawler(BaseCrawler):
    """布鲁克林植物园 — 爬取植物名录 (non-artifact, legacy module)"""

    BASE = "https://www.bbg.org"

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)

    def _abs(self, url: str) -> str:
        return f"{self.BASE}{url}" if url.startswith("/") else url

    def crawl(self) -> Iterable[Dict[str, Any]]:
        pages = [
            "/collections/cherry_stages",
            "/bloom",
            "/collections/cherries",
        ]
        for path in pages:
            url = self._abs(path)
            try:
                html = self.fetch(url)
            except Exception:
                continue
            soup = BeautifulSoup(html, "html.parser")
            title_el = soup.select_one("h1")
            collection = title_el.get_text(strip=True) if title_el else path.strip("/")

            seen = set()
            for img in soup.find_all("img"):
                src = img.get("src") or ""
                alt = img.get("alt", "").strip()
                if not src or "/logo" in src or "svg" in src:
                    continue
                abs_src = self._abs(src)
                if abs_src in seen:
                    continue
                seen.add(abs_src)
                if len(alt) > 3:
                    item = _base("Brooklyn Botanic Garden", "Brooklyn, New York, United States")
                    plant = alt.split(",")[0].strip() if "," in alt else alt
                    item.update({
                        "object_id": hashlib.md5(abs_src.encode()).hexdigest()[:12],
                        "title": alt,
                        "type": "plant",
                        "description": collection,
                        "detail_url": url,
                        "image_url": abs_src,
                        "_plant_name": plant,
                        "_collection": collection,
                    })
                    yield item


# ═══════════════════════════════════════════════════════════════════════
# 4. British Museum  —  Playwright-browser to bypass Cloudflare
# ═══════════════════════════════════════════════════════════════════════

class BritishMuseumCrawler(BaseCrawler):
    """大英博物馆 — 通过 Playwright 浏览器绕过 Cloudflare，拦截内部 ES API"""

    BASE = "https://www.britishmuseum.org"
    MEDIA_BASE = "https://media.britishmuseum.org"

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)

    @staticmethod
    def _clean_html(raw: str) -> str:
        return re.sub(r"<[^>]+>", "", raw).strip()

    def crawl(self) -> Iterable[Dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("pip install playwright && playwright install chromium")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="en-GB",
            )
            page = ctx.new_page()
            api_data = {}

            def capture(response):
                if "_search" in response.url and response.status == 200:
                    try:
                        api_data["body"] = response.json()
                    except Exception:
                        pass

            page.on("response", capture)
            page.goto(
                f"{self.BASE}/collection/search?place=China&page=0",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            page.wait_for_timeout(8000)

            if "body" not in api_data:
                browser.close()
                raise RuntimeError("British Museum API blocked by Cloudflare")

            hits = api_data["body"].get("hits", {}).get("hits", [])

            for hit in hits:
                src = hit.get("_source", {})
                brief_str = src.get("@template", {}).get("brief", "{}")
                try:
                    brief = json.loads(brief_str)
                except (json.JSONDecodeError, TypeError):
                    brief = {}

                # object type
                obj_types = brief.get("Object Type") or brief.get("object_type") or []
                object_type = ""
                if isinstance(obj_types, list):
                    for t in obj_types:
                        if isinstance(t, dict):
                            val = BritishMuseumCrawler._clean_html(t.get("value", ""))
                            if val:
                                object_type = val
                elif isinstance(obj_types, str):
                    object_type = BritishMuseumCrawler._clean_html(obj_types)

                # title / name
                names = src.get("name", [])
                titles = []
                for n in names:
                    if isinstance(n, dict) and n.get("type") == "object name":
                        v = n.get("value", "")
                        if v:
                            titles.append(v)
                object_name = " / ".join(titles) if titles else object_type

                # production date
                prod_date = ""
                pd = brief.get("Production date") or brief.get("production_date") or ""
                if isinstance(pd, list):
                    vals = []
                    for v in pd:
                        if isinstance(v, dict):
                            vals.append(BritishMuseumCrawler._clean_html(v.get("value", "")))
                    prod_date = "; ".join(vals)
                else:
                    prod_date = BritishMuseumCrawler._clean_html(str(pd))

                # findspot / place
                findspot_raw = brief.get("Findspot") or brief.get("findspot") or {}
                findspot = ""
                if isinstance(findspot_raw, dict):
                    findspot = BritishMuseumCrawler._clean_html(findspot_raw.get("value", ""))

                # culture / period
                culture_raw = brief.get("Culture/period") or brief.get("culture") or ""
                culture = ""
                if isinstance(culture_raw, list):
                    vals = [BritishMuseumCrawler._clean_html(c.get("value", "")) for c in culture_raw if isinstance(c, dict)]
                    culture = "; ".join(vals)
                else:
                    culture = BritishMuseumCrawler._clean_html(str(culture_raw))

                # material
                material_raw = brief.get("Material") or brief.get("material") or ""
                material = ""
                if isinstance(material_raw, list):
                    vals = [BritishMuseumCrawler._clean_html(m.get("value", "")) for m in material_raw if isinstance(m, dict)]
                    material = "; ".join(vals)
                else:
                    material = BritishMuseumCrawler._clean_html(str(material_raw))

                # museum number
                museum_no = BritishMuseumCrawler._clean_html(
                    str(brief.get("Museum number") or brief.get("museum_number") or "")
                )

                # image
                img_url = ""
                if src.get("multimedia"):
                    loc = (
                        src["multimedia"][0]
                        .get("@processed", {})
                        .get("large", {})
                        .get("location", "")
                    )
                    if loc:
                        img_url = f"{self.MEDIA_BASE}/{loc}"

                identifiers = src.get("identifier", [])
                uid = ""
                reg_num = ""
                for id_item in identifiers:
                    if isinstance(id_item, dict):
                        if id_item.get("type") == "unique object id":
                            uid = id_item.get("value", "")
                        if id_item.get("type") == "registration number":
                            reg_num = id_item.get("value", "")
                object_url = f"{self.BASE}/collection/object/{uid}" if uid else ""

                item = _base("The British Museum", "London, United Kingdom")
                item.update({
                    "object_id": museum_no or reg_num or uid,
                    "title": object_name,
                    "period": prod_date,
                    "type": object_type,
                    "material": material,
                    "description": culture,
                    "dimensions": "",
                    "detail_url": object_url,
                    "image_url": img_url,
                    "credit_line": findspot,
                    "accession_number": museum_no or reg_num,
                    # Extra fields
                    "_culture": culture,
                    "_findspot": findspot,
                    "_object_name_detail": object_name,
                })
                yield item

            browser.close()


# ═══════════════════════════════════════════════════════════════════════
# 5. Art Institute of Chicago  —  open REST API (no key)
# ═══════════════════════════════════════════════════════════════════════

class ArtInstituteChicagoCrawler(BaseCrawler):
    """芝加哥艺术博物馆 — 开放 REST API，支持分页"""

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)
        self._session = requests.Session()

    CHICAGO_FIELDS = (
        "id,title,image_id,date_display,medium_display,artist_display,"
        "place_of_origin,dimensions,credit_line,accession_number,"
        "classification_display,style_title,technique_title,department_title"
    )

    def _fetch_page(self, query: str = "china", page: int = 1, limit: int = 100) -> dict:
        url = f"{CHICAGO_API_BASE}/artworks/search"
        params = {"q": query, "page": page, "limit": limit, "fields": self.CHICAGO_FIELDS}
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def crawl(self) -> Iterable[Dict[str, Any]]:
        page = 1
        max_pages = 50  # up to 5000 items
        while page <= max_pages:
            try:
                data = self._fetch_page("china", page)
            except requests.RequestException:
                print(f"  Chicago page {page} failed, retrying with delay...")
                time.sleep(3)
                try:
                    data = self._fetch_page("china", page)
                except requests.RequestException:
                    print(f"  Chicago page {page} still failing, stopping pagination")
                    break

            pagination = data.get("pagination", {})
            total_pages = pagination.get("total_pages", 1)

            for artwork in data.get("data", []):
                image_id = artwork.get("image_id", "")
                image_url = (
                    f"https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg"
                    if image_id else ""
                )

                item = _base("Art Institute of Chicago", "Chicago, United States")
                item.update({
                    "object_id": str(artwork.get("id", "")),
                    "title": artwork.get("title", ""),
                    "period": artwork.get("date_display", ""),
                    "type": artwork.get("classification_display", ""),
                    "material": artwork.get("medium_display", ""),
                    "description": artwork.get("description", ""),
                    "dimensions": artwork.get("dimensions", ""),
                    "detail_url": f"https://www.artic.edu/artworks/{artwork.get('id', '')}",
                    "image_url": image_url,
                    "credit_line": artwork.get("credit_line", ""),
                    "accession_number": artwork.get("accession_number", ""),
                    # Extra fields
                    "_artist": artwork.get("artist_display", ""),
                    "_place_of_origin": artwork.get("place_of_origin", ""),
                    "_style": artwork.get("style_title", ""),
                    "_department": artwork.get("department_title", ""),
                    "_technique": artwork.get("technique_title", ""),
                    "_image_id": image_id,
                    "_classification": artwork.get("classification_title", ""),
                })
                if item["object_id"]:
                    yield item

            page += 1
            if page > total_pages:
                break
            time.sleep(2.5)  # rate-limit protection


# ═══════════════════════════════════════════════════════════════════════
# 6. Princeton University Art Museum  —  Playwright + internal API
# ═══════════════════════════════════════════════════════════════════════

class PrincetonMuseumCrawler(BaseCrawler):
    """普林斯顿大学艺术博物馆 — Playwright 拦截内部搜索 API"""

    BASE = "https://artmuseum.princeton.edu"
    API_BASE = "https://data.artmuseum.princeton.edu/collection/msearch"

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)

    def _parse_source(self, src: dict) -> dict:
        item = _base("Princeton University Art Museum", "Princeton, United States")
        oid = str(src.get("objectid", ""))
        img_list = src.get("primaryimage") or []
        img_url = img_list[0] if isinstance(img_list, list) and img_list else ""

        item.update({
            "object_id": oid or hashlib.md5(str(src.get("objectnumber", "")).encode()).hexdigest()[:12],
            "title": src.get("displaytitle", ""),
            "period": src.get("displayperiod") or src.get("displaydate", ""),
            "type": "",
            "material": src.get("medium", ""),
            "description": src.get("displayculture", ""),
            "dimensions": "",
            "detail_url": f"{self.BASE}/art/collections/{oid}" if oid else "",
            "image_url": img_url,
            "credit_line": "",
            "accession_number": src.get("objectnumber", ""),
            # Extra fields
            "_displayculture": src.get("displayculture", ""),
            "_displaydate": src.get("displaydate", ""),
            "_displayperiod": src.get("displayperiod", ""),
            "_objectnumber": src.get("objectnumber", ""),
            "_medium_detail": src.get("medium", ""),
        })
        return item

    def crawl(self) -> Iterable[Dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("pip install playwright && playwright install chromium")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            page = ctx.new_page()
            first_data = {}

            def capture(response):
                try:
                    if "data.artmuseum.princeton.edu/collection/msearch" in response.url and response.status == 200:
                        if not first_data:
                            first_data["body"] = response.json()
                except Exception:
                    pass

            page.on("response", capture)

            # Navigate to search page
            page.goto(
                f"{self.BASE}/search/collections?search=china",
                wait_until="commit",
                timeout=30000,
            )
            # Wait for React app to load and call API
            for _ in range(15):
                page.wait_for_timeout(2000)
                if first_data:
                    break

            if not first_data:
                browser.close()
                raise RuntimeError("Princeton Museum API not intercepted")

            body = first_data["body"]
            results = body.get("results", {})
            total = results.get("total", {})
            total_val = total.get("value", 0) if isinstance(total, dict) else 0
            hits = results.get("hits", [])
            page_size = len(hits) or 24
            max_items = min(total_val, 3600)  # cap at 3600 items

            # Yield first page
            for hit in hits:
                yield self._parse_source(hit.get("_source", hit))

            # Pagination via XMLHttpRequest (withCredentials works in browser context)
            max_pages = min(max_items // page_size + 1, 150)  # up to 150 pages (3600 items)
            for p in range(1, max_pages):
                from_offset = p * page_size
                try:
                    result = page.evaluate(
                        """(url) => new Promise((resolve, reject) => {
                            var xhr = new XMLHttpRequest();
                            xhr.open('GET', url, true);
                            xhr.withCredentials = true;
                            xhr.onload = () => resolve(JSON.parse(xhr.responseText));
                            xhr.onerror = () => reject('XHR failed');
                            xhr.send();
                        })""",
                        f"{self.API_BASE}?&sort=relevance&from={from_offset}",
                    )
                    page_hits = result.get("results", {}).get("hits", [])
                    for hit in page_hits:
                        yield self._parse_source(hit.get("_source", hit))
                    if len(page_hits) < page_size:
                        break
                except Exception as e:
                    print(f"  Princeton page {p} error: {e}")
                    continue

            browser.close()


# ═══════════════════════════════════════════════════════════════════════
# 7. Brooklyn Museum  —  Playwright + internal search API interception
# ═══════════════════════════════════════════════════════════════════════

class BrooklynArtMuseumCrawler(BaseCrawler):
    """布鲁克林艺术博物馆 — 通过 Playwright 拦截内部搜索 API (Sanity CMS)"""

    BASE = "https://www.brooklynmuseum.org"
    API_BASE = "https://search.brooklynmuseum.org/api/search"

    def __init__(self, start_url: str, **kw):
        super().__init__(**kw)

    def _parse_item(self, raw: dict) -> dict:
        item = _base("Brooklyn Museum", "Brooklyn, New York, United States")

        img_url = raw.get("imageUrl", "")
        if not img_url:
            for f in ("image", "image_url", "thumbnail"):
                v = raw.get(f, "")
                if v:
                    img_url = v
                    break

        oid = str(raw.get("sourceId", raw.get("sourceid", raw.get("id", ""))))
        item.update({
            "object_id": oid,
            "title": raw.get("title") or raw.get("objectName") or "",
            "period": raw.get("dates") or raw.get("period") or raw.get("date") or "",
            "type": raw.get("classification") or raw.get("objectName") or raw.get("type") or "",
            "material": raw.get("medium") or raw.get("material") or "",
            "description": raw.get("description") or raw.get("label") or "",
            "dimensions": raw.get("dimensions") or raw.get("measurements") or "",
            "detail_url": raw.get("url") or f"{self.BASE}/opencollection/objects/{oid}" if oid else "",
            "image_url": img_url,
            "credit_line": raw.get("creditLine") or raw.get("credit_line") or "",
            "accession_number": raw.get("accessionNumber") or raw.get("accession_number") or "",
        })

        # Collect all extra fields from raw API response
        known = set(item.keys())
        for k, v in raw.items():
            if k not in known and not k.startswith("_"):
                if v is not None and not isinstance(v, (dict, list)):
                    item[f"_{k}"] = str(v)
        return item

    def crawl(self) -> Iterable[Dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("pip install playwright && playwright install chromium")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            page = ctx.new_page()

            # Step 1: navigate to search page to establish session + get first page
            first_body = {}
            def capture(response):
                if "search.brooklynmuseum.org" in response.url and response.status == 200:
                    try:
                        if not first_body:
                            first_body["data"] = response.json()
                    except Exception:
                        pass

            page.on("response", capture)
            page.goto(
                f"{self.BASE}/opencollection/search?q=china",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            page.wait_for_timeout(8000)

            if not first_body:
                browser.close()
                raise RuntimeError("Brooklyn Museum API not intercepted")

            body = first_body["data"]
            metadata = body.get("metadata", {})
            max_pages = metadata.get("maxPages", metadata.get("pages", 1))
            total = metadata.get("total", 0)

            def yield_page(page_body: dict):
                for raw in page_body.get("data", []):
                    yield self._parse_item(raw)

            yield from yield_page(body)

            # Step 2: paginate via Playwright APIRequestContext (shares browser session)
            max_pages = min(max_pages + 1, 31)  # cap at 30 pages (~720 items)
            api_context = page.request
            for p in range(2, max_pages):
                try:
                    api_url = (
                        f"{self.API_BASE}?type=collectionObject"
                        f"&sortField=_score&sortOrder=desc&page={p}"
                    )
                    resp = api_context.get(api_url)
                    if resp.status != 200:
                        break
                    page_data = resp.json()
                    if not page_data.get("data"):
                        break
                    yield from yield_page(page_data)
                except Exception as e:
                    print(f"  Brooklyn Museum page {p} error: {e}")
                    continue

            browser.close()
