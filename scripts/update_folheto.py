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

def load_status():
    if not STATUS_FILE.exists():
        return {}
    raw = STATUS_FILE.read_text(encoding="utf-8")
    m = re.search(r"window\.MISSAL_STATUS\s*=\s*(\{.*\})\s*;\s*$", raw, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}

def save_leaflet_status(key, urls):
    """Salva o folheto semanal escolhido sem apagar o status diário."""
    status = load_status()
    status["sundayLeafletDate"] = key

    desktop = str(urls.get("desktop") or urls.get("generic") or urls.get("mobile") or "")
    mobile = str(urls.get("mobile") or urls.get("generic") or urls.get("desktop") or "")

    if desktop:
        status["sundayLeafletDesktopUrl"] = desktop
    if mobile:
        status["sundayLeafletMobileUrl"] = mobile

    preferred = mobile or desktop
    if preferred:
        status["sundayLeafletUrl"] = preferred

    STATUS_FILE.write_text(
        "window.MISSAL_STATUS = " + json.dumps(status, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8"
    )

def leaflet_variant(url):
    name = norm(url.rsplit("/", 1)[-1])
    if any(x in name for x in ["versao-celular", "versao celular", "celular", "mobile"]):
        return "mobile"
    if any(x in name for x in ["prova-final", "prova final", "final"]):
        return "desktop"
    return "generic"

def target_sunday(today=None):
    today = today or datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    return today + timedelta(days=(6 - today.weekday()) % 7)

def choose_week_leaflet(discovered):
    """
    Regra semanal:
    - usa o folheto do domingo que encerra a semana, se já estiver publicado;
    - enquanto ele não existir, mantém o domingo anterior mais recente;
    - após o domingo passar, esse mesmo folheto vira o fallback até o próximo sair.
    """
    target = target_sunday()
    eligible = []
    for key in discovered:
        try:
            dt = date.fromisoformat(key)
        except Exception:
            continue
        if dt <= target:
            eligible.append(dt)

    if not eligible:
        return None, None

    chosen = target if target in eligible else max(eligible)
    key = chosen.isoformat()
    return key, discovered.get(key)

def candidate_months():
    # Busca o mês atual, o anterior e os próximos dois meses; isso cobre folhetos
    # publicados com antecedência e arquivos colocados no mês anterior.
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
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
        details = fita1.setdefault("details", [])

        def apply_identification(prefix, detected_label):
            nonlocal changed
            if not detected_label:
                return
            row = next(
                (item for item in details
                 if isinstance(item, list) and len(item) >= 2
                 and str(item[0]).startswith(prefix)), None
            )
            if row is None:
                return

            previous = str(row[0]).split(" • sugestão")[0].strip()
            previous_text = str(row[1]).strip()
            only_reference = (
                not previous_text or
                "Consultar o texto integral no Missal Romano" in previous_text or
                previous_text.endswith(("...", "…"))
            )
            exact = previous == detected_label
            formula_only = (
                prefix == "Ato Penitencial —" and
                detected_label in (
                    "Ato Penitencial — Primeira fórmula",
                    "Ato Penitencial — Segunda fórmula",
                    "Ato Penitencial — Terceira fórmula"
                ) and previous.startswith(detected_label)
            )
            if not (exact or formula_only or only_reference):
                label = "Conferência necessária — " + (
                    "Saudação" if prefix == "Saudação " else "Ato Penitencial"
                )
                warning = (
                    f"Folheto indica {detected_label}; o texto existente "
                    "precisa ser conferido no Missal antes de substituir."
                )
                existing = next(
                    (d for d in details if isinstance(d, list) and len(d) >= 2
                     and d[0] == label), None
                )
                if existing is None:
                    details.append([label, warning])
                    changed = True
                elif existing[1] != warning:
                    existing[1] = warning
                    changed = True
                return

            # Sem opção detectada, não inventar 1ª, 2ª ou 3ª opção.
            chosen = previous if formula_only and not exact else detected_label
            # Uma referência ao Missal não é transcrição integral da oração.
            new_label = chosen + (" • sugestão" if only_reference else "")
            if row[0] != new_label:
                row[0] = new_label
                changed = True

        apply_identification("Saudação ", f"Saudação {saud}" if saud else None)
        apply_identification("Ato Penitencial —", f"Ato Penitencial — {ato}" if ato else None)

        required = [
            next((d for d in details if isinstance(d, list) and len(d) >= 2
                  and str(d[0]).startswith(prefix)), None)
            for prefix in ("Saudação ", "Ato Penitencial —")
        ]
        if (saud and ato and all(required)
                and all(" • sugestão" not in str(d[0]) for d in required)
                and not any(str(d[0]).startswith("Conferência necessária")
                            for d in details if isinstance(d, list) and d)):
            if fita1.pop("suggestion", None) is not None:
                changed = True

    fita2 = next((x for x in entry["tapes"] if x["n"] == 2), None)
    if fita2 and missal_page and not str(fita2.get("page") or "").strip():
        # A primeira referência no PDF pode não ser a página da Missa.
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
    discovered_leaflets = {}
    seen = set()
    for url in pdfs:
        if url in seen:
            continue
        seen.add(url)
        try:
            text = pdf_text(url)
            key = parse_date(text)
            if not key:
                continue

            dt = date.fromisoformat(key)
            variant = leaflet_variant(url)

            # Guarda todos os folhetos datados encontrados, inclusive de dias
            # de semana. O mapa dominical usado como fallback continua separado.
            if dt.weekday() == 6:
                bucket = discovered_leaflets.setdefault(key, {})
                if variant not in bucket:
                    bucket[variant] = url

            print(f"[folheto] {key} ({variant}): {url}")

            # Se a data já existe no site, salva o link direto do folheto.
            # Isso permite que um folheto especial de segunda a sábado tenha
            # prioridade somente no próprio dia.
            if key not in data:
                continue

            entry = data[key]
            url_field = (
                "folhetoMobileUrl" if variant == "mobile"
                else "folhetoDesktopUrl" if variant == "desktop"
                else "folhetoUrl"
            )
            if entry.get(url_field) != url:
                entry[url_field] = url
                changed_any = True

            # Quando houver folheto oficial para qualquer dia cadastrado,
            # aplica também as escolhas reconhecidas à separação desse dia.
            if update_entry(entry, text, url):
                changed_any = True
        except Exception as e:
            print(f"[aviso] Falha em {url}: {e}")

    if changed_any:
        save_data(data)
        print("Dados atualizados.")
    else:
        print("Nenhuma alteração necessária nos dados.")

    leaflet_key, leaflet_urls = choose_week_leaflet(discovered_leaflets)
    if leaflet_key and leaflet_urls:
        save_leaflet_status(leaflet_key, leaflet_urls)
        target = target_sunday().isoformat()
        if leaflet_key == target:
            print(f"[folheto-semanal] Folheto da semana disponível: {leaflet_key}")
        else:
            print(f"[folheto-semanal] Folheto da semana ainda indisponível; mantendo {leaflet_key}.")
    else:
        print("[folheto-semanal] Nenhum folheto válido encontrado; status anterior preservado.")

    print("Atualização de dados concluída. Aguardando validação antes da publicação.")

if __name__ == "__main__":
    main()
