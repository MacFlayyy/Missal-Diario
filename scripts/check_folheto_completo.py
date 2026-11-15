#!/usr/bin/env python3
"""Confere se o domingo já liberado está 100% conforme o folheto.

Regra do projeto: nos dias com folheto, tudo deve bater com o folheto. Este
teste falha (e o workflow abre um aviso no GitHub) quando o domingo da semana
já está publicado e:
  - o folheto existe mas não foi aplicado, ou
  - faltou reconhecer Ritos Iniciais (1), Prefácio (3) ou Oração Eucarística (4).

Sem folheto publicado ainda, só avisa (código 2). Não bloqueia a publicação: o dia continua no ar com as sugestões do Missal,
marcadas como "Sugestão", até o leitor ser corrigido.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {1, 3, 4}


def load(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    return json.loads(src[src.index("{"):src.rindex("}") + 1])


def main() -> int:
    data, status = load(ROOT / "data.js"), load(ROOT / "status.js")
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    sunday = today + timedelta(days=(6 - today.weekday()) % 7)
    key = sunday.isoformat()
    if status.get("availableThrough", "") < key:
        print(f"Domingo {key} ainda não liberado; nada a conferir.")
        return 0
    d = data.get(key)
    if not d:
        print(f"ERRO: domingo {key} liberado mas ausente de data.js")
        return 1
    url = d.get("folhetoDesktopUrl") or d.get("folhetoUrl")
    if not url:
        print(f"AVISO: domingo {key} liberado; o folheto ainda não foi publicado pela arquidiocese.")
        return 2
    parts = set(d.get("officialVerifiedParts") or [])
    missing = sorted(REQUIRED - parts) if d.get("officialLeafletApplied") else sorted(REQUIRED)
    if missing:
        names = {1: "Ritos Iniciais", 3: "Prefácio", 4: "Oração Eucarística"}
        print(f"ERRO: folheto de {key} não foi totalmente aplicado. Faltou: "
              + ", ".join(names[m] for m in missing) + f"\nFolheto: {url}")
        return 1
    print(f"Folheto de {key} aplicado por completo (partes {sorted(parts)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
