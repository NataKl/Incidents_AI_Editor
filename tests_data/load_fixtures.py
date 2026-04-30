#!/usr/bin/env python3
"""Загрузка tests_data/events.json и tests_data/incidents.json в PostgreSQL (events, incidents, incident_events).

Запуск (контейнер app, см. том ./tests_data):

  docker compose exec app python /app/tests_data/load_fixtures.py --purge-all-tables

С корня проекта без Docker:

  PYTHONPATH=backend python tests_data/load_fixtures.py [--purge-all-tables]

По умолчанию удаляются только строки с детерминированными UUID фикстуры; «чужие» события сохраняются.
Для полной очистки таблиц перед загрузкой используйте --purge-all-tables.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import psycopg

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
if (_ROOT / "core").is_dir():
    sys.path.insert(0, str(_ROOT))
elif _BACKEND.is_dir():
    sys.path.insert(0, str(_BACKEND))


def fixture_event_id(line_1based: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"ai_editor:fixture:event:{line_1based}")


def fixture_incident_id(slug: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"ai_editor:fixture:incident:{slug}")


def pg_conn():
    os.environ.setdefault("POSTGRES_HOST", "db")
    from core.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    return psycopg.connect(
        dbname=s.postgres_db,
        user=s.postgres_user,
        password=s.postgres_password,
        host=s.postgres_host,
        port=s.postgres_port,
    )


def parse_ts(ts: object) -> datetime | None:
    if ts is None or ts == "null":
        return None
    if isinstance(ts, str):
        s = ts.strip()
        if s == "" or s.lower() == "null":
            return None
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    return None


def load_fixtures(
    *,
    purge_all_test_tables: bool = False,
    delete_fixtures_only: bool = True,
) -> None:
    fixtures = Path(__file__).resolve().parent
    raw_events = fixtures / "events.json"
    raw_inc = fixtures / "incidents.json"

    event_lines = [ln for ln in raw_events.read_text(encoding="utf-8").splitlines() if ln.strip()]
    incidents_lines = [ln for ln in raw_inc.read_text(encoding="utf-8").splitlines() if ln.strip()]

    payloads: list[tuple[int, dict]] = []

    lineno = 0
    for ln in event_lines:
        lineno += 1
        obj = json.loads(ln)
        payloads.append((lineno, obj))

    incident_specs: list[dict] = [json.loads(ln) for ln in incidents_lines]

    with pg_conn() as conn:
        with conn.cursor() as cur:
            if purge_all_test_tables:
                cur.execute(
                    "TRUNCATE incident_events, diagnoses, incidents, events CASCADE"
                )
            elif delete_fixtures_only:
                inc_ids = [fixture_incident_id(str(i)) for i, _ in enumerate(incident_specs)]
                eve_ids_delete = [
                    fixture_event_id(line) for line in range(1, len(event_lines) + 1)
                ]
                for iid in inc_ids:
                    cur.execute("DELETE FROM incident_events WHERE incident_id = %s", (str(iid),))
                for iid in inc_ids:
                    cur.execute(
                        "DELETE FROM diagnoses WHERE incident_id = %s::uuid",
                        (str(iid),),
                    )
                cur.execute(
                    "DELETE FROM incidents WHERE id = ANY(%s::uuid[])",
                    ([str(x) for x in inc_ids],),
                )
                cur.execute(
                    "DELETE FROM events WHERE id = ANY(%s::uuid[])",
                    ([str(x) for x in eve_ids_delete],),
                )

            for lineno, obj in payloads:
                eid = fixture_event_id(lineno)
                level_raw = obj.get("level")
                message = obj.get("message")
                svc = obj.get("service")
                ts = parse_ts(obj.get("ts"))

                if lineno == 19:
                    # некорректный level из примера 18–20 — CHECK в таблице events не допускает
                    continue

                level = (
                    level_raw.strip().lower()
                    if isinstance(level_raw, str)
                    else str(level_raw)
                ).lower()
                assert level in ("info", "warning", "error"), lineno

                if svc is None:
                    raise RuntimeError(f"line {lineno}: missing service")
                svc_s = svc.strip()
                msg_s = message if isinstance(message, str) else ""
                msg_s = msg_s.strip() if lineno != 18 else (message or "")

                created_at_val = parse_ts(obj.get("created_at"))

                if created_at_val is not None:
                    cur.execute(
                        """
                        INSERT INTO events (id, created_at, service, level, message, ts)
                        VALUES (%s::uuid, %s, %s, %s, %s, %s)
                        """,
                        (str(eid), created_at_val, svc_s, level, msg_s, ts),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO events (id, service, level, message, ts)
                        VALUES (%s::uuid, %s, %s, %s, %s)
                        """,
                        (str(eid), svc_s, level, msg_s, ts),
                    )

            for idx, inc in enumerate(incident_specs):
                iid = fixture_incident_id(str(idx))
                title = inc["title"].strip()
                priority = int(inc["priority"])
                lines_1based: list[int] = [int(x) for x in inc["event_lines_1based"]]
                cur.execute(
                    """
                    INSERT INTO incidents (id, title, priority)
                    VALUES (%s::uuid, %s, %s)
                    """,
                    (str(iid), title, priority),
                )
                for bl in lines_1based:
                    ev = fixture_event_id(bl)
                    if bl == 19:
                        raise RuntimeError(
                            "incident ссылается на строку 19: эта строка имеет недопустимый level для БД"
                        )
                    cur.execute(
                        """
                        INSERT INTO incident_events (incident_id, event_id)
                        VALUES (%s::uuid, %s::uuid)
                        """,
                        (str(iid), str(ev)),
                    )

        conn.commit()

    skipped = [(ln, o) for ln, o in payloads if ln == 19]
    print(
        "Готово: событий вставлено",
        len(payloads) - len(skipped),
        "пропуск строки некорректного level:",
        skipped and skipped[0][0],
    )
    print("Инцидентов:", len(incident_specs))


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Загрузка тестовых событий/инцидентов.")
    p.add_argument(
        "--purge-all-tables",
        action="store_true",
        help="Перед загрузкой TRUNCATE таблиц events, incidents, incident_events (и связанное). "
        "Без этого удаляются только строки с детерминированными UUID фикстуры.",
    )
    args = p.parse_args()
    load_fixtures(purge_all_test_tables=args.purge_all_tables, delete_fixtures_only=not args.purge_all_tables)


if __name__ == "__main__":
    main()
