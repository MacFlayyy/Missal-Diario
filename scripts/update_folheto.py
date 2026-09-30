#!/usr/bin/env python3
"""
Atualizador automático do Missal Diário.

- Procura PDFs do "O Povo de Deus" nos diretórios públicos de uploads da
  Arquidiocese de Brasília.
- Extrai o texto do folheto.
- Identifica a data e, para domingos já cadastrados em data.js, troca as
  sugestões pelas escolhas encontradas no folheto quando for possível
  reconhecê-las com segurança.
- Não usa API paga nem chave secreta.
"""

from __future__ import annotations
from pathlib import Path
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from io import BytesIO
from urllib.parse import urljoin
import json, re, unicodedata

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data.js"
STATUS_FILE = ROOT / "status.js"
BASE = "https://arqbrasilia.com.br"
UA = {"User-Agent": "Mozilla/5.0 (MissalDiario/1.0; parish liturgy helper)"}

MONTHS = {
    "janeiro":1, "fevereiro":2, "marco":3, "março":3, "abril":4,
    "maio":5, "junho":6, "julho":7, "agosto":8, "setembro":9,
    "outubro":10, "novembro":11, "dezembro":12,
}

def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("–","-").replace("—","-")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

SAUDACOES = [
    ("A", "a graca de nosso senhor jesus cristo, o amor do pai e a comunhao do espirito santo"),
    ("B", "a graca e a paz de deus, nosso pai, e de jesus cristo, nosso senhor"),
    ("C", "o senhor, que encaminha os nossos coracoes para o amor de deus e a constancia de cristo"),
    ("D", "o deus da esperanca, que nos cumula de toda alegria e paz em nossa fe"),
    ("E", "a vos, irmaos, paz e fe da parte de deus, o pai, e do senhor jesus cristo"),
    ("F", "irmaos eleitos segundo a presciencia de deus pai"),
    ("G", "a graca e a paz daquele que e, que era e que vem"),
    ("H", "o senhor esteja convosco"),
]

ATO_INTROS = [
    ("Primeira fórmula — 1ª opção", "irmaos e irmas, reconhecamos os nossos pecados, para celebrarmos dignamente os santos misterios"),
    ("Primeira fórmula — 2ª opção", "o senhor jesus, que nos convida a mesa da palavra e da eucaristia"),
    ("Primeira fórmula — 3ª opção", "no dia em que celebramos a vitoria de cristo sobre o pecado e a morte"),
    ("Segunda fórmula — 1ª opção", "irmaos e irmas, reconhecamos os nossos pecados, para celebrarmos dignamente os santos misterios"),
    ("Segunda fórmula — 2ª opção", "no inicio desta celebracao eucaristica, pecamos a conversao do coracao"),
    ("Segunda fórmula — 3ª opção", "de coracao contrito e humilde, aproximemo-nos do deus justo e santo"),
    ("Terceira fórmula — 1ª opção", "irmaos e irmas, reconhecamos os nossos pecados, para celebrarmos dignamente os santos misterios"),
    ("Terceira fórmula — 2ª opção", "em jesus cristo, o justo, que intercede por nos e nos reconcilia com o pai"),
    ("Terceira fórmula — 3ª opção", "o senhor disse: quem dentre vos estiver sem pecado"),
]

PREFACIOS = [
    ("Prefácio dos Domingos do Tempo Comum I", "474", "o misterio pascal e o povo de deus"),
    ("Prefácio dos Domingos do Tempo Comum II", "475", "o misterio da salvacao"),
    ("Prefácio dos Domingos do Tempo Comum III", "476", "a salvacao dos homens, pelo homem"),
    ("Prefácio dos Domingos do Tempo Comum IV", "477", "a historia da salvacao"),
    ("Prefácio dos Domingos do Tempo Comum V", "478", "a criacao"),
    ("Prefácio do Advento I", "451", "as duas vindas de cristo"),
    ("Prefácio do Advento II", "453", "a dupla espera de cristo"),
    ("Prefácio dos Santos Mártires I", "502", "o testemunho do martirio"),
    ("Prefácio dos Santos Mártires II", "503", "as maravilhas de deus na vitoria dos martires"),
    ("Prefácio dos Santos Doutores da Igreja I", "506", "os doutores da igreja, reflexo da sabedoria"),
    ("Prefácio das Santas Virgens e Religiosos", "508", "o sinal da vida consagrada a deus"),
]

