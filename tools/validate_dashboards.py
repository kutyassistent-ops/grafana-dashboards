#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка экспортированных дашбордов Grafana.

Проверяет, что каждый JSON в репозитории — валидный ресурс Grafana
(resource API, `dashboard.grafana.app/v2`), и печатает сводку: UID, заголовок,
число панелей, строк и переменных.

Запуск:

    python tools/validate_dashboards.py

Код возврата 0 — все файлы в порядке, 1 — есть проблемы.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXPECTED_API = "dashboard.grafana.app/v2"
EXPECTED_KIND = "Dashboard"


def collect_panels(spec):
    """Панели лежат в spec.elements как карта panel-<id> -> панель.

    На разных выгрузках это либо объект-карта, либо список с одним объектом —
    поддерживаются оба варианта.
    """
    elements = spec.get("elements") or {}
    if isinstance(elements, dict):
        return elements
    if isinstance(elements, list):
        for item in elements:
            if isinstance(item, dict):
                return item
    return {}


def count_rows(spec):
    """Строки (ряды) лежат в spec.layout.spec.rows (иногда layout — список)."""
    layout = spec.get("layout") or {}
    if isinstance(layout, list):
        layout = layout[0] if layout else {}
    if not isinstance(layout, dict):
        return 0
    inner = layout.get("spec") or {}
    if not isinstance(inner, dict):
        return 0
    return len(inner.get("rows") or [])


def validate(path):
    """Возвращает (проблемы, сводка) для одного файла."""
    problems = []
    raw = path.read_text(encoding="utf-8")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return ["не является валидным JSON: %s" % exc], {}

    for key in ("apiVersion", "kind", "metadata", "spec"):
        if key not in data:
            problems.append("нет поля %s" % key)

    if data.get("apiVersion") != EXPECTED_API:
        problems.append(
            "apiVersion = %r, ожидался %r" % (data.get("apiVersion"), EXPECTED_API)
        )
    if data.get("kind") != EXPECTED_KIND:
        problems.append("kind = %r, ожидался %r" % (data.get("kind"), EXPECTED_KIND))

    meta = data.get("metadata") or {}
    if not meta.get("name"):
        problems.append("нет metadata.name (classic UID дашборда)")

    spec = data.get("spec") or {}
    if not spec.get("title"):
        problems.append("нет spec.title")

    panels = collect_panels(spec)
    if not panels:
        problems.append("нет панелей (spec.elements)")

    variables = spec.get("variables") or []
    for var in variables:
        inner = var.get("spec") or {}
        if not inner.get("name"):
            problems.append("переменная без имени: %r" % var)

    summary = {
        "uid": meta.get("name", "?"),
        "title": spec.get("title", "?"),
        "panels": len(panels),
        "rows": count_rows(spec),
        "variables": len(variables),
        "var_names": [((v.get("spec") or {}).get("name", "?")) for v in variables],
    }
    return problems, summary


def main():
    files = sorted(REPO.rglob("*.json"))
    files = [f for f in files if ".git" not in f.parts and "tools" not in f.parts]

    if not files:
        print("JSON-файлы дашбордов не найдены")
        return 1

    failed = False
    print("%-22s %-34s %6s %5s %5s  %s" % ("UID", "Заголовок", "Панелей", "Строк", "Перем.", "Переменные"))
    print("-" * 96)

    for path in files:
        rel = path.relative_to(REPO)
        problems, summary = validate(path)
        if problems:
            failed = True
            print("ОШИБКА  %s" % rel)
            for problem in problems:
                print("        - %s" % problem)
        else:
            print(
                "%-22s %-34s %6d %5d %5d  %s"
                % (
                    summary["uid"],
                    summary["title"][:33],
                    summary["panels"],
                    summary["rows"],
                    summary["variables"],
                    ", ".join(summary["var_names"]) or "-",
                )
            )

    print("-" * 96)
    print("Проверено файлов: %d" % len(files))
    if failed:
        print("Есть ошибки")
        return 1
    print("Все дашборды валидны")
    return 0


if __name__ == "__main__":
    sys.exit(main())
