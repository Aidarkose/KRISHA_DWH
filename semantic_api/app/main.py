"""FastAPI-обёртка над MetricFlow CLI (KRISHA_DWH semantic layer)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .mf_runner import (
    MFError,
    list_dimensions,
    list_metrics,
    parse,
    query,
)

log = logging.getLogger("semantic_api")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        log.info("dbt parse on startup…")
        parse()
        log.info("dbt parse OK")
    except MFError as e:
        log.warning("dbt parse failed on startup: %s", e.stderr or e)
    yield


app = FastAPI(
    title="KRISHA_DWH Semantic Layer API",
    description=(
        "Семантический слой над marts.dim_listing + marts.fact_listing_price_history "
        "на dbt + MetricFlow. /query принимает список метрик/измерений и возвращает "
        "результат в JSON."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


class QueryRequest(BaseModel):
    metrics: list[str] = Field(
        ...,
        description="Список имён метрик из metrics.yml (listings_count, avg_price_per_m2 и т.д.)",
        examples=[["avg_price_per_m2", "listings_count"]],
    )
    group_by: Optional[list[str]] = Field(
        default=None,
        description="Измерения вида entity__dimension, например listing__city_name, metric_time__month",
        examples=[["listing__city_name"]],
    )
    where: Optional[list[str]] = Field(
        default=None,
        description=(
            "Список SQL-фильтров в jinja-нотации MetricFlow. "
            "Пример: \"{{ Dimension('listing__deal_type') }} = 'sale'\""
        ),
    )
    order_by: Optional[list[str]] = Field(
        default=None,
        description="Имена метрик/измерений; префикс - = DESC. Пример: ['-listings_count']",
    )
    limit: Optional[int] = Field(default=None, ge=1, le=10_000)
    explain: bool = Field(
        default=False,
        description="Если true — также вернуть сгенерированный SQL.",
    )


class QueryResponse(BaseModel):
    rows: list[dict]
    row_count: int
    sql: Optional[str] = None


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.post("/parse", tags=["meta"], summary="Перечитать manifest dbt (после изменения yml)")
def reparse() -> dict:
    try:
        parse()
    except MFError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e))
    return {"status": "parsed"}


@app.get("/metrics", tags=["catalog"], summary="Список доступных метрик")
def metrics() -> dict:
    try:
        return {"output": list_metrics()}
    except MFError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e))


@app.get(
    "/dimensions",
    tags=["catalog"],
    summary="Список измерений, доступных для набора метрик",
)
def dimensions(metrics: str) -> dict:
    metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
    if not metric_list:
        raise HTTPException(status_code=400, detail="parameter `metrics` is required")
    try:
        return {"output": list_dimensions(metric_list)}
    except MFError as e:
        raise HTTPException(status_code=500, detail=e.stderr or str(e))


@app.post(
    "/query",
    response_model=QueryResponse,
    tags=["query"],
    summary="Выполнить запрос к семантическому слою",
)
def post_query(req: QueryRequest) -> QueryResponse:
    try:
        result = query(
            metrics=req.metrics,
            group_by=req.group_by,
            where=req.where,
            order_by=req.order_by,
            limit=req.limit,
            explain=req.explain,
        )
    except MFError as e:
        raise HTTPException(status_code=400, detail=e.stderr or str(e))
    return QueryResponse(rows=result.rows, row_count=len(result.rows), sql=result.sql)
