#!/usr/bin/env python3
"""Calendário litúrgico perpétuo (Brasil) com as páginas do Missal Romano.

Calcula, para QUALQUER data, a celebração do dia segundo as Normas Universais
do Ano Litúrgico e o Calendário próprio do Brasil (Missal Romano, 3ª edição
típica, CNBB 2023, p. 69–89), e localiza a página do formulário, do prefácio e
da bênção em ``missal-calendar-index.json`` — índice extraído uma única vez do
próprio Missal. Como o Missal não muda de um ano para o outro, não é preciso
cadastrar calendário anual: nada aqui depende do ano nem de sites externos.
"""
from __future__ import annotations
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
import json
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
_INDEX = json.loads((ROOT / "missal-calendar-index.json").read_text(encoding="utf-8"))
TEMPORAL = _INDEX["temporal"]
MOVABLE = _INDEX["movable"]
SANCTORAL = _INDEX["sanctoral"]
_PREFACES = json.loads((ROOT / "missal-prefaces-verified.json").read_text(encoding="utf-8"))["prefaces"]
PREFACE_BY_PAGE = {str(v["page"]): (k, v.get("subtitle", "")) for k, v in _PREFACES.items()}

DAYS = ("Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
        "Sexta-feira", "Sábado", "Domingo")
COLOR_HEX = {"Branca": "#f7f1df", "Verde": "#3b6f50", "Vermelha": "#9f2d2d",
             "Roxa": "#6b4f7b", "Roxa (ou rósea)": "#7a5b85",
             "Preta ou roxa": "#3f3646",
             "Roxa de manhã / Branca à tarde": "#6b4f7b"}
ORDINAL_M = ("", "Primeiro", "Segundo", "Terceiro", "Quarto", "Quinto", "Sexto", "Sétimo")

# Graus de precedência (Normas Universais, n. 59) — número menor prevalece.
R_TRIDUUM, R_HIGH, R_SOLEMNITY, R_LORD_FEAST, R_SUNDAY, R_FEAST = 1, 2, 3, 5, 6, 7
R_PRIV_FERIA, R_MEMORIAL, R_OPTIONAL, R_FERIA = 9, 10, 12, 13
LORD_FEASTS = {"02-02", "08-06", "09-14", "11-09"}


