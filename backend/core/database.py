from collections.abc import Callable, Iterator
from contextlib import contextmanager

from psycopg_pool import ConnectionPool

from core.config import settings

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.db_conninfo,
            min_size=1,
            max_size=10,
            kwargs={"connect_timeout": 10},
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection() -> Iterator:
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def init_schema() -> None:
    # Ленивый импорт: иначе цикл core.database ↔ models.* (CRUD тянет connection).
    from models.admin_data import ADMIN_DATA_DDL
    from models.audit_runs import AUDIT_RUNS_DDL
    from models.diagnoses import DIAGNOSES_DDL
    from models.events import EVENTS_DDL
    from models.incidents import (
        INCIDENT_EVENTS_DDL,
        INCIDENTS_DDL,
        ensure_incident_events_event_unique,
    )

    statements = [
        EVENTS_DDL,
        INCIDENTS_DDL,
        INCIDENT_EVENTS_DDL,
        DIAGNOSES_DDL,
        AUDIT_RUNS_DDL,
        ADMIN_DATA_DDL,
    ]
    with connection() as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
            ensure_incident_events_event_unique(cur)
        conn.commit()


def run_tx(fn: Callable) -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            fn(cur)
        conn.commit()
