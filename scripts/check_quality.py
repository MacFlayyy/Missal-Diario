#!/usr/bin/env python3
"""Verificação de qualidade que roda em TODA publicação (diária e de código).

Junta numa só rede as conferências que antes eram feitas à mão:

1. Dados de todos os dias: data × dia da semana, ordem das fitas, resumo
   rápido × páginas das fitas, cor × código da cor, textos quebrados
   (undefined, espaços duplos, palavra repetida, parênteses/aspas abertos).
2. Calendário: de hoje em diante, cada dia precisa bater com o motor do
   calendário litúrgico (cor, tempo, página da Missa e do Prefácio), a não ser
   nas partes conferidas no folheto oficial.
3. Página HTML: um único <main>, nenhum id repetido, toda referência ARIA e
   todo label apontando para um id que existe, nenhum link interno quebrado.

Sai com código 1 e lista cada problema se encontrar qualquer erro.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import liturgical_calendar as lc  # noqa: E402

WEEKDAYS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
            "Sexta-feira", "Sábado", "Domingo"]
COLOR_HEX = lc.COLOR_HEX
TEXT_RULES = [
    (re.compile(r"\bundefined\b|\bNone\b|\bnull\b|\bNaN\b|\?\?|\[object"), "texto quebrado"),
    (re.compile(r"\S  +\S"), "espaço duplo"),
    (re.compile(r"\s[,;:](?!\d)|\s\.(?![\d.])"), "espaço antes de pontuação"),
    (re.compile(r"^\s|\s$"), "espaço sobrando nas pontas"),
    (re.compile(r"\.\.(?!\.)"), "ponto duplo"),
    (re.compile(r"\b(\w{2,})\s+\1\b", re.I), "palavra repetida"),
]
URL_KEYS = {"folhetoUrl", "folhetoDesktopUrl", "folhetoMobileUrl", "colorHex", "source", "sourceUrl"}

problems: list[str] = []


def fail(where: str, msg: str) -> None:
    problems.append(f"{where}: {msg}")


def load_js_object(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    return json.loads(src[src.index("{"):src.rindex("}") + 1])


def walk_text(value, where, key=""):
    if isinstance(value, dict):
        for k, v in value.items():
            if k not in URL_KEYS:
                walk_text(v, f"{where}.{k}", k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            walk_text(v, f"{where}[{i}]", key)
    elif isinstance(value, str):
        for rule, name in TEXT_RULES:
            m = rule.search(value)
            if m:
                fail(where, f"{name} → …{value[max(0, m.start() - 25):m.end() + 25]}…")
        if value.count("(") != value.count(")"):
            fail(where, f"parênteses sem par → {value[:90]}")
        if value.count("“") != value.count("”") or value.count('"') % 2:
            fail(where, f"aspas sem par → {value[:90]}")


def check_data(data: dict, status: dict) -> None:
    for key, d in sorted(data.items()):
        day = date.fromisoformat(key)
        label = d.get("label", "")
        if not label.startswith(WEEKDAYS[day.weekday()]):
            fail(key, f"rótulo com dia da semana errado: {label}")
        if day.strftime("%d/%m/%Y") not in label:
            fail(key, f"rótulo com data errada: {label}")
        tapes = d.get("tapes") or []
        if [t.get("n") for t in tapes] != [1, 2, 3, 4, 5]:
            fail(key, f"fitas fora de ordem: {[t.get('n') for t in tapes]}")
        pages, quick = [str(t.get("page", "")) for t in tapes], []
        for p in pages:
            if not p or p == "—":
                fail(key, f"fita sem página: {pages}")
            elif not quick or quick[-1] != p:
                quick.append(p)
        if d.get("quick", "").replace(" ", "") != "→".join(quick).replace(" ", ""):
            fail(key, f"resumo rápido '{d.get('quick')}' ≠ fitas {pages}")
        for t in tapes:
            if not str(t.get("title", "")).strip():
                fail(key, f"fita {t.get('n')} sem título")
            for row in t.get("details", []):
                if not (isinstance(row, list) and len(row) == 2 and all(isinstance(x, str) and x.strip() for x in row)):
                    fail(key, f"fita {t.get('n')} com detalhe malformado: {row!r}")
        mass_page = str(tapes[1].get("page", "")).split()[0] if len(tapes) > 1 else ""
        for t in tapes:
            for row in t.get("details", []):
                m = re.search(r"Formulário: p\. (\d+)", str(row[1]) if isinstance(row, list) and len(row) == 2 else "")
                if m and m.group(1) != mass_page:
                    fail(key, f"fita {t.get('n')} cita formulário na p. {m.group(1)}, mas a Missa está na p. {mass_page}")
        if d.get("color") not in COLOR_HEX:
            fail(key, f"cor desconhecida: {d.get('color')}")
        elif d.get("colorHex", "").lower() != COLOR_HEX[d["color"]]:
            fail(key, f"código da cor {d.get('colorHex')} não corresponde a {d['color']}")
        for field in ("celebration", "season", "grade", "cycle"):
            if not str(d.get(field, "")).strip():
                fail(key, f"campo vazio: {field}")
        walk_text(d, key)

    through = status.get("availableThrough", "")
    if through not in data:
        fail("status.js", f"availableThrough {through} não existe em data.js")


# Diferenças antigas e já conferidas (folheto aplicado ou página do título).
KNOWN_DIFFERENCES = {"2026-10-02", "2026-10-05", "2026-10-06", "2026-10-12"}


def check_calendar(data: dict) -> None:
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()
    for key, d in sorted(data.items()):
        if key < today or key in KNOWN_DIFFERENCES:
            continue
        e = lc.build_entry(date.fromisoformat(key))
        verified = set(d.get("officialVerifiedParts") or []) if d.get("officialLeafletApplied") else set()
        for field in ("color", "season", "cycle"):
            if d.get(field) != e.get(field):
                fail(key, f"{field} '{d.get(field)}' ≠ calendário '{e.get(field)}'")
        for i, part in ((1, 2), (2, 3)):
            got, want = str(d["tapes"][i]["page"]), str(e["tapes"][i]["page"])
            if got != want and part not in verified and i + 1 not in verified:
                fail(key, f"fita {i + 1} p. {got} ≠ calendário p. {want} (sem folheto que justifique)")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.refs, self.mains, self.hrefs = [], [], 0, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "main":
            self.mains += 1
        if a.get("id"):
            self.ids.append(a["id"])
        for attr in ("aria-labelledby", "aria-describedby", "aria-controls", "aria-owns", "for", "list"):
            if a.get(attr):
                self.refs += [(attr, x) for x in a[attr].split()]
        if tag == "a" and (a.get("href") or "").startswith("#") and len(a["href"]) > 1:
            self.hrefs.append(a["href"][1:])


def check_page() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    p = PageParser()
    p.feed(html)
    if p.mains != 1:
        fail("index.html", f"{p.mains} elementos <main> (deve haver 1)")
    seen = set()
    for i in p.ids:
        if i in seen:
            fail("index.html", f"id repetido: {i}")
        seen.add(i)
    # ids criados pelo JavaScript também contam como destino válido.
    dynamic = set(re.findall(r"\.id\s*=\s*['\"]([\w-]+)['\"]", html)) | set(re.findall(r"id=\\?['\"]([\w-]+)\\?['\"]", html))
    for attr, ref in p.refs:
        if ref not in seen and ref not in dynamic:
            fail("index.html", f"{attr}='{ref}' aponta para id inexistente")
    for ref in p.hrefs:
        if ref not in seen and ref not in dynamic:
            fail("index.html", f"link interno #{ref} sem destino")


def main() -> int:
    data = load_js_object(ROOT / "data.js")
    status = load_js_object(ROOT / "status.js")
    check_data(data, status)
    check_calendar(data)
    check_page()
    if problems:
        print(f"QUALIDADE: {len(problems)} problema(s) encontrado(s):")
        for p in problems:
            print("  ✗", p)
        return 1
    print(f"QUALIDADE OK: {len(data)} dias, calendário e página sem erros.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
