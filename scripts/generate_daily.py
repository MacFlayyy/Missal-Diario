#!/usr/bin/env python3
"""Geração diária sob demanda, sem depender de calendário anual pré-preenchido.

Prioridade: primeiro o folheto da Arquidiocese (outro script), depois uma
referência brasileira de liturgia diária que reproduz as informações CNBB.
A fonte consultada aqui fornece data, celebração, tempo e cor, mas NÃO o
número de página da terceira edição do Missal Romano: nunca inventá-lo.
"""
from __future__ import annotations
from datetime import date, timedelta, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import re
import unicodedata
from html.parser import HTMLParser
from html import unescape
from urllib.request import urlopen, Request
from ritos_texts import SAUDACOES, ATO_PENITENCIAL, suggested_blessing, suggested_preface

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data.js"
TZ = ZoneInfo("America/Sao_Paulo")
SOURCE = "https://carmosaodomingos.com.br/liturgia"
MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro")
DAYS = ("Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
        "Sexta-feira", "Sábado", "Domingo")

def simplify(value):
    normalized = unicodedata.normalize("NFD", str(value))
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").lower()

def daily_url(day):
    return f"{SOURCE}?data={day.isoformat()}&mes={day:%Y-%m}"

def liturgical_year(day):
    # Ano A começou no Advento/2025, B no Advento/2026 e C no Advento/2027.
    advent = date(day.year, 12, 25)
    advent -= timedelta(days=(advent.weekday()+1) % 7 + 21)
    active_year = day.year if day >= advent else day.year-1
    return "Ano " + ("A", "B", "C")[(active_year-2025) % 3]


