"""Юнит-тест парсера на синтетической HTML-фикстуре."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Добавляем родителя пакета в sys.path, чтобы импортировать listing_parser
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from listing_parser import parse_listing  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_listing.html"


@pytest.fixture(scope="module")
def html_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_basic_fields(html_text: str) -> None:
    fields = parse_listing(html_text, listing_id=700123456)

    assert fields.listing_id == 700123456
    assert fields.deal_type == "sale"
    assert fields.category == "prodazha-kvartiry"
    assert fields.url and "700123456" in fields.url

    assert fields.price_kzt == 45000000.0
    assert fields.rooms == 3
    assert fields.city_name == "Алматы"
    assert fields.district_name and "Бостандыкский" in fields.district_name

    assert fields.lat == pytest.approx(43.238949, rel=1e-5)
    assert fields.lon == pytest.approx(76.889709, rel=1e-5)
    assert fields.city_id == 1


def test_parse_attributes(html_text: str) -> None:
    fields = parse_listing(html_text, listing_id=700123456)
    assert fields.building_type == "монолитный"
    assert fields.build_year == 2015
    assert fields.floor == 5
    assert fields.floors_total == 12
    assert fields.area_total_m2 == 75.0
    assert fields.renovation == "евроремонт"
    assert fields.bathroom == "раздельный"
    assert fields.ceiling_height_m == pytest.approx(3.0)
    assert fields.complex_name == "Самал Тауэрс"


def test_parse_description_and_photos(html_text: str) -> None:
    fields = parse_listing(html_text, listing_id=700123456)
    assert fields.description and "уютная" in fields.description
    assert fields.description_hash and len(fields.description_hash) == 32
    assert fields.photos_count == 2
    assert all(u.startswith("https://") for u in fields.photos_urls)


def test_parse_seller_and_status(html_text: str) -> None:
    fields = parse_listing(html_text, listing_id=700123456)
    assert fields.seller_type == "owner"
    assert fields.seller_name and "Айдар" in fields.seller_name
    assert fields.status == "active"
