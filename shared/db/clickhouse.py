from __future__ import annotations

from typing import Any

from clickhouse_driver import Client

from shared.config import settings

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            database=settings.clickhouse_db,
            user=settings.clickhouse_user,
            password=settings.clickhouse_password,
            settings={"use_numpy": False},
        )
    return _client


def execute(query: str, params: dict[str, Any] | None = None) -> list[Any]:
    return get_client().execute(query, params or {})


def execute_with_column_types(query: str, params: dict[str, Any] | None = None) -> tuple[list[Any], list[Any]]:
    return get_client().execute(query, params or {}, with_column_types=True)


def insert(table: str, rows: list[dict[str, Any]], column_names: list[str]) -> None:
    if not rows:
        return
    data = [[row[col] for col in column_names] for row in rows]
    get_client().execute(
        f"INSERT INTO {table} ({', '.join(column_names)}) VALUES",  # noqa: S608
        data,
    )