def _plain(text):
    text = unicodedata.normalize("NFD", str(text).lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def easter(year):
    """Domingo de Páscoa (algoritmo gregoriano de Meeus/Jones/Butcher)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def sunday_of(day):
    """Domingo que abre a semana litúrgica do dia."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def advent_start(year):
    christmas = date(year, 12, 25)
    fourth = christmas - timedelta(days=(christmas.weekday() + 1) % 7 or 7)
    return fourth - timedelta(days=21)


def epiphany(year):
    """No Brasil: domingo entre 2 e 8 de janeiro."""
    first = date(year, 1, 2)
    return first + timedelta(days=(6 - first.weekday()) % 7)


def baptism(year):
    epi = epiphany(year)
    return epi + timedelta(days=1 if epi.day >= 7 else 7)


def sunday_cycle(day):
    """Ano A/B/C: o ano litúrgico começa no 1º Domingo do Advento."""
    lit_year = day.year + 1 if day >= advent_start(day.year) else day.year
    return "Ano " + "CAB"[lit_year % 3]


def weekday_cycle(day):
    return "Ano I" if day.year % 2 else "Ano II"


# ------------------------------------------------------------------ Tempo
def temporal(day):
    """Celebração do Próprio do Tempo: chave do índice, nome, grau e cor."""
    y, wd = day.year, (day.weekday() + 1) % 7      # wd: 0=domingo … 6=sábado
    E = easter(y)
    ash, pentecost = E - timedelta(days=46), E + timedelta(days=49)
    adv = advent_start(y)
    dayname = DAYS[day.weekday()]

    def out(key, name, grade, rank, season, color, **extra):
        return dict(key=key, name=name, grade=grade, rank=rank, season=season,
                    color=color, **extra)

    # ---- Tempo do Natal (início do ano)
    if day == date(y, 1, 1):
        return out("mae-de-deus", "Santa Maria, Mãe de Deus", "Solenidade", R_SOLEMNITY,
                   "Natal", "Branca", saint="Oitava do Natal do Senhor")
    epi, bat = epiphany(y), baptism(y)
    if day == epi:
        return out("epifania", "Epifania do Senhor", "Solenidade", R_HIGH, "Natal", "Branca",
                   vigil="epifania-vigilia")
    if day == bat:
        return out("batismo", "Batismo do Senhor", "Festa", R_LORD_FEAST, "Natal", "Branca")
    if day < bat:
        when = "antes" if day < epi else "depois"
        return out(f"natal-feria-{wd}", f"{dayname} do Tempo do Natal, {when} da Epifania",
                   "Dia de semana", R_FERIA, "Natal", "Branca",
                   hint=("Usar a Coleta indicada para antes da Epifania." if day < epi
                         else "Usar a Coleta indicada para depois da Epifania."))

    # ---- Tempo Comum (primeira parte)
    if day < ash:
        week = (sunday_of(day) - sunday_of(bat)).days // 7 + 1
        return _ordinary(out, week, wd)

    # ---- Quaresma, Semana Santa e Tríduo
    if day < E:
        if day == ash:
            return out("cinzas", "Quarta-feira de Cinzas", "Quarta-feira de Cinzas", R_HIGH,
                       "Quaresma", "Roxa")
        first_sunday = ash + timedelta(days=4)
        if day < first_sunday:
            return out(f"cinzas-{wd}", f"{dayname} depois das Cinzas", "Dia de semana",
                       R_PRIV_FERIA, "Quaresma", "Roxa")
        offset = (E - day).days
        if offset == 7:
            return out("ramos", "Domingo de Ramos da Paixão do Senhor", "Domingo de Ramos",
                       R_HIGH, "Quaresma", "Vermelha")
        if 4 <= offset <= 6:
            return out(f"ss-{wd}", f"{dayname} da Semana Santa", "Semana Santa", R_HIGH,
                       "Quaresma", "Roxa")
        if offset == 3:
            return out("ceia", "Quinta-feira da Ceia do Senhor", "Tríduo Pascal", R_TRIDUUM,
                       "Tríduo Pascal", "Branca", special="ceia")
        if offset == 2:
            return out("paixao", "Sexta-feira da Paixão do Senhor", "Tríduo Pascal", R_TRIDUUM,
                       "Tríduo Pascal", "Vermelha", special="paixao")
        if offset == 1:
            return out("vigilia-pascal", "Sábado Santo — Vigília Pascal na Noite Santa",
                       "Tríduo Pascal", R_TRIDUUM, "Tríduo Pascal", "Branca", special="vigilia")
        week = (day - first_sunday).days // 7 + 1
        if wd == 0:
            name = f"{week}º Domingo da Quaresma" + (" — Laetare" if week == 4 else "")
            return out(f"qua-{week}-0", name, "Domingo da Quaresma", R_HIGH, "Quaresma",
                       "Roxa (ou rósea)" if week == 4 else "Roxa")
        return out(f"qua-{week}-{wd}", f"{dayname} da {week}ª Semana da Quaresma",
                   "Dia de semana", R_PRIV_FERIA, "Quaresma", "Roxa")

    # ---- Tempo Pascal
    if day <= pentecost:
        n = (day - E).days
        if n == 0:
            return out("pascoa", "Domingo da Páscoa na Ressurreição do Senhor", "Solenidade",
                       R_TRIDUUM, "Páscoa", "Branca")
        if n < 7:
            return out(f"oitava-{wd}", f"{dayname} na Oitava da Páscoa", "Oitava da Páscoa",
                       R_HIGH, "Páscoa", "Branca")
        if n == 42:
            return out("ascensao", "Ascensão do Senhor", "Solenidade", R_HIGH, "Páscoa",
                       "Branca", vigil="ascensao-vigilia")
        if n == 49:
            return out("pentecostes", "Domingo de Pentecostes", "Solenidade", R_HIGH, "Páscoa",
                       "Vermelha", vigil="pentecostes-vigilia")
        week = n // 7 + 1
        if wd == 0:
            name = f"{week}º Domingo da Páscoa" + (" — Divina Misericórdia" if week == 2 else "")
            return out(f"pas-{week}-0", name, "Domingo da Páscoa", R_HIGH, "Páscoa", "Branca")
        return out(f"pas-{week}-{wd}", f"{dayname} da {week}ª Semana da Páscoa",
                   "Dia de semana", R_FERIA, "Páscoa", "Branca")

    # ---- Advento e Natal (fim do ano)
    if day >= adv:
        christmas = date(y, 12, 25)
        if day < christmas:
            week = (sunday_of(day) - adv).days // 7 + 1
            if wd == 0:
                name = f"{week}º Domingo do Advento" + (" — Gaudete" if week == 3 else "")
                return out(f"adv-{week}-0", name, "Domingo do Advento", R_HIGH, "Advento",
                           "Roxa (ou rósea)" if week == 3 else "Roxa")
            if day.month == 12 and day.day >= 17:
                if day.day == 24:
                    return out("dec-24", "24 de dezembro — Féria privilegiada do Advento / Vigília do Natal",
                               "Féria privilegiada do Advento", R_PRIV_FERIA, "Advento",
                               "Roxa de manhã / Branca à tarde", special="dec24")
                return out(f"dec-{day.day}", f"{day.day} de dezembro — Féria privilegiada do Advento",
                           "Féria privilegiada do Advento", R_PRIV_FERIA, "Advento", "Roxa")
            return out(f"adv-{week}-{wd}", f"{dayname} da {week}ª Semana do Advento",
                       "Dia de semana", R_FERIA, "Advento", "Roxa")
        if day == christmas:
            return out("natal-dia", "Natal do Senhor", "Solenidade", R_HIGH, "Natal", "Branca",
                       special="natal")
        family = (date(y, 12, 30) if christmas.weekday() == 6
                  else christmas + timedelta(days=(6 - christmas.weekday()) % 7 or 7))
        if day == family:
            return out("sagrada-familia", "Sagrada Família de Jesus, Maria e José", "Festa",
                       R_LORD_FEAST, "Natal", "Branca")
        nth = {26: "Segundo", 27: "Terceiro", 28: "Quarto", 29: "Quinto", 30: "Sexto", 31: "Sétimo"}[day.day]
        key = f"dec-{day.day}" if day.day >= 29 else "dec-29"
        return out(key, f"{nth} dia na Oitava do Natal", "Dia na Oitava do Natal",
                   R_PRIV_FERIA, "Natal", "Branca")

    # ---- Tempo Comum (segunda parte) e solenidades do Senhor
    n = (day - E).days
    if n == 56:
        return out("trindade", "Santíssima Trindade", "Solenidade", R_SOLEMNITY, "Tempo Comum", "Branca")
    if n == 60:
        return out("corpus-christi", "Santíssimo Corpo e Sangue de Cristo", "Solenidade",
                   R_SOLEMNITY, "Tempo Comum", "Branca")
    if n == 68:
        return out("sagrado-coracao", "Sagrado Coração de Jesus", "Solenidade", R_SOLEMNITY,
                   "Tempo Comum", "Branca")
    king = adv - timedelta(days=7)
    if day == king:
        return out("cristo-rei", "Nosso Senhor Jesus Cristo, Rei do Universo", "Solenidade",
                   R_SOLEMNITY, "Tempo Comum", "Branca")
    week = 34 - (king - sunday_of(day)).days // 7
    return _ordinary(out, week, wd)


def _ordinary(out, week, wd):
    if wd == 0:
        return out(f"tc-{week}", f"{week}º Domingo do Tempo Comum", "Domingo do Tempo Comum",
                   R_SUNDAY, "Tempo Comum", "Verde")
    return out(f"tc-{week}", f"{week}ª Semana do Tempo Comum", "Dia de semana", R_FERIA,
               "Tempo Comum", "Verde")


# ------------------------------------------------------------------ Santos
def _kind(name):
    n = _plain(name)
    if any(w in n for w in ("virgem maria", "imaculad", "assuncao", "visitacao")):
        return "mary"
    if any(w in n for w in ("apresentacao do senhor", "transfiguracao", "exaltacao", "anunciacao",
                            "dedicacao", "todos os santos", "fieis defuntos")):
        return "lord"
    if "apostol" in n or "evangelista" in n:
        return "apostle"
    if any(w in n for w in ("martir", "martirio", "inocentes")):
        return "martyr"
    if "doutor" in n:
        return "doctor"
    if any(w in n for w in ("virgem", "religios", "abade", "eremita", "monge")):
        return "religious"
    if any(w in n for w in ("bispo", "papa", "presbitero", "diacono")):
        return "pastor"
    return "saint"


def _saint_color(name, key=""):
    n = _plain(name)
    if key == "11-02":
        return "Preta ou roxa"
    if any(w in n for w in ("conversao de sao paulo", "catedra", "sao joao, apostolo")):
        return "Branca"
    if any(w in n for w in ("martir", "martirio", "inocentes", "apostol", "evangelista",
                            "exaltacao da santa cruz")):
        return "Vermelha"
    return "Branca"


def short_name(name):
    """Nome do santo sem os títulos (", bispo e doutor da Igreja")."""
    return re.split(r",\s*(?=[a-zà-ú])", name)[0].strip()


def _is_blocked(day):
    """Dias que não admitem solenidade transferida/ocorrente."""
    t = temporal(day)
    return t["rank"] <= R_HIGH or t["rank"] == R_SOLEMNITY


@lru_cache(maxsize=16)
def sanctoral_year(year):
    """Santos do ano civil, já com as transferências do Brasil e das Normas."""
    result = {}

    def put(day, entry):
        result.setdefault(day, []).append(entry)

    E = easter(year)
    for key, entries in SANCTORAL.items():
        month, dom = (int(x) for x in key.split("-"))
        if key in ("01-01", "12-25"):
            continue                      # já tratados no Próprio do Tempo
        nominal = date(year, month, dom)
        for entry in entries:
            item = dict(entry, key=key)
            day = nominal
            if key == "06-29":            # domingo entre 28/6 e 4/7
                first = date(year, 6, 28)
                day = first + timedelta(days=(6 - first.weekday()) % 7)
            elif key == "08-15" and nominal.weekday() != 6:
                day = nominal + timedelta(days=(6 - nominal.weekday()) % 7)
            elif key == "11-01":
                if nominal.weekday() not in (5, 6):       # 2/11 no domingo → sábado, dia 1º
                    day = nominal + timedelta(days=(6 - nominal.weekday()) % 7)
            elif item["rank"] == "S":
                t = temporal(nominal)
                in_holy_week_or_octave = -7 <= (nominal - E).days <= 7
                if in_holy_week_or_octave:
                    if key == "03-19":    # São José: sábado antes do Domingo de Ramos
                        day = E - timedelta(days=8)
                    else:                 # Anunciação: segunda após o 2º Domingo da Páscoa
                        day = E + timedelta(days=8)
                elif t["rank"] <= R_HIGH and nominal.weekday() == 6:
                    day = nominal + timedelta(days=1)
                elif t["rank"] == R_SOLEMNITY:
                    # Coincidência com solenidade do Senhor (ex.: São João Batista
                    # e Sagrado Coração): celebra-se na véspera.
                    day = nominal - timedelta(days=1)
                while _is_blocked(day) and day != nominal:
                    day += timedelta(days=1)
            if day != nominal:
                item["transferred_from"] = nominal
            put(day, item)

    # Memórias móveis
    put(E + timedelta(days=50), dict(MOVABLE["mae-da-igreja"], rank="M", key="mae-da-igreja"))
    put(E + timedelta(days=69), dict(MOVABLE["imaculado-coracao"], rank="M", key="imaculado-coracao"))
    return result


def _sanct_rank(item):
    if item["rank"] in ("S", "C"):
        return R_SOLEMNITY
    if item["rank"] == "F":
        return R_LORD_FEAST if item["key"] in LORD_FEASTS else R_FEAST
    return R_MEMORIAL if item["rank"] == "M" else R_OPTIONAL


# ------------------------------------------------------------------ Dia
def liturgical_day(day):
    """Resolve o dia: o que se celebra, grau, cor, ciclo e páginas do Missal."""
    t = temporal(day)
    saints = list(sanctoral_year(day.year).get(day, []))
    strong = t["season"] in ("Advento", "Natal", "Quaresma", "Páscoa", "Tríduo Pascal")
    is_sunday = day.weekday() == 6

    obligatory = [s for s in saints if s["rank"] == "M"]
    if len(obligatory) > 1:
        # Duas memórias obrigatórias no mesmo dia: a de Maria, Mãe da Igreja,
        # prevalece; nos demais casos ambas se tornam facultativas.
        for s in obligatory:
            if not any(o["key"] == "mae-da-igreja" for o in obligatory) or s["key"] != "mae-da-igreja":
                s["rank"] = "O"
                s["demoted"] = True

    winner = min(saints, key=_sanct_rank) if saints else None
    celebrated = None
    if winner and winner["rank"] != "O" and _sanct_rank(winner) < t["rank"]:
        celebrated = winner

    info = {"date": day, "temporal_key": t["key"], "season": t["season"],
            "special": t.get("special"), "is_sunday": is_sunday}
    others = [s for s in saints if s is not celebrated]

    if celebrated:
        rank = celebrated["rank"]
        info.update(
            celebration=celebrated["name"],
            grade={"S": "Solenidade", "F": "Festa", "M": "Memória", "C": "Comemoração"}[rank],
            color=_saint_color(celebrated["name"], celebrated["key"]),
            page=celebrated.get("page", "—"),
            saint=short_name(celebrated["name"]) if rank != "C" else "—",
            kind=_kind(celebrated["name"]), sanct=celebrated, source="santos",
        )
        if celebrated.get("vigil"):
            info["vigil_page"] = celebrated["vigil"]
        if celebrated.get("transferred_from"):
            info["note"] = (f"{info['grade']} transferida de "
                            f"{celebrated['transferred_from']:%d/%m} conforme o calendário litúrgico do Brasil.")
        else:
            info["note"] = f"{info['grade']} celebrada neste dia."
        if rank == "M" and strong:
            # Nos tempos fortes mantém-se o prefácio do tempo (uso do site).
            info["seasonal_preface"] = True
    else:
        entry = TEMPORAL[t["key"]]
        info.update(celebration=t["name"], grade=t["grade"], color=t["color"],
                    page=entry["page"], saint=t.get("saint", "—"), kind="temporal",
                    source="tempo", hint=t.get("hint"))
        if t.get("vigil"):
            info["vigil_page"] = TEMPORAL[t["vigil"]]["page"]
        optional = [s for s in others if s["rank"] in ("O", "M")]
        saturday_mary = (day.weekday() == 5 and t["rank"] == R_FERIA
                         and t["season"] == "Tempo Comum")
        names = [short_name(s["name"]) for s in optional]
        if t["rank"] == R_FERIA and (optional or saturday_mary):
            if saturday_mary:
                names.append("Santa Maria no Sábado")
            info["grade"] = "Memória facultativa"
            info["saint"] = "; ".join(names)
            info["note"] = "; ".join(names) + " — memória facultativa"
        elif optional:
            kept = [s for s in optional if s["rank"] == "M" or s.get("demoted")]
            if t["rank"] == R_PRIV_FERIA and optional:
                info["saint"] = "; ".join(names)
                info["note"] = ("; ".join(names) + " — neste dia pode-se fazer apenas a comemoração "
                                "(Coleta do santo), mantendo a Missa do dia.")
            elif kept:
                info["saint"] = "; ".join(short_name(s["name"]) for s in kept) + " — memória omitida"
                info["note"] = info["saint"] + " neste ano."
            else:
                info["saint"] = "; ".join(names)
                info["note"] = "; ".join(names) + " — memória facultativa omitida neste dia."
        feasts = [s for s in others if s["rank"] in ("F",)]
        if feasts:
            info["saint"] = "; ".join(short_name(s["name"]) for s in feasts) + " — festa omitida"
            info["note"] = info["saint"] + " neste ano."
        if not info.get("note"):
            info["note"] = (info["celebration"] + ".") if info["grade"] != "Dia de semana" \
                else f"Dia de semana — {t['season']}: Missa do dia."

    # Ciclo de leituras: domingos e solenidades do Senhor seguem o ano A/B/C;
    # dias de semana do Tempo Comum, o ano I/II; os demais têm leituras próprias.
    abc_keys = ("trindade", "corpus-christi", "sagrado-coracao", "batismo", "sagrada-familia",
                "vigilia-pascal")
    if is_sunday or (info["source"] == "tempo" and t["key"] in abc_keys):
        info["cycle"] = sunday_cycle(day)
    elif t["season"] == "Tempo Comum" and info["grade"] != "Solenidade":
        info["cycle"] = weekday_cycle(day)
    else:
        info["cycle"] = "—"

    info["preface"] = _preface(info, t)
    info["blessing"] = _blessing(info, t)
    info["solemn"] = is_sunday or info["grade"] in ("Solenidade", "Festa", "Comemoração") \
        or t["rank"] <= R_HIGH
    return info


def _ordinary_preface(page):
    title, subtitle = PREFACE_BY_PAGE[str(page)]
    return {"page": str(page), "title": title, "subtitle": subtitle}


SEASON_PREFACE = {"Advento": 451, "Natal": 455, "Quaresma": 459, "Páscoa": 466}
KIND_PREFACE = {"martyr": 502, "doctor": 506, "religious": 508, "pastor": 504, "mary": 493,
                "apostle": 498, "saint": 500, "lord": 500}


def _preface(info, t):
    if info["source"] == "santos" and not info.get("seasonal_preface"):
        own = info["sanct"].get("preface")
        if own:
            return dict(own)
        return _ordinary_preface(KIND_PREFACE[info["kind"]])
    if info["source"] == "santos":          # memória em tempo forte
        if t["season"] == "Advento" and info["date"].day >= 17 and info["date"].month == 12:
            return _ordinary_preface(453)
        return _ordinary_preface(SEASON_PREFACE.get(t["season"], 509))
    own = TEMPORAL[t["key"]].get("preface")
    if own:
        return dict(own)
    if t["season"] == "Tempo Comum":
        return _ordinary_preface(477 if info["is_sunday"] else 509)
    if t["key"] == "paixao":
        return None
    return _ordinary_preface(SEASON_PREFACE.get(t["season"], 509))


SEASON_BLESSING = {"Advento": ("578", "Bênção Solene — Advento"),
                   "Natal": ("579", "Bênção Solene — Natal"),
                   "Páscoa": ("581", "Bênção Solene — Tempo Pascal"),
                   "Tempo Comum": ("585", "Bênção Solene — Tempo Comum VI")}
BLESSING_TITLE = {"578": "Bênção Solene — Advento", "579": "Bênção Solene — Natal",
                  "580": "Bênção Solene — Epifania do Senhor",
                  "581": "Bênção Solene — Tempo Pascal", "582": "Bênção Solene — Espírito Santo",
                  "585": "Bênção Solene — Bem-aventurada Virgem Maria",
                  "586": "Bênção Solene — Santos Apóstolos",
                  "587": "Bênção Solene — Na festa de um Santo",
                  "588": "Bênção Solene — Dedicação de Igreja"}


def _blessing(info, t):
    """(página, título, é própria do formulário?)"""
    if info["source"] == "santos":
        sanct = info["sanct"]
        ref = sanct.get("blessing")
        if ref:
            page = str(ref["page"])
            title = BLESSING_TITLE.get(page, "Bênção Solene")
            if sanct["key"] == "06-29":
                title = "Bênção Solene — Santos Pedro e Paulo"
            elif sanct["key"] == "11-01":
                title = "Bênção Solene — Todos os Santos"
            elif sanct["key"] == "11-02":
                title = "Bênção Solene — Celebração pelos Fiéis Defuntos"
            return {"page": page, "title": title, "from_missal": True}
        if info["kind"] == "mary":
            return {"page": "585", "title": BLESSING_TITLE["585"]}
        if info["kind"] == "apostle":
            return {"page": "586", "title": BLESSING_TITLE["586"]}
        if t["season"] == "Quaresma":
            return {"page": "589", "title": "Bênção: Oração sobre o povo — à escolha", "people": True}
        if t["season"] in ("Advento", "Natal", "Páscoa") and info["grade"] == "Memória":
            page, title = SEASON_BLESSING[t["season"]]
            return {"page": page, "title": title}
        return {"page": "587", "title": BLESSING_TITLE["587"]}
    entry = TEMPORAL[t["key"]]
    if entry.get("blessing"):
        ref = entry["blessing"]
        page = str(ref["page"])
        if ref.get("own"):
            return {"page": page, "title": "Bênção Solene — própria desta celebração", "from_missal": True}
        title = BLESSING_TITLE.get(page, "Bênção Solene")
        if t["key"] == "ramos":
            title = "Bênção Solene — Paixão do Senhor"
        return {"page": page, "title": title, "from_missal": True}
    if entry.get("povo"):
        return {"page": str(entry["povo"]["page"]), "title": "Bênção: Oração sobre o povo — própria do dia",
                "people": True, "from_missal": True}
    if t["season"] in ("Quaresma",):
        return {"page": "589", "title": "Bênção: Oração sobre o povo — à escolha", "people": True}
    if t["season"] == "Tríduo Pascal":
        return None
    page, title = SEASON_BLESSING.get(t["season"], SEASON_BLESSING["Tempo Comum"])
    return {"page": page, "title": title}


# ------------------------------------------------------------------ Registro do site
OE_RESPONSE = "“Anunciamos, Senhor, a vossa morte e proclamamos a vossa ressurreição. Vinde, Senhor Jesus!”"


def _tape_preface(pref):
    if not pref:
        return {"n": 3, "page": "—", "title": "Prefácio — não há neste dia", "notIndicated": True,
                "details": [["Indicação", "Nesta celebração não há Prefácio."]]}
    if pref["title"] == "Prefácio próprio":
        return {"n": 3, "page": pref["page"], "title": "Prefácio próprio — " + pref["subtitle"],
                "details": [["Uso", "No próprio formulário da celebração"]]}
    details = ([["Título", pref["subtitle"]]] if pref.get("subtitle") else []) + [["Uso", "Sugestão"]]
    return {"n": 3, "page": pref["page"], "title": pref["title"], "details": details, "suggestion": True}


def _tape_oe(solemn):
    page, title = ("545", "Oração Eucarística III") if solemn else ("536", "Oração Eucarística II")
    return {"n": 4, "page": page, "title": title, "suggestion": True,
            "details": [["Aclamação", "Mistério da fé! • sugestão"], ["Resposta", OE_RESPONSE],
                        ["Uso", "Sugestão enquanto não houver indicação do folheto"]]}


def _tape_blessing(bless):
    if not bless:
        return {"n": 5, "page": "—", "title": "Bênção Solene — não há neste dia", "notIndicated": True,
                "details": [["Indicação", "Nesta celebração não há bênção solene."]]}
    if bless.get("from_missal"):
        use = "Indicada no próprio formulário do Missal (facultativa)"
    else:
        use = "Sugestão adequada ao tempo ou à celebração"
    return {"n": 5, "page": bless["page"], "title": bless["title"], "details": [["Uso", use]],
            "suggestion": True}


def build_entry(day):
    """Registro completo do dia no formato usado em data.js."""
    info = liturgical_day(day)
    special = info.get("special") if info["source"] == "tempo" else None
    label = f"{DAYS[day.weekday()]} • {day:%d/%m/%Y}"
    season = info["season"]
    color = info["color"]
    cycle = info["cycle"]
    subtitle = (f"{cycle} • {season}" if cycle != "—" else season)
    page = info["page"]
    details2 = [["Formulário", "Missa do dia"]]
    if info.get("hint"):
        details2.append(["Atenção", info["hint"]])
    if info.get("vigil_page"):
        details2 = [["Missa do dia", f"pág. {page}"],
                    ["Missa da Vigília", f"pág. {info['vigil_page']} — na tarde/noite da véspera"]]
    tape2 = {"n": 2, "page": page, "title": info["celebration"], "details": details2}
    tape3 = _tape_preface(info["preface"])
    tape4 = _tape_oe(info["solemn"])
    tape5 = _tape_blessing(info["blessing"])
    note = info.get("note") or ""
    celebration = info["celebration"]
    grade = info["grade"]

    if special == "dec24":
        tape2 = {"n": 2, "page": "124 / 126", "title": "24 de dezembro — manhã / Vigília do Natal",
                 "details": [["Manhã", "pág. 124"], ["Tarde/noite", "Missa da Vigília do Natal — pág. 126"]]}
        tape3 = {"n": 3, "page": "453 / 455", "title": "Prefácio do Advento II / Prefácio do Natal do Senhor I",
                 "details": [["Manhã", "Prefácio do Advento II — pág. 453"],
                             ["Vigília do Natal", "Prefácio do Natal do Senhor I — pág. 455"],
                             ["Uso", "Escolher conforme a Missa celebrada; confirmar no folheto."]],
                 "suggestion": True}
        tape4 = _tape_oe(True)
        tape5 = {"n": 5, "page": "578 / 579", "title": "Bênção Solene — Advento / Natal",
                 "details": [["Manhã", "Bênção do Advento — pág. 578 (sugestão)"],
                             ["Vigília", "Bênção do Natal — pág. 579 (sugestão)"]], "suggestion": True}
        subtitle = "Advento • véspera do Natal"
        note = ("Manhã: Missa do dia 24, Advento, cor roxa. Tarde/noite: Vigília de Natal, cor branca. "
                "Escolher o prefácio e a bênção adequados à celebração.")
    elif special == "natal":
        tape2 = {"n": 2, "page": "128 / 130 / 132", "title": "Natal do Senhor",
                 "details": [["Missas de 25/12", "Missa da Noite — p. 128; Missa da Aurora — p. 130; Missa do Dia — p. 132."],
                             ["Vigília de 24/12", "A Missa da Vigília (p. 126) deve ser selecionada no dia 24/12."],
                             ["Escolha", "Usar o formulário correspondente à hora e ao tipo de celebração."]]}
        tape5 = {"n": 5, "page": "579", "title": "Bênção Solene — Natal",
                 "details": [["Uso", "Sugestão adequada ao tempo ou à celebração"]], "suggestion": True}
        note = "Solenidade celebrada neste dia."
    elif special == "ceia":
        tape2["details"] = [["Formulário", "Missa vespertina da Ceia do Senhor"],
                            ["Missa do Crisma", "Pela manhã, na catedral — pág. 232 (onde for celebrada)"],
                            ["Lava-pés", "Depois da homilia, onde houver"]]
        tape5 = {"n": 5, "page": "—", "title": "Bênção Solene — não há neste dia", "notIndicated": True,
                 "details": [["Indicação", "A Missa termina com a transladação do Santíssimo Sacramento, sem bênção final."]]}
        note = "Missa vespertina da Ceia do Senhor. Diz-se o Glória; não há bênção final."
    elif special == "paixao":
        tape1_override = True
        tape2["details"] = [["Celebração", "Celebração da Paixão do Senhor (não há Missa neste dia)"],
                            ["Partes", "Liturgia da Palavra, Adoração da Cruz e Sagrada Comunhão"]]
        tape4 = {"n": 4, "page": "—", "title": "Oração Eucarística — não há neste dia", "notIndicated": True,
                 "details": [["Indicação", "Neste dia não se celebra a Eucaristia; distribui-se a Comunhão consagrada na véspera."]]}
        tape5 = {"n": 5, "page": "—", "title": "Bênção Solene — não há neste dia", "notIndicated": True,
                 "details": [["Indicação", "A celebração termina com a oração sobre o povo, no próprio formulário."]]}
        note = "Não há Missa: Celebração da Paixão do Senhor. Sem ritos iniciais (entrada em silêncio e prostração)."
    elif special == "vigilia":
        tape2["details"] = [["Formulário", "Vigília Pascal na Noite Santa"],
                            ["Durante o dia", "No Sábado Santo não há Missa; a Vigília é celebrada à noite."]]
        note = "Não há Missa durante o dia. À noite: Vigília Pascal (bênção do fogo, Precônio, leituras, liturgia batismal e eucarística)."

    if special in ("paixao", "vigilia"):
        reason = ("Entrada em silêncio e prostração; não há saudação nem ato penitencial."
                  if special == "paixao" else
                  "A Vigília começa com a bênção do fogo e a preparação do círio; não há ato penitencial.")
        tape1 = {"n": 1, "page": "—", "title": "Ritos Iniciais — não há neste dia", "notIndicated": True,
                 "details": [["Indicação", reason]]}
    else:
        from ritos_texts import SAUDACOES, ATO_PENITENCIAL
        tape1 = {"n": 1, "page": "430", "title": "Ritos Iniciais",
                 "details": [["Saudação A • sugestão", SAUDACOES["A"]],
                             ["Ato Penitencial — Segunda fórmula, 2ª opção • sugestão",
                              ATO_PENITENCIAL["Segunda fórmula, 2ª opção"]]],
                 "suggestion": True}

    return {
        "label": label, "celebration": celebration, "subtitle": subtitle,
        "saint": info.get("saint") or "—", "grade": grade, "season": season,
        "color": color, "colorHex": COLOR_HEX.get(color, "#3b6f50"),
        "note": note, "liturgicalNote": note,
        "source": "Separação pelo Missal Romano • sugestões onde não houver folheto",
        "cycle": cycle,
        "tapes": [tape1, tape2, tape3, tape4, tape5],
        "generated": "calendario-perpetuo",
    }
