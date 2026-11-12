#!/usr/bin/env python3
"""Gera os dias que ainda não existem em data.js.

Não depende de calendário anual cadastrado nem de sites externos: cada dia é
calculado por ``liturgical_calendar`` (calendário litúrgico perpétuo do Brasil)
e recebe as páginas do Missal Romano a partir de ``missal-calendar-index.json``.
"""
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from liturgical_calendar import build_entry, sunday_cycle  # noqa: E402
from ritos_texts import quick_from_tapes  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data.js"
TZ = ZoneInfo("America/Sao_Paulo")
# Dias gerados com antecedência, para que os folhetos (publicados alguns dias
# antes) possam ser aplicados. O site só mostra cada dia a partir das 05h.
DAYS_AHEAD = 40


def liturgical_year(day):
    return sunday_cycle(day)


def new_entry(day):
    entry = build_entry(day)
    entry["quick"] = quick_from_tapes(entry["tapes"])
    return entry


def ensure_dates(data, day, days_ahead=1):
    """Garante o dia pedido e os seguintes; devolve as datas acrescentadas."""
    added = []
    for offset in range(days_ahead + 1):
        current = day + timedelta(days=offset)
        key = current.isoformat()
        if key in data:
            continue
        data[key] = new_entry(current)
        added.append(key)
    return added


def main():
    day = datetime.now(TZ).date()
    text = DATA_FILE.read_text(encoding="utf-8")
    match = re.search(r"window\.MISSAL_DATA\s*=\s*(\{.*\})\s*;\s*$", text, re.S)
    if not match:
        raise RuntimeError("data.js inválido")
    data = json.loads(match.group(1))
    # Se a atualização ficou parada por algum tempo, preenche também os dias que faltaram.
    last = max((k for k in data if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k)), default=day.isoformat())
    start = min(day, datetime.fromisoformat(last).date() + timedelta(days=1))
    added = ensure_dates(data, start, (day - start).days + DAYS_AHEAD)
    if added:
        ordered = dict(sorted(data.items()))
        DATA_FILE.write_text("window.MISSAL_DATA = " +
                             json.dumps(ordered, ensure_ascii=False, indent=2) + ";\n",
                             encoding="utf-8")
    print("[geração diária] " + (f"{len(added)} dia(s): {added[0]} … {added[-1]}" if added
                                   else "datas já cadastradas"))
    if day.isoformat() not in data:
        raise RuntimeError("Data de hoje não foi gerada; publicação bloqueada")


if __name__ == "__main__":
    main()