def load_data():
    raw = DATA_FILE.read_text(encoding="utf-8")
    m = re.search(r"window\.MISSAL_DATA\s*=\s*(\{.*\})\s*;\s*$", raw, re.S)
    if not m:
        raise RuntimeError("data.js inválido")
    return json.loads(m.group(1))

def save_data(data):
    DATA_FILE.write_text(
        "window.MISSAL_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8"
    )

def save_status():
    """Libera o dia somente depois que esta execução terminou com sucesso."""
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    payload = {
        "availableThrough": now.strftime("%Y-%m-%d"),
        "lastSuccessfulUpdateAt": now.isoformat(timespec="seconds"),
        "timezone": "America/Sao_Paulo",
    }
    STATUS_FILE.write_text(
        "window.MISSAL_STATUS = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8"
    )

def candidate_months():
    # Busca o mês atual, o anterior e os próximos dois meses; isso cobre folhetos
    # publicados com antecedência e arquivos colocados no mês anterior.
    today = date.today()
    months = set()
    for offset in range(-1, 3):
        y, m = today.year, today.month + offset
        while m < 1: y, m = y-1, m+12
        while m > 12: y, m = y+1, m-12
        months.add((y,m))
    # Também cobre todo o período cadastrado de 2026.
    for m in range(9, 13):
        months.add((2026,m))
    return sorted(months)

def list_pdfs(year, month):
    url = f"{BASE}/wp-content/uploads/{year}/{month:02d}/"
    r = requests.get(url, headers=UA, timeout=25)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        name = href.rsplit("/",1)[-1]
        n = norm(name)
        if href.lower().endswith(".pdf") and (
            "povo" in n and "deus" in n or
            re.search(r"(^|[-_])opd([-_]|$)", n)
        ):
            out.append(href)
    return sorted(set(out))

def pdf_text(url):
    r = requests.get(url, headers=UA, timeout=40)
    r.raise_for_status()
    reader = PdfReader(BytesIO(r.content))
    # O necessário costuma estar nas primeiras páginas, mas OE/bênção podem estar depois.
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    return text

def parse_date(text):
    t = norm(text[:5000])
    m = re.search(r"brasilia,?\s*(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d{2})", t)
    if not m:
        return None
    day, month_name, year = m.groups()
    month = MONTHS.get(month_name)
    if not month:
        return None
    return f"{int(year):04d}-{month:02d}-{int(day):02d}"

def section(text, heading, next_headings):
    nt = norm(text)
    h = norm(heading)
    pos = nt.find(h)
    if pos < 0:
        return ""
    ends = []
    for nh in next_headings:
        p = nt.find(norm(nh), pos + len(h))
        if p >= 0:
            ends.append(p)
    end = min(ends) if ends else min(len(nt), pos + 3500)
    return nt[pos:end]

def classify_saudacao(text):
    sec = section(text, "SAUDAÇÃO INICIAL", ["ATO PENITENCIAL", "COLETA", "HINO DO GLÓRIA"])
    for label, sig in SAUDACOES:
        if sig in sec:
            return label
    return None

