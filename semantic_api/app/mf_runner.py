"""Тонкий wrapper вокруг MetricFlow CLI (`mf`).

MetricFlow в open-source-варианте не отдаёт Python API стабильно — поэтому
самый надёжный путь это subprocess к `mf` CLI с CSV-выгрузкой и парсингом.
"""
from __future__ import annotations

import csv
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

DBT_PROJECT_DIR = os.environ.get("DBT_PROJECT_DIR", "/dbt")
DBT_PROFILES_DIR = os.environ.get("DBT_PROFILES_DIR", "/dbt")
MF_TIMEOUT_SEC = int(os.environ.get("MF_TIMEOUT_SEC", "180"))


class MFError(RuntimeError):
    def __init__(self, message: str, stderr: str = "", returncode: int = -1):
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode


@dataclass
class MFResult:
    rows: list[dict]
    sql: Optional[str] = None
    raw_stdout: str = ""


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["DBT_PROJECT_DIR"] = DBT_PROJECT_DIR
    env["DBT_PROFILES_DIR"] = DBT_PROFILES_DIR
    return env


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=DBT_PROJECT_DIR,
        env=_env(),
        capture_output=True,
        text=True,
        timeout=MF_TIMEOUT_SEC,
    )
    if proc.returncode != 0:
        raise MFError(
            f"command failed: {' '.join(cmd)}",
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
    return proc


def parse() -> str:
    """Прогрев dbt parse — иначе `mf` ругается на отсутствующий manifest."""
    proc = _run(["dbt", "parse", "--quiet"])
    return proc.stdout


def list_metrics() -> str:
    return _run(["mf", "list", "metrics", "--show-all-dimensions"]).stdout


def list_dimensions(metrics: Iterable[str]) -> str:
    return _run(
        ["mf", "list", "dimensions", "--metrics", ",".join(metrics)]
    ).stdout


def query(
    metrics: list[str],
    group_by: Optional[list[str]] = None,
    where: Optional[list[str]] = None,
    order_by: Optional[list[str]] = None,
    limit: Optional[int] = None,
    explain: bool = False,
) -> MFResult:
    if not metrics:
        raise ValueError("metrics не должен быть пустым")

    with tempfile.TemporaryDirectory(prefix="mf_") as tmp:
        csv_path = Path(tmp) / "out.csv"
        cmd: list[str] = [
            "mf",
            "query",
            "--metrics",
            ",".join(metrics),
            "--csv",
            str(csv_path),
        ]
        if group_by:
            cmd += ["--group-by", ",".join(group_by)]
        if where:
            for w in where:
                cmd += ["--where", w]
        if order_by:
            cmd += ["--order-by", ",".join(order_by)]
        if limit:
            cmd += ["--limit", str(int(limit))]
        if explain:
            cmd += ["--explain"]

        proc = _run(cmd)

        rows: list[dict] = []
        if csv_path.exists():
            with csv_path.open() as f:
                rows = list(csv.DictReader(f))

        sql = None
        if explain and "SQL Query" in proc.stdout:
            sql = proc.stdout.split("SQL Query", 1)[1].strip()

        return MFResult(rows=rows, sql=sql, raw_stdout=proc.stdout)
