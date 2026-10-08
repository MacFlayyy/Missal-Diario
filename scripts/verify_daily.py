#!/usr/bin/env python3
"""Falha a automação se o Missal do dia não estiver realmente pronto."""

from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import re

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("America/Sao_Paulo")


def load_js(path, variable):
    raw = path.read_text(encoding="utf-8")
    m = re.search(rf"{re.escape(variable)}\s*=\s*(\{{.*\}})\s*;\s*$", raw, re.S)
    if not m:
        raise RuntimeError(f"Não foi possível ler {path.name}")
    return json.loads(m.group(1))


def main():
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    data = load_js(ROOT / "data.js", "window.MISSAL_DATA")
    status = load_js(ROOT / "status.js", "window.MISSAL_STATUS")
    standalone = (ROOT / "Missal-Diario-Standalone.html").read_text(encoding="utf-8")

    errors = []
    if today not in data:
        errors.append(f"data.js não contém {today}")
    if status.get("availableThrough") != today:
        errors.append(
            f"status.js disponível até {status.get('availableThrough')!r}, esperado {today!r}"
        )
    if f'"{today}"' not in standalone:
        errors.append(f"standalone não contém {today}")

    now = datetime.now(TZ)
    if now.weekday() == 5:
        next_sunday = (now.date() + timedelta(days=1)).isoformat()
        if next_sunday in data and status.get("sundayPreview") != next_sunday:
            errors.append(f"Prévia dominical não foi liberada para {next_sunday}")

    if errors:
        raise SystemExit("PUBLICAÇÃO BLOQUEADA:\n- " + "\n- ".join(errors))

    print(f"Validação local OK para {today}.")


if __name__ == "__main__":
    main()