def classify_ato(text):
    sec = section(text, "ATO PENITENCIAL", ["HINO DO GLÓRIA", "COLETA"])
    # Distinguish formula by body first.
    if "confesso a deus todo-poderoso" in sec:
        formula = "Primeira fórmula"
    elif "tende compaixao de nos, senhor" in sec and "manifestai, senhor, a vossa misericordia" in sec:
        formula = "Segunda fórmula"
    elif ("senhor, que" in sec and "cristo, que" in sec) or "kyrie" in sec:
        formula = "Terceira fórmula"
    else:
        formula = None

    # Identify the introduction option. Same generic invitation appears in all three formulas.
    intro_option = None
    specific = [
        ("1ª opção", "irmaos e irmas, reconhecamos os nossos pecados"),
        ("2ª opção", "o senhor jesus, que nos convida a mesa da palavra e da eucaristia"),
        ("3ª opção", "no dia em que celebramos a vitoria de cristo sobre o pecado e a morte"),
    ] if formula == "Primeira fórmula" else [
        ("1ª opção", "irmaos e irmas, reconhecamos os nossos pecados"),
        ("2ª opção", "no inicio desta celebracao eucaristica, pecamos a conversao do coracao"),
        ("3ª opção", "de coracao contrito e humilde, aproximemo-nos do deus justo e santo"),
    ] if formula == "Segunda fórmula" else [
        ("1ª opção", "irmaos e irmas, reconhecamos os nossos pecados"),
        ("2ª opção", "em jesus cristo, o justo, que intercede por nos e nos reconcilia com o pai"),
        ("3ª opção", "o senhor disse: quem dentre vos estiver sem pecado"),
    ] if formula == "Terceira fórmula" else []

    for opt, sig in specific:
        if sig in sec:
            intro_option = opt
            # Prefer specific option over generic shared 1st option.
            if opt != "1ª opção":
                break

    if formula and intro_option:
        return f"{formula}, {intro_option}"
    return formula

def detect_prefacio(text):
    n = norm(text)
    for title, page, sig in PREFACIOS:
        if norm(title) in n or sig in n:
            return title, page
    return None

def detect_eucharistic(text):
    n = norm(text)
    for roman, page in [("v","564"),("iv","554"),("iii","545"),("ii","536"),("i","523")]:
        patterns = [
            f"oracao eucaristica {roman}",
            f"oração eucarística {roman}",
        ]
        if any(norm(p) in n for p in patterns):
            return f"Oração Eucarística {roman.upper()}", page
    return None

def detect_acclamation(text):
    n = norm(text)
    choices = [
        ("Mistério da fé para a salvação do mundo!", "misterio da fe para a salvacao do mundo"),
        ("Mistério da fé e do amor!", "misterio da fe e do amor"),
        ("Tudo isto é mistério da fé!", "tudo isto e misterio da fe"),
        ("Mistério da fé!", "misterio da fe"),
    ]
    for label, sig in choices:
        if sig in n:
            return label
    return None

def response_for_acclamation(label):
    n = norm(label or "")
    if "misterio da fe para a salvacao do mundo" in n:
        return "“Salvador do mundo, salvai-nos, vós que nos libertastes pela cruz e ressurreição.”"
    if "misterio da fe e do amor" in n:
        return "“Todas as vezes que comemos deste pão e bebemos deste cálice, anunciamos, Senhor, a vossa morte, enquanto esperamos a vossa vinda!”"
    if "misterio da fe" in n:
        return "“Anunciamos, Senhor, a vossa morte e proclamamos a vossa ressurreição. Vinde, Senhor Jesus!”"
    return None

def detect_missal_page(text):
    n = norm(text[:6000])
    m = re.search(r"(?:missal romano|mr\.?)\s*,?\s*p(?:ag)?\.?\s*(\d{2,4})(?:\s*[-–]\s*(\d{2,4}))?", n)
    if not m:
        return None
    return m.group(1) if not m.group(2) else f"{m.group(1)}-{m.group(2)}"

