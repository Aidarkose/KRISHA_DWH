"""Парсинг sitemap-индекса krisha.kz и индивидуальных sitemap-файлов."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

from lxml import etree

from fetcher import BASE_URL, fetch_text_sync

SITEMAP_INDEX_URL = f"{BASE_URL}/sitemap.xml"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# /a/show/700123456 или /<deal>/<type>/show/700123456
SHOW_URL_RE = re.compile(r"/a/show/(?P<id>\d+)")
LISTING_URL_RE = re.compile(
    r"/(?P<deal>prodazha|arenda)/(?P<ptype>kvartiry|doma|dachi|"
    r"kommercheskaya-nedvizhimost|zemelnye-uchastki)[^/]*/show/(?P<id>\d+)"
)


@dataclass
class DiscoveredId:
    listing_id: int
    category: str
    sitemap_url: str


def fetch_sitemap_index() -> list[str]:
    """Возвращает список URL вложенных sitemap-файлов с advert*.xml."""
    xml = fetch_text_sync(SITEMAP_INDEX_URL)
    root = etree.fromstring(xml.encode("utf-8"))
    urls: list[str] = []
    for loc in root.findall("sm:sitemap/sm:loc", NS):
        url = (loc.text or "").strip()
        if not url:
            continue
        if "/advert" in url:
            urls.append(url)
    return urls


def iter_listings_in_sitemap(
    sitemap_url: str,
    categories: tuple[str, ...] = ("prodazha-kvartiry", "arenda-kvartiry"),
) -> Iterator[DiscoveredId]:
    """Парсит один advert*.xml и yield-ит DiscoveredId для нужных категорий."""
    xml = fetch_text_sync(sitemap_url)
    root = etree.fromstring(xml.encode("utf-8"))
    for url_el in root.findall("sm:url/sm:loc", NS):
        loc = (url_el.text or "").strip()
        if not loc:
            continue
        m = LISTING_URL_RE.search(loc)
        if not m:
            # fallback: некоторые ссылки идут как /a/show/<id>
            m2 = SHOW_URL_RE.search(loc)
            if not m2:
                continue
            yield DiscoveredId(int(m2.group("id")), "unknown", sitemap_url)
            continue
        deal = m.group("deal")
        ptype = m.group("ptype")
        category = f"{deal}-{ptype}"
        if categories and category not in categories:
            continue
        yield DiscoveredId(int(m.group("id")), category, sitemap_url)
