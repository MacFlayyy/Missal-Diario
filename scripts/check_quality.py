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
        for t, p in zip(tapes, pages):
            if not p or p == "—":
                # Tríduo Pascal: fitas que não existem no dia vêm marcadas como "não indicada".
                if not t.get("notIndicated"):
                    fail(key, f"fita {t.get('n')} sem página: {pages}")
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
        # Folheto só existe para o domingo: dia de semana não pode prometer "indicação do folheto".
        if day.weekday() != 6 and not d.get("officialLeafletApplied"):
            for t in tapes:
                for row in t.get("details", []):
                    if isinstance(row, list) and "folheto" in " ".join(map(str, row)).lower():
                        fail(key, f"fita {t.get('n')} fala de folheto num dia de semana: {row[1][:70]}")
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
        if d.get("subtitle") != e.get("subtitle"):
            fail(key, f"linha do título '{d.get('subtitle')}' ≠ padrão '{e.get('subtitle')}'")
        for field in ("color", "season", "cycle"):
            if d.get(field) != e.get(field):
                fail(key, f"{field} '{d.get(field)}' ≠ calendário '{e.get(field)}'")
        for i, part in ((1, 2), (2, 3)):
            got, want = str(d["tapes"][i]["page"]), str(e["tapes"][i]["page"])
            if got != want and part not in verified and i + 1 not in verified:
                fail(key, f"fita {i + 1} p. {got} ≠ calendário p. {want} (sem folheto que justifique)")


VERIFIED_PAIRS = ROOT / "scripts" / "missal_pages_verified.json"


def forever_years() -> list[int]:
    """Anos que cobrem TODOS os casos possíveis do calendário, para sempre.

    O ano litúrgico inteiro depende só de duas coisas: a data da Páscoa
    (35 datas possíveis) e se o ano é bissexto. São no máximo 70 tipos de ano;
    pegamos o primeiro ano de cada tipo a partir de hoje (até 9999), mais os
    próximos anos seguidos. Se todos esses anos estão certos, qualquer ano
    futuro também está, porque ele repete um desses tipos.
    """
    import calendar as cal
    this = datetime.now(ZoneInfo("America/Sao_Paulo")).date().year
    years = {this, this + 1, this + 2}
    seen = set()
    for y in range(this, 10000):
        e = lc.easter(y)
        kind = (e.month, e.day, cal.isleap(y))
        if kind not in seen:
            seen.add(kind)
            years.add(y)
    if len(seen) != 70:
        fail("calendário", f"esperava 70 tipos de ano, achei {len(seen)}")
    return sorted(years)


def expected_cycle(day: date) -> tuple[str, str]:
    """Cálculo independente do ciclo de leituras, para conferir o motor.

    O ano litúrgico começa no 1º Domingo do Advento (domingo entre 27/11 e
    3/12). Domingos: A, B, C conforme o resto da divisão do ano por 3
    (1 → A, 2 → B, 0 → C). Dias de semana do Tempo Comum: Ano I nos anos
    ímpares, Ano II nos pares.
    """
    from datetime import timedelta
    nov27 = date(day.year, 11, 27)
    advent = nov27 + timedelta(days=(6 - nov27.weekday()) % 7)
    lit_year = day.year + 1 if day >= advent else day.year
    return "Ano " + {1: "A", 2: "B", 0: "C"}[lit_year % 3], "Ano " + ("I" if lit_year % 2 else "II")


