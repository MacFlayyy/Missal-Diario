#!/usr/bin/env python3
"""Robô corretor do Missal Diário.

Roda antes das verificações em toda atualização. Em vez de só barrar a
publicação, corrige sozinho o que estiver fora do padrão nos dias de hoje em
diante, sempre pelo calendário litúrgico perpétuo e pelas páginas já
conferidas no Missal:

1. Correções pontuais: rótulo (dia da semana e data), linha abaixo do título,
   ciclo, tempo litúrgico, cor e código da cor, ordem das fitas, páginas de
   Missa e Prefácio sem folheto que as justifique, resumo rápido, espaços
   duplos ou nas pontas dos textos e campos vazios.
2. Se depois disso um dia ainda tiver qualquer problema nas verificações de
   qualidade, o dia inteiro é refeito do zero pelo Missal (sem o folheto) e
   verificado de novo.

Folheto oficial aplicado e conferido nunca é desfeito por uma correção
pontual: só as partes que o folheto não confirmou seguem o calendário.
Imprime tudo o que foi corrigido; sai com código 0 mesmo sem correções.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import liturgical_calendar as lc  # noqa: E402
from ritos_texts import apply_rite_suggestions, fill_folheto_gaps, quick_from_tapes  # noqa: E402
from validate_daily import load_js_object, save_data  # noqa: E402

DATA_FILE = ROOT / "data.js"
TZ = ZoneInfo("America/Sao_Paulo")
WEEKDAYS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
            "Sexta-feira", "Sábado", "Domingo"]
URL_KEYS = {"folhetoUrl", "folhetoDesktopUrl", "folhetoMobileUrl", "colorHex", "source", "sourceUrl",
            "dailySourceUrl", "ritesOfficialUrl"}


def fresh_entry(day: date) -> dict:
    """O dia montado do zero pelo Missal, como o robô diário faz."""
    entry = lc.build_entry(day)
    apply_rite_suggestions(entry)
    fill_folheto_gaps(entry)
    entry["quick"] = quick_from_tapes(entry["tapes"])
    return entry


def tidy_text(value, fixes, where, key=""):
    """Tira espaços duplos e nas pontas, sem mexer em links."""
    if isinstance(value, dict):
        for k, v in list(value.items()):
            if k in URL_KEYS:
                continue
            new = tidy_text(v, fixes, where, k)
            if new is not v:
                value[k] = new
        return value
    if isinstance(value, list):
        for i, v in enumerate(value):
            new = tidy_text(v, fixes, where, key)
            if new is not v:
                value[i] = new
        return value
    if isinstance(value, str):
        new = re.sub(r"(?<=\S) {2,}(?=\S)", " ", value).strip()
        if new != value:
            fixes.append(f"{where}: espaço sobrando corrigido em “{new[:50]}”")
            return new
    return value


def fix_entry(key: str, d: dict) -> list[str]:
    day = date.fromisoformat(key)
    e = lc.build_entry(day)
    fixes: list[str] = []
    leaflet = bool(d.get("officialLeafletApplied"))
    verified = set(d.get("officialVerifiedParts") or []) if leaflet else set()

    label = f"{WEEKDAYS[day.weekday()]} • {day:%d/%m/%Y}"
    if d.get("label") != label:
        fixes.append(f"{key}: rótulo '{d.get('label')}' → '{label}'")
        d["label"] = label

    for field in ("subtitle", "cycle", "season"):
        if d.get(field) != e.get(field):
            fixes.append(f"{key}: {field} '{d.get(field)}' → '{e.get(field)}'")
            d[field] = e[field]
    if not leaflet and (d.get("color"), d.get("colorHex")) != (e.get("color"), e.get("colorHex")):
        fixes.append(f"{key}: cor '{d.get('color')}' → '{e.get('color')}'")
        d["color"], d["colorHex"] = e["color"], e["colorHex"]
    if d.get("color") in lc.COLOR_HEX and str(d.get("colorHex", "")).lower() != lc.COLOR_HEX[d["color"]]:
        fixes.append(f"{key}: código da cor corrigido para {d['color']}")
        d["colorHex"] = lc.COLOR_HEX[d["color"]]
    for field in ("celebration", "grade"):
        if not str(d.get(field, "")).strip():
            fixes.append(f"{key}: campo vazio '{field}' preenchido pelo Missal")
            d[field] = e[field]

    tapes = d.get("tapes") or []
    if [t.get("n") for t in tapes] != [1, 2, 3, 4, 5]:
        by_n = {t.get("n"): t for t in tapes}
        d["tapes"] = [by_n.get(n) or e["tapes"][n - 1] for n in range(1, 6)]
        fixes.append(f"{key}: fitas reorganizadas na ordem 1 a 5")
        tapes = d["tapes"]

    # Missa (fita 2) e Prefácio (fita 3): sem folheto que confirme, seguem o Missal.
    for i in (1, 2):
        if i + 1 in verified:
            continue
        got, want = str(tapes[i].get("page")), str(e["tapes"][i].get("page"))
        if got != want:
            fixes.append(f"{key}: fita {i + 1} p. {got} → p. {want} (Missal)")
            tapes[i] = e["tapes"][i]

    tidy_text(d, fixes, key)

    quick = quick_from_tapes(tapes)
    if str(d.get("quick", "")).replace(" ", "") != quick.replace(" ", ""):
        fixes.append(f"{key}: resumo rápido refeito → {quick}")
        d["quick"] = quick
    return fixes


def remaining_problems(data: dict) -> dict[str, list[str]]:
    """Roda as verificações de qualidade dos dados e agrupa por dia."""
    import check_quality as cq
    cq.problems.clear()
    status_file = ROOT / "status.js"
    status = cq.load_js_object(status_file) if status_file.exists() else {}
    cq.check_data(data, status)
    cq.check_calendar(data)
    found: dict[str, list[str]] = {}
    for p in cq.problems:
        where, _, msg = p.partition(": ")
        found.setdefault(where.split(".")[0].split("[")[0], []).append(msg)
    cq.problems.clear()
    return found


def main() -> int:
    data = load_js_object(DATA_FILE, "window.MISSAL_DATA")
    today = datetime.now(TZ).date().isoformat()
    fixes: list[str] = []

    for key in sorted(k for k in data if k >= today):
        fixes += fix_entry(key, data[key])

    for key, msgs in sorted(remaining_problems(data).items()):
        if key < today or key not in data:
            continue
        data[key] = fresh_entry(date.fromisoformat(key))
        fixes.append(f"{key}: refeito pelo Missal por causa de: {'; '.join(msgs)[:200]}")

    if fixes:
        save_data(data)
        print("ROBÔ CORRETOR — correções feitas:")
        for f in fixes:
            print(f"- {f}")
        summary = __import__("os").environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write("## Robô corretor\n" + "\n".join(f"- {f}" for f in fixes) + "\n")
    else:
        print("ROBÔ CORRETOR: nada para corrigir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