class PublicLiturgyParser(HTMLParser):
    """Lê o texto de página sem bibliotecas externas ou execução de scripts."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments=[]
        self.skip=0

    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript"):
            self.skip+=1

    def handle_endtag(self,tag):
        if tag in ("script","style","noscript"):
            self.skip=max(0,self.skip-1)

    def handle_data(self,value):
        if not self.skip:
            value=re.sub(r"\s+"," ",value).strip()
            if value:
                self.fragments.append(unescape(value))


def read_liturgical_day(day, fetch=None):
    if fetch is None:
        def fetch(url):
            request=Request(url,headers={
                "User-Agent":"Mozilla/5.0 (MissalDiario/1.1; data liturgica publica)"})
            with urlopen(request,timeout=24) as response:
                return response.read().decode("utf-8",errors="replace")
    html = fetch(daily_url(day))
    if len(html) < 400:
        raise RuntimeError("Fonte diária sem dados suficientes")
    parser=PublicLiturgyParser()
    parser.feed(html)
    lines=parser.fragments
    date_label = f"{day.day:02d} de {MONTHS[day.month-1]} de {day.year}"
    page_normalized = simplify(" ".join(lines))
    if simplify(date_label) not in page_normalized:
        raise RuntimeError(f"Fonte litúrgica não confirmou a data {day}")
    try:
        idx = lines.index("Memória/Celebração")
        celebration = lines[idx+1].strip()
        tidx = lines.index("Tempo")
        liturgical_period = lines[tidx+1].strip()
    except (ValueError, IndexError) as exc:
        raise RuntimeError("Fonte litúrgica sem celebração/tempo identificável") from exc
    color_match = re.search(
        r"Cor litúrgica:\s*(Branco|Branca|Verde|Vermelho|Vermelha|Roxo|Roxa|Róseo|Rósea)",
        " ".join(lines[:90]), re.I)
    if not color_match:
        raise RuntimeError(f"Cor litúrgica de {day} não pôde ser verificada")
    variants={"branco":"Branca","branca":"Branca","verde":"Verde",
              "vermelho":"Vermelha","vermelha":"Vermelha",
              "roxo":"Roxa","roxa":"Roxa","roseo":"Roxa (ou rósea)","rosea":"Roxa (ou rósea)"}
    color = variants[simplify(color_match.group(1))]
    season_map={"natal":"Natal","advento":"Advento","quaresma":"Quaresma",
                "pascoa":"Páscoa","pascal":"Páscoa","comum":"Tempo Comum"}
    season = next((value for key,value in season_map.items()
                   if key in simplify(liturgical_period)),None)
    if not season:
        raise RuntimeError(f"Tempo litúrgico não reconhecido: {liturgical_period}")
    if not celebration or len(celebration) > 160:
        raise RuntimeError("Celebração ausente ou inválida")
    weekday = DAYS[day.weekday()]
    raw = simplify(celebration)
    generic = bool(re.match(r"^(segunda|terca|quarta|quinta|sexta|sabado|domingo)[- ,]",raw))
    if generic:
        celebration = f"{weekday} • {liturgical_period}"
        grade = "Domingo" if day.weekday()==6 else "Dia de semana"
        saint = "—"
    else:
        grade = next((label for key,label in (
            ("solenidade","Solenidade"),("festa","Festa"),
            ("memoria","Memória")) if key in raw),None)
        if grade:
            celebration = re.sub(r",?\s*(Solenidade|Festa|Memória)(?:,.*)?$", "", celebration, flags=re.I).strip()
        elif day.weekday()==6:
            grade = "Domingo"
        else:
            grade = "Dia de semana"
        saint = celebration if grade in ("Memória", "Festa", "Solenidade") else "—"
    if grade=="Domingo" and day.weekday()==6 and "domingo" not in simplify(celebration):
        celebration = f"{celebration} — Domingo"
    return {
        "day":day, "celebration":celebration, "grade":grade,
        "season":season, "color":color, "saint":saint, "reference":daily_url(day),
        # O ciclo dominical (A/B/C) aplica-se somente aos domingos;
        # festas/solenidades feriais não transformam o dia em domingo.
        "cycle":liturgical_year(day) if day.weekday()==6
                 else ("Ano I" if day.year%2 else "Ano II")
    }

def new_entry(info):
    day=info["day"]; week=day.weekday()
    month=day.month
    date_label=f"{DAYS[week]} • {day:%d/%m/%Y}"
    color_hex={"Branca":"#d0ad67","Verde":"#3b6f50","Vermelha":"#9f2d2d",
               "Roxa":"#6b4f7b","Roxa (ou rósea)":"#6b4f7b"}.get(info["color"],"#c8a96a")
    entry={
        "label":date_label, "celebration":info["celebration"],
        "subtitle":f"{info['season']} • {info['grade']}", "saint":info["saint"],
        "grade":info["grade"], "season":info["season"], "color":info["color"],
        "colorHex":color_hex, "cycle":info["cycle"],
        "liturgicalNote":"Dia confirmado em fonte litúrgica brasileira; páginas e opções não indicadas são sugestões ou requerem conferência.",
        "note":"Gerado sob demanda. A página própria da Missa deve ser conferida no Missal Romano CNBB 2023; não é fornecida pela fonte online.",
        "source":"Calendário litúrgico brasileiro • dados do dia verificados; marcações não confirmadas são sugestões",
        "dailySourceUrl":info["reference"], "dailySourceVerified":True,
        "tapes":[
            {"n":1,"page":"430","title":"Ritos Iniciais","suggestion":True,
             "details":[["Saudação A • sugestão",SAUDACOES["A"]],
                        ["Ato Penitencial — Segunda fórmula, 2ª opção • sugestão",
                         ATO_PENITENCIAL["Segunda fórmula, 2ª opção"]]]},
            {"n":2,"page":"—","title":info["celebration"],"pageUnverified":True,
             "details":[["Página","A conferir no Missal Romano CNBB 2023; fonte consultada não apresenta a página do formulário."],
                        ["Celebração","Nome, tempo e cor verificados na fonte litúrgica diária."]]},
            {"n":3,"page":"—","title":"Prefácio — a conferir","suggestion":True,
             "details":[["Uso","Sugestão enquanto não houver folheto."]]},
            {"n":4,"page":"536","title":"Oração Eucarística II","suggestion":True,
             "details":[["Aclamação","Mistério da fé! • sugestão"],
                        ["Resposta","Anunciamos, Senhor, a vossa morte e proclamamos a vossa ressurreição. Vinde, Senhor Jesus!"]]},
            {"n":5,"page":"—","title":"Bênção Solene — a conferir","suggestion":True,
             "details":[["Uso","Sugestão enquanto não houver folheto."]]},
        ]
    }
    entry["tapes"][2]["page"],entry["tapes"][2]["title"]=suggested_preface(entry)
    entry["tapes"][4]["page"],entry["tapes"][4]["title"]=suggested_blessing(entry)
    entry["quick"]=" → ".join("?" if t.get("pageUnverified") else t["page"] for t in entry["tapes"])
    return entry

def ensure_dates(data, day, fetch=None):
    """Gera apenas o dia atual e a antecipação dominical do sábado."""
    needed=[day]
    if day.weekday()==5:
        needed.append(day+timedelta(days=1))
    added=[]
    for date_key in needed:
        key=date_key.isoformat()
        if key in data:
            continue
        try:
            info=read_liturgical_day(date_key,fetch=fetch)
        except Exception as exc:
            if date_key == day:
                # A celebração do próprio dia é obrigatória; jamais
                # declarar sucesso sem confirmar seus dados litúrgicos.
                raise
            # A consulta antecipada do domingo pode estar indisponível
            # na madrugada do sábado. Registrar e tentar novamente no
            # próximo agendamento sem bloquear o sábado já verificado.
            print(f"::warning title=Prévia dominical pendente::{key}: {exc}")
            continue
        data[key]=new_entry(info)
        added.append(key)
    return added

def main():
    day=datetime.now(TZ).date()
    text=DATA_FILE.read_text(encoding="utf-8")
    match=re.search(r"window\.MISSAL_DATA\s*=\s*(\{.*\})\s*;\s*$",text,re.S)
    if not match:
        raise RuntimeError("data.js inválido")
    data=json.loads(match.group(1))
    added=ensure_dates(data,day)
    if added:
        ordered=dict(sorted(data.items()))
        DATA_FILE.write_text("window.MISSAL_DATA = "+
            json.dumps(ordered,ensure_ascii=False,indent=2)+";\n",encoding="utf-8")
    print("[geração diária] "+(", ".join(added) if added else "datas já cadastradas"))
    if day.isoformat() not in data:
        raise RuntimeError("Data de hoje não foi gerada; publicação bloqueada")

if __name__=="__main__":
    main()
