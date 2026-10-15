#!/usr/bin/env python3
"""Conferência independente de referências contra índice criado do PDF de 2023.

O índice é de metadados, não substitui a consulta litúrgica ao livro físico/PDF.
Se o PDF original estiver disponível localmente via MISSAL_ROMANO_PDF, confere
também SHA-256 integral e cada página registrada, sem publicá-lo no site.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = [
    "temporal_advento_natal",
    "temporal_comum",
    "ritos_iniciais",
    "prefacios_ordinario",
    "oracoes_eucaristicas",
    "bencaos_solenes",
    "proprio_santos_e_festas",
    "comuns",
]
BY_TAPE = {
    1: {"ritos_iniciais"},
    2: {"temporal_advento_natal", "temporal_comum", "proprio_santos_e_festas", "comuns"},
    3: {"prefacios_ordinario", "proprio_santos_e_festas", "oracoes_eucaristicas", "temporal_comum"},
    4: {"oracoes_eucaristicas"},
    5: {"bencaos_solenes"},
}
# Algumas páginas do Próprio são prefácios próprios; outras são só formulário.
OWN_PREFACES = {818, 828, 843, 852, 873}
SPECIAL_PREFACES = {426, 614}


def load_js(path, prefix):
    raw = path.read_text(encoding="utf-8")
    match = re.search(re.escape(prefix) + r"\s*=\s*(\{.*\})\s*;?\s*$", raw, flags=re.S)
    if not match:
        raise ValueError(f"Formato inválido em {path.name}")
    return json.loads(match.group(1))


def referenced_pages(value):
    value = str(value or "").strip()
    if value in ("", "—", "?"):
        return []
    # Aceita páginas alternativas (ex.: 126 / 128 / 130 / 132) sem
    # transformar indevidamente a referência em intervalo contínuo.
    parts = re.split(r"\s*(?:/|,|\bou\b|[–-])\s*", value, flags=re.I)
    if not all(re.fullmatch(r"\d{2,4}", x) for x in parts):
        raise ValueError("Expressão de página não reconhecida: " + value)
    return [int(x) for x in parts]


def check_index_and_data():
    idx = json.loads((ROOT / "missal-reference-index.json").read_text(encoding="utf-8"))
    data = load_js(ROOT / "data.js", "window.MISSAL_DATA")
    groups = {name:set(map(int,idx["categories"][name])) for name in CATEGORIES}
    registered = set().union(*groups.values())
    # Registro INDEPENDENTE por celebração conferido no PDF do Missal.
    # O índice anterior só impedia páginas inexistentes ou em seções erradas.
    date_map = json.loads(
        (ROOT / "missal-date-formulary-map.json").read_text(encoding="utf-8")
    )
    if date_map.get("reference_pdf_sha256") != idx.get("source_pdf_sha256"):
        raise SystemExit("Os dois índices do Missal usam PDFs de edições diferentes.")
    known_dates = date_map.get("entries", {})
    # As remissões facultativas são extraídas dos formulários reais do PDF
    # (ex.: 02/11, 28/10, 30/11 e 12/12), não dos valores atuais do data.js.
    rubric_file = ROOT / "missal-rubrics-verified.json"
    rubrics = json.loads(rubric_file.read_text(encoding="utf-8"))
    if rubrics.get("pdf_sha256") != idx.get("source_pdf_sha256"):
        raise SystemExit("O índice de rubricas não corresponde à edição do PDF.")
    blessing_rules = rubrics.get("blessings", {})
    # Conferências independentes baseadas na edição de 2023 (datas e rubricas).
    # Ao contrário do mapa histórico, estas constantes NÃO são geradas de data.js.
    VERIFIED_DATE_RUBRICS = {
        "2026-11-30": {"season": "Advento", "mass_pages": "865"},
        "2026-11-02": {"mass_pages": "846 / 847 / 848"},
        "2026-12-25": {"season": "Natal", "mass_pages": "128 / 130 / 132"},
    }
    errors, suggestions, total = [], [], 0
    unmatched_dates = []
    for key,day in data.items():
        tapes = day.get("tapes") or []
        verified = VERIFIED_DATE_RUBRICS.get(key)
        if verified:
            if "season" in verified and str(day.get("season","")).strip() != verified["season"]:
                errors.append(f"{key}: tempo litúrgico incompatível com a rubrica de 2023")
            if len(tapes) < 2 or str(tapes[1].get("page","")).strip() != verified["mass_pages"]:
                errors.append(f"{key}: opções de formulário divergentes das páginas do Missal 2023")
        expected = known_dates.get(key)
        if expected:
            actual_page = str(tapes[1].get("page","")).strip() if len(tapes) > 1 else ""
            registered_page = str(expected.get("missal_formulary_page","")).strip()
            if actual_page != registered_page:
                errors.append(
                    f"{key}: página da Missa {actual_page!r} diverge do PDF "
                    f"verificado para a celebração ({registered_page!r})"
                )
            # Os nomes de dias especiais podem mudar de abreviação, mas mudanças
            # litúrgicas devem ser observadas e revisadas separadamente.
            if str(day.get("celebration","")).strip() != str(expected.get("celebration","")).strip():
                errors.append(f"{key}: celebração diverge do cadastro específico do Missal")
        else:
            unmatched_dates.append(key)
            if len(tapes)>1 and not tapes[1].get("pageUnverified") and not day.get("officialLeafletApplied"):
                errors.append(
                    f"{key}: formulário tem página numérica sem vínculo verificado "
                    "ao PDF nem indicação de folheto oficial"
                )
        if [t.get("n") for t in tapes] != [1,2,3,4,5]:
            errors.append(f"{key}: fitas 1–5 ausentes ou desordenadas")
        specific = blessing_rules.get(key)
        if specific and len(tapes)>4 and not day.get("officialLeafletApplied"):
            blessing = tapes[4]
            expected_blessing = str(specific["blessing_page"])
            if str(blessing.get("page","")) != expected_blessing:
                errors.append(
                    f"{key}: bênção sugerida p. {blessing.get('page')} diverge "
                    f"da remissão facultativa do próprio (p. {expected_blessing})"
                )
            if not blessing.get("suggestion"):
                errors.append(f"{key}: uso facultativo não marcado como sugestão")
            own_page = int(str(tapes[1].get("page","")).split(" / ")[0])
            if own_page != int(specific["formulary_page"]):
                errors.append(f"{key}: própria celebração difere da página do índice de rubricas")
        for tape in tapes:
            n = tape.get("n")
            if n not in BY_TAPE:
                continue
            try:
                pages = referenced_pages(tape.get("page"))
            except ValueError as e:
                errors.append(f"{key}, fita {n}: {e}")
                continue
            if not pages:
                if not tape.get("pageUnverified") and not tape.get("notIndicated"):
                    errors.append(f"{key}, fita {n}: página vazia sem aviso de conferência")
                else:
                    suggestions.append((key,n))
                continue
            for page in pages:
                total += 1
                if page < 1 or page > idx["source_pdf_pages"]:
                    errors.append(f"{key}, fita {n}: página {page} inexistente no PDF")
                    continue
                if page not in registered:
                    if not tape.get("pageUnverified"):
                        errors.append(f"{key}, fita {n}: página {page} não consta do índice extraído do PDF")
                    continue
                if not any(page in groups[category] for category in BY_TAPE[n]):
                    errors.append(f"{key}, fita {n}: página {page} em seção incompatível com a fita")
                if n==3 and page in groups["proprio_santos_e_festas"] and page not in OWN_PREFACES:
                    errors.append(f"{key}: página {page} não inicia prefácio próprio no PDF")
                if n==3 and page in groups["temporal_comum"] and page not in SPECIAL_PREFACES:
                    errors.append(f"{key}: página {page} não inicia prefácio próprio")
                if n==3 and page in groups["oracoes_eucaristicas"] and page not in SPECIAL_PREFACES:
                    errors.append(f"{key}: oração eucarística não identificada como prefácio próprio")
        expected = " → ".join("?" if t.get("pageUnverified") else str(t.get("page","—")) for t in tapes)
        if day.get("quick") != expected:
            errors.append(f"{key}: separação rápida diverge das fitas")
    print(f"Conferência de índice: {len(data)} dias, {total} páginas referenciadas; "
          f"{len(suggestions)} fitas aguardam conferência.")
    print(f"Vínculos de celebração e página verificados: "
          f"{len(data)-len(unmatched_dates)}; "
          f"datas ainda sem vínculo próprio: {len(unmatched_dates)}.")
    print(f"Remissões de bênçãos verificadas no PDF: {len(blessing_rules)} datas.")
    if unmatched_dates:
        print("::warning::Datas sem vínculo próprio no índice do PDF: "
              + ", ".join(unmatched_dates[:8])
              + ("..." if len(unmatched_dates)>8 else ""))
    if errors:
        print("FALHAS DE REFERÊNCIA:")
        for e in errors: print(" -",e)
        raise SystemExit(1)
    print("Nenhuma referência fora do índice examinado, das seções ou da separação rápida.")
    return idx


def optional_pdf_integrity(idx):
    path = os.environ.get("MISSAL_ROMANO_PDF","").strip()
    if not path:
        print("PDF completo mantido fora do repositório público. "
              "Para verificar o arquivo original: MISSAL_ROMANO_PDF=/caminho/missal.pdf")
        return
    pdf = Path(path)
    if not pdf.is_file():
        raise SystemExit(f"PDF não encontrado: {pdf}")
    h=hashlib.sha256()
    with pdf.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):
            h.update(chunk)
    if h.hexdigest()!=idx["source_pdf_sha256"]:
        raise SystemExit("Atenção: PDF diferente da edição usada para montar o índice.")
    print("Integridade SHA-256 do PDF completo confirmada.")


def main():
    idx = check_index_and_data()
    optional_pdf_integrity(idx)


if __name__=="__main__":
    main()
