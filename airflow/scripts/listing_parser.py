"""Парсинг HTML-карточки объявления krisha.kz через selectolax."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from selectolax.parser import HTMLParser

PRICE_RE = re.compile(r"[\d\s ]+")
INT_RE = re.compile(r"-?\d+")
FLOAT_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


@dataclass
class ListingFields:
    listing_id: int
    category: str | None = None
    deal_type: str | None = None
    property_type: str | None = "apartment"
    price_kzt: float | None = None
    currency: str = "KZT"
    rooms: int | None = None
    area_total_m2: float | None = None
    area_living_m2: float | None = None
    area_kitchen_m2: float | None = None
    floor: int | None = None
    floors_total: int | None = None
    building_type: str | None = None
    build_year: int | None = None
    ceiling_height_m: float | None = None
    bathroom: str | None = None
    furniture: str | None = None
    renovation: str | None = None
    balcony: str | None = None
    parking: str | None = None
    city_id: int | None = None
    city_name: str | None = None
    district_name: str | None = None
    address_text: str | None = None
    complex_name: str | None = None
    lat: float | None = None
    lon: float | None = None
    description: str | None = None
    description_hash: bytes | None = None
    photos_count: int | None = None
    photos_urls: list[str] = field(default_factory=list)
    seller_type: str | None = None
    seller_name: str | None = None
    posted_at: datetime | None = None
    status: str | None = "active"
    url: str | None = None


# карта label→ключ ListingFields
_LABEL_MAP = {
    "тип дома": "building_type",
    "год постройки": "build_year",
    "этаж": "_floor_full",
    "площадь": "_area_full",
    "площадь, м²": "_area_full",
    "площадь кухни": "area_kitchen_m2",
    "жилая площадь": "area_living_m2",
    "состояние": "renovation",
    "санузел": "bathroom",
    "балкон": "balcony",
    "балкон остеклен": "_balcony_glazed",
    "парковка": "parking",
    "потолки": "ceiling_height_m",
    "высота потолков": "ceiling_height_m",
    "телефон": "_phone_present",
    "интернет": "_internet",
    "мебель": "furniture",
    "жилой комплекс": "complex_name",
    "год постройки/сдачи": "build_year",
}


def _digits_to_int(text: str | None) -> int | None:
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit() or ch == "-")
    if not digits or digits == "-":
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _digits_to_float(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = text.replace(",", ".").replace(" ", " ")
    m = FLOAT_RE.search(cleaned)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _norm(text: str | None) -> str | None:
    if text is None:
        return None
    return " ".join(text.split()) or None


def _parse_floor_pair(value: str | None) -> tuple[int | None, int | None]:
    if not value:
        return (None, None)
    parts = value.split("из")
    if len(parts) == 1:
        parts = value.split("/")
    if len(parts) >= 2:
        return (_digits_to_int(parts[0]), _digits_to_int(parts[1]))
    return (_digits_to_int(value), None)


def _parse_area_triple(value: str | None) -> tuple[float | None, float | None, float | None]:
    """'120, жилая 80, кухня 15 м²' → (120.0, 80.0, 15.0). Мы парсим простой случай."""
    if not value:
        return (None, None, None)
    total = _digits_to_float(value)
    return (total, None, None)


def _parse_url(html: HTMLParser) -> str | None:
    og = html.css_first('meta[property="og:url"]')
    if og and og.attributes.get("content"):
        return og.attributes["content"]
    canon = html.css_first('link[rel="canonical"]')
    if canon and canon.attributes.get("href"):
        return canon.attributes["href"]
    return None


def _parse_deal_type_from_text(html: HTMLParser) -> tuple[str | None, str | None]:
    """Возвращает (deal_type, category_hint) по <title> и breadcrumbs.

    Krisha рендерит canonical как `/a/show/{id}` без deal-сегмента, поэтому
    deal_type ищем в тексте: 'Продажа' / 'Аренда' / 'Сдам'.
    """
    title_node = html.css_first("title")
    title = (title_node.text(strip=True).lower() if title_node else "")

    deal: str | None = None
    if any(k in title for k in ("продаж", "купить", "продам")):
        deal = "sale"
    elif any(k in title for k in ("арен", "сдам", "сдает", "снять")):
        deal = "rent"

    # backup — ссылки на категорию в breadcrumbs/навигации
    if deal is None:
        for a in html.css('a[href*="/prodazha/"], a[href*="/arenda/"]'):
            href = a.attributes.get("href", "")
            if "/prodazha/" in href:
                deal = "sale"
                break
            if "/arenda/" in href:
                deal = "rent"
                break

    # category hint: подтип недвижимости
    cat: str | None = None
    if "квартир" in title:
        cat = "kvartiry"
    elif "дом" in title:
        cat = "doma"
    elif "коммерч" in title:
        cat = "kommercheskaya-nedvizhimost"

    return deal, cat


def _parse_jsonld(html: HTMLParser) -> dict[str, Any] | None:
    for node in html.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text() or "{}")
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") in {"Product", "Offer", "Apartment"}:
                    return item
        elif isinstance(data, dict):
            if data.get("@type") in {"Product", "Offer", "Apartment"}:
                return data
    return None


def _parse_data_attrs(html: HTMLParser) -> dict[str, str]:
    """Собирает data-* атрибуты с корневых нод объявления (есть city, sec, lat и т.д.)."""
    attrs: dict[str, str] = {}
    for sel in ("[data-id]", "[data-sec]", "[data-lat]", "[data-lon]", "[data-city-id]"):
        node = html.css_first(sel)
        if not node:
            continue
        for k, v in node.attributes.items():
            if k.startswith("data-") and v:
                attrs[k] = v
    return attrs


def _parse_price(html: HTMLParser) -> float | None:
    node = html.css_first(".offer__price") or html.css_first('[itemprop="price"]')
    if not node:
        return None
    text = node.text(strip=True)
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    return float(digits)


def _parse_title(html: HTMLParser) -> tuple[int | None, str | None]:
    """h1 типа '3-комнатная квартира, 75 м² · 5/9 этаж' → (rooms, _)."""
    h1 = html.css_first("h1")
    if not h1:
        return (None, None)
    title = h1.text(strip=True)
    rooms = None
    m = re.match(r"(\d+)\s*-\s*комнат", title.lower())
    if m:
        rooms = int(m.group(1))
    return (rooms, title)


def _parse_address(html: HTMLParser) -> tuple[str | None, str | None]:
    node = html.css_first(".offer__location") or html.css_first('[itemprop="address"]')
    if not node:
        return (None, None)
    text = _norm(node.text())
    if not text:
        return (None, None)
    parts = [p.strip() for p in text.split(",")]
    city = parts[0] if parts else None
    district = parts[1] if len(parts) > 1 else None
    return (city, district)


def _parse_attribute_table(html: HTMLParser) -> dict[str, str]:
    """dl/dd-style блок 'Параметры' → {label_lower: value}."""
    out: dict[str, str] = {}
    for row in html.css(".offer__info-item"):
        label_node = row.css_first(".offer__info-title")
        value_node = row.css_first(".offer__advert-short-info") or row.css_first(".offer__info-value")
        if not label_node or not value_node:
            continue
        label = (label_node.text(strip=True) or "").lower().rstrip(":")
        value = _norm(value_node.text())
        if label and value:
            out[label] = value
    # альтернативная разметка
    for row in html.css("dl > div, dt + dd"):
        pass
    return out


def _parse_description(html: HTMLParser) -> str | None:
    node = html.css_first(".js-description") or html.css_first(".offer__description")
    if node:
        return _norm(node.text())
    og = html.css_first('meta[property="og:description"]')
    if og:
        return _norm(og.attributes.get("content"))
    return None


def _parse_photos(html: HTMLParser) -> list[str]:
    urls: list[str] = []
    for img in html.css(".gallery__small-list img, .gallery__main img, picture img"):
        src = img.attributes.get("src") or img.attributes.get("data-src")
        if src and src.startswith("http"):
            urls.append(src)
    return list(dict.fromkeys(urls))


def _parse_posted_at(html: HTMLParser) -> datetime | None:
    node = html.css_first(".offer__date") or html.css_first('[class*="date"]')
    if not node:
        return None
    text = _norm(node.text())
    if not text:
        return None
    # формат: "обновлено 28 апр 2026" — тут оставим NULL, точная локализация — отдельная задача
    return None


def _seller_type(html: HTMLParser) -> str | None:
    if html.css_first(".owners__label-owner"):
        return "owner"
    if html.css_first(".owners__label-realtor") or html.css_first(".agent"):
        return "agent"
    return None


def _seller_name(html: HTMLParser) -> str | None:
    node = html.css_first(".owners__name") or html.css_first(".agent__name")
    if not node:
        return None
    return _norm(node.text())


def _status(html: HTMLParser) -> str:
    if html.css_first(".offer__status-archive"):
        return "archived"
    if html.css_first(".offer__bage--mortgaged"):
        return "mortgaged"
    return "active"


def parse_listing(html_text: str, listing_id: int) -> ListingFields:
    """Извлекает поля из HTML карточки. Не падает на отсутствующих полях — кладёт None."""
    html = HTMLParser(html_text)
    fields = ListingFields(listing_id=listing_id)

    # url + canonical
    fields.url = _parse_url(html)

    # категория из URL
    if fields.url:
        m = re.search(
            r"/(prodazha|arenda)/(kvartiry|doma|dachi|"
            r"kommercheskaya-nedvizhimost|zemelnye-uchastki)",
            fields.url,
        )
        if m:
            fields.deal_type = "sale" if m.group(1) == "prodazha" else "rent"
            fields.category = f"{m.group(1)}-{m.group(2)}"

    # fallback: deal_type и подкатегория из title/breadcrumbs (canonical
    # часто отдаётся как /a/show/{id} без deal-сегмента)
    if fields.deal_type is None:
        deal_text, cat_hint = _parse_deal_type_from_text(html)
        if deal_text:
            fields.deal_type = deal_text
            if fields.category is None and cat_hint:
                prefix = "prodazha" if deal_text == "sale" else "arenda"
                fields.category = f"{prefix}-{cat_hint}"

    # data-attrs (city, lat, lon, sec)
    data = _parse_data_attrs(html)
    if "data-city-id" in data:
        fields.city_id = _digits_to_int(data["data-city-id"])
    if "data-lat" in data:
        fields.lat = _digits_to_float(data["data-lat"])
    if "data-lon" in data:
        fields.lon = _digits_to_float(data["data-lon"])

    # цена
    fields.price_kzt = _parse_price(html)

    # rooms из title
    rooms, _ = _parse_title(html)
    fields.rooms = rooms

    # адрес
    city, district = _parse_address(html)
    fields.city_name = city
    fields.district_name = district
    fields.address_text = ", ".join(p for p in (city, district) if p) or None

    # параметры
    attrs = _parse_attribute_table(html)
    for label, value in attrs.items():
        key = _LABEL_MAP.get(label)
        if not key:
            continue
        if key == "_floor_full":
            f, ft = _parse_floor_pair(value)
            fields.floor = f
            fields.floors_total = ft
        elif key == "_area_full":
            total, living, kitchen = _parse_area_triple(value)
            fields.area_total_m2 = total
        elif key == "build_year":
            fields.build_year = _digits_to_int(value)
        elif key == "ceiling_height_m":
            fields.ceiling_height_m = _digits_to_float(value)
        elif key == "area_kitchen_m2":
            fields.area_kitchen_m2 = _digits_to_float(value)
        elif key == "area_living_m2":
            fields.area_living_m2 = _digits_to_float(value)
        elif key.startswith("_"):
            continue
        else:
            setattr(fields, key, value)

    # JSON-LD как backstop
    jsonld = _parse_jsonld(html)
    if jsonld:
        if fields.price_kzt is None:
            offer = jsonld.get("offers") if isinstance(jsonld, dict) else None
            if isinstance(offer, dict) and offer.get("price"):
                fields.price_kzt = _digits_to_float(str(offer["price"]))

    # описание + хеш
    fields.description = _parse_description(html)
    if fields.description:
        fields.description_hash = hashlib.sha256(fields.description.encode("utf-8")).digest()

    # фото
    fields.photos_urls = _parse_photos(html)
    fields.photos_count = len(fields.photos_urls)

    # продавец
    fields.seller_type = _seller_type(html)
    fields.seller_name = _seller_name(html)

    # статус и дата
    fields.status = _status(html)
    fields.posted_at = _parse_posted_at(html)

    return fields


def html_sha256(html_text: str) -> bytes:
    return hashlib.sha256(html_text.encode("utf-8")).digest()