def update_entry(entry, text, url):
    changed = False

    saud = classify_saudacao(text)
    ato = classify_ato(text)
    missal_page = detect_missal_page(text)
    pref = detect_prefacio(text)
    oe = detect_eucharistic(text)
    acl = detect_acclamation(text)

    fita1 = next((x for x in entry["tapes"] if x["n"] == 1), None)
    if fita1 and (saud or ato):
        old_details = fita1.get("details", [])
        saud_prayer = next((r[1] for r in old_details if isinstance(r,list) and len(r)>=2 and str(r[0]).startswith("Saudação ")), "“A graça de nosso Senhor Jesus Cristo...”")
        ato_prayer = next((r[1] for r in old_details if isinstance(r,list) and len(r)>=2 and str(r[0]).startswith("Ato Penitencial —")), "“No início desta celebração eucarística...”")

        # O folheto oficial substitui as sugestões quando a informação foi reconhecida.
        if saud:
            saud_label = f"Saudação {saud}"
        else:
            old_saud = next((r[0] for r in old_details if isinstance(r,list) and len(r)>=2 and str(r[0]).startswith("Saudação ")), "Saudação A • sugestão")
            saud_label = old_saud

        if ato:
            ato_label = f"Ato Penitencial — {ato}"
        else:
            old_ato = next((r[0] for r in old_details if isinstance(r,list) and len(r)>=2 and str(r[0]).startswith("Ato Penitencial —")), "Ato Penitencial — Segunda fórmula, 2ª opção • sugestão")
            ato_label = old_ato

        fita1["details"] = [[saud_label, saud_prayer], [ato_label, ato_prayer]]
        if saud and ato:
            fita1.pop("suggestion", None)
        changed = True

    fita2 = next((x for x in entry["tapes"] if x["n"] == 2), None)
    if fita2 and missal_page:
        fita2["page"] = missal_page
        changed = True

    fita3 = next((x for x in entry["tapes"] if x["n"] == 3), None)
    if fita3 and pref:
        title, page = pref
        fita3["page"] = page
        fita3["title"] = title
        fita3["details"] = [["Indicação","Identificado no folheto oficial"]]
        fita3.pop("suggestion", None)
        changed = True

    fita4 = next((x for x in entry["tapes"] if x["n"] == 4), None)
    if fita4 and oe:
        title, page = oe
        fita4["page"] = page
        fita4["title"] = title
        rows = fita4.get("details", [])
        # remove old "Uso" suggestion row
        rows = [r for r in rows if r[0] != "Uso"]
        if acl:
            found = False
            for r in rows:
                if r[0] == "Aclamação":
                    r[1] = acl
                    found = True
            if not found:
                rows.append(["Aclamação", acl])

            response = response_for_acclamation(acl)
            if response:
                response_found = False
                for r in rows:
                    if r[0] == "Resposta":
                        r[1] = response
                        response_found = True
                if not response_found:
                    rows.append(["Resposta", response])

        fita4["details"] = rows
        fita4.pop("suggestion", None)
        changed = True

    n = norm(text)
    fita5 = next((x for x in entry["tapes"] if x["n"] == 5), None)
    if fita5 and "bencao solene" in n:
        fita5["details"] = [["Indicação","O folheto traz bênção solene"]]
        fita5.pop("suggestion", None)
        changed = True

    if changed:
        entry["source"] = "Atualizado pelo folheto oficial O Povo de Deus"
        entry["note"] = "Folheto oficial encontrado e aplicado automaticamente. As partes não identificadas permanecem conforme a pré-separação do Missal."
        entry["folhetoUrl"] = url
        entry["quick"] = " → ".join(
            str(t["page"]) for t in entry["tapes"] if str(t.get("page","—")) not in {"—",""}
        )
    return changed

def main():
    data = load_data()
    pdfs = []
    for y,m in candidate_months():
        try:
            pdfs.extend(list_pdfs(y,m))
        except Exception as e:
            print(f"[aviso] Falha ao listar {y}/{m:02d}: {e}")

    changed_any = False
    seen = set()
    for url in pdfs:
        if url in seen:
            continue
        seen.add(url)
        try:
            text = pdf_text(url)
            key = parse_date(text)
            if not key or key not in data:
                continue
            # O Povo de Deus é usado principalmente nos domingos.
            dt = date.fromisoformat(key)
            if dt.weekday() != 6:
                continue
            print(f"[folheto] {key}: {url}")
            if update_entry(data[key], text, url):
                changed_any = True
        except Exception as e:
            print(f"[aviso] Falha em {url}: {e}")

    if changed_any:
        save_data(data)
        print("Dados atualizados.")
    else:
        print("Nenhuma alteração necessária nos dados.")

    print("Atualização de dados concluída. Aguardando validação antes da publicação.")

if __name__ == "__main__":
    main()
