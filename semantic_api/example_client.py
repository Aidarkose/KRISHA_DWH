"""Пример клиента к семантическому API KRISHA_DWH.

Запуск (вне контейнера, requests должен быть установлен):
    python semantic_api/example_client.py
"""
from __future__ import annotations

import json
from urllib import request

BASE = "http://localhost:8090"


def post_json(path: str, payload: dict) -> dict:
    req = request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())


def get(path: str) -> dict:
    with request.urlopen(f"{BASE}{path}", timeout=30) as resp:
        return json.loads(resp.read())


def main() -> None:
    print("== /health ==")
    print(get("/health"))

    print("\n== /metrics ==")
    print(get("/metrics")["output"])

    # 1. Топ-10 городов по средней цене за м² (продажа активных объявлений)
    print("\n== Топ-10 городов по avg_price_per_m2 (sale, active) ==")
    out = post_json(
        "/query",
        {
            "metrics": ["avg_price_per_m2", "listings_count"],
            "group_by": ["listing__city_name"],
            "where": [
                "{{ Dimension('listing__deal_type') }} = 'sale'",
            ],
            "order_by": ["-listings_count"],
            "limit": 10,
        },
    )
    print(f"rows = {out['row_count']}")
    for r in out["rows"]:
        print(r)

    # 2. Динамика медианной цены аренды по месяцам
    print("\n== median_price по месяцам, deal_type = rent_long ==")
    out = post_json(
        "/query",
        {
            "metrics": ["median_price"],
            "group_by": ["metric_time__month"],
            "where": [
                "{{ Dimension('listing__deal_type') }} = 'rent_long'",
            ],
            "order_by": ["metric_time__month"],
        },
    )
    for r in out["rows"]:
        print(r)

    # 3. Чистая ценовая активность по городам (derived metric)
    print("\n== net_price_movements по городам ==")
    out = post_json(
        "/query",
        {
            "metrics": ["net_price_movements"],
            "group_by": ["listing__city_name"],
            "order_by": ["-net_price_movements"],
            "limit": 10,
            "explain": True,
        },
    )
    for r in out["rows"]:
        print(r)
    if out.get("sql"):
        print("\n-- сгенерированный SQL (хвост) --")
        print(out["sql"][-800:])


if __name__ == "__main__":
    main()