def check_cycle(day: date, e: dict) -> None:
    abc, weekday = expected_cycle(day)
    cycle = e.get("cycle", "—")
    where = day.isoformat()
    if cycle in ("Ano A", "Ano B", "Ano C") and cycle != abc:
        fail(where, f"ciclo {cycle} ≠ {abc}")
    if cycle in ("Ano I", "Ano II") and cycle != weekday:
        fail(where, f"ciclo {cycle} ≠ {weekday}")
    if day.weekday() == 6 and cycle not in ("Ano A", "Ano B", "Ano C"):
        fail(where, f"domingo sem ano A/B/C: {cycle}")
    if e.get("grade") == "Dia de semana" and e.get("season") == "Tempo Comum" and cycle != weekday:
        fail(where, f"dia de semana do Tempo Comum sem {weekday}: {cycle}")
    # Linha abaixo do título, em qualquer ano: domingo mostra Ano A/B/C;
    # dia de semana do Tempo Comum (sem solenidade/festa) mostra Ano I/II;
    # os demais dias mostram só o tempo, sem ano.
    sub = str(e.get("subtitle", ""))
    lord_abc = ("Santíssima Trindade", "Santíssimo Corpo e Sangue de Cristo", "Sagrado Coração de Jesus",
                "Batismo do Senhor", "Sagrada Família de Jesus, Maria e José", "Sábado Santo — Vigília Pascal")
    if day.weekday() == 6 or str(e.get("celebration", "")).startswith(lord_abc):
        want_year = abc
    elif e.get("season") == "Tempo Comum" and e.get("grade") not in ("Solenidade", "Festa"):
        want_year = weekday
    else:
        want_year = None
    if want_year and not sub.startswith(want_year + " • "):
        fail(where, f"linha do título '{sub}' deveria começar com '{want_year} • '")
    if not want_year and sub.startswith("Ano "):
        fail(where, f"linha do título '{sub}' não deveria mostrar ano")
    pref = e["tapes"][2]
    # 3º, 4º e 5º Domingos da Quaresma: prefácio próprio só no Ano A.
    if day.weekday() == 6 and e.get("season") == "Quaresma" and pref.get("page") in ("187", "196", "204") and abc != "Ano A":
        fail(where, f"prefácio próprio do Ano A usado no {abc}")


def check_cycle_400_years() -> None:
    """O ciclo A/B/C e I/II repete a cada 6 anos e o calendário gregoriano a
    cada 400: confere as viradas do ano litúrgico em 400 anos seguidos."""
    from datetime import timedelta
    this = datetime.now(ZoneInfo("America/Sao_Paulo")).date().year
    for y in range(this, this + 400):
        nov27 = date(y, 11, 27)
        advent = nov27 + timedelta(days=(6 - nov27.weekday()) % 7)
        for day in (advent - timedelta(days=1), advent, advent + timedelta(days=7), date(y, 7, 1)):
            check_cycle(day, lc.build_entry(day))


def check_engine_forever() -> None:
    """Exige que cada fita, em todo tipo de ano possível, aponte para uma
    combinação já conferida no Missal. Nenhuma página nova entra no site sem
    ter sido verificada, em nenhum ano futuro."""
    from datetime import timedelta
    ok = {tuple(x) for x in json.loads(VERIFIED_PAIRS.read_text(encoding="utf-8"))["pares"]}
    seen, text_seen = set(), set()
    for year in forever_years():
        day = date(year, 1, 1)
        while day.year == year:
            try:
                e = lc.build_entry(day)
            except Exception as exc:  # noqa: BLE001
                fail(day.isoformat(), f"calendário automático falhou: {exc}")
            else:
                before = len(problems)
                walk_text(e, day.isoformat())
                for t in e["tapes"]:
                    if str(t.get("title", "")).rstrip().endswith((",", "—", "-")):
                        fail(day.isoformat(), f"fita {t.get('n')} com título cortado: {t.get('title')}")
                    if t.get("n") == 3 and not t.get("notIndicated") and not str(t.get("title", "")).startswith("Prefácio próprio") \
                            and " / " not in str(t.get("page")) and not any(r[0] == "Título" for r in t.get("details", [])):
                        fail(day.isoformat(), f"prefácio sem subtítulo: {t.get('title')}")
                check_cycle(day, e)
                if len(problems) > before:
                    seen_text = {p.split(": ", 1)[-1] for p in problems[before:]}
                    del problems[before:]
                    for msg in sorted(seen_text - text_seen):
                        fail(day.isoformat(), msg)
                    text_seen |= seen_text
                for t in e["tapes"]:
                    k = (t.get("n"), str(t.get("page")), t.get("title"))
                    if k not in ok and k not in seen:
                        seen.add(k)
                        fail(day.isoformat(), f"fita {k[0]} p. {k[1]} '{k[2]}' ainda não conferida no Missal")
            day += timedelta(days=1)


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
    check_engine_forever()
    check_cycle_400_years()
    check_page()
    if problems:
        print(f"QUALIDADE: {len(problems)} problema(s) encontrado(s):")
        for p in problems:
            print("  ✗", p)
        return 1
    print(f"QUALIDADE OK: {len(data)} dias, calendário de todos os anos possíveis conferido e página sem erros.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
