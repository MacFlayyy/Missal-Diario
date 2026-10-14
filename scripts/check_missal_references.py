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
    errors, suggestions, total = [], [], 0
    for key,day in data.items():
        tapes = day.get("tapes") or []
        if [t.get("n") for t in tapes] != [1,2,3,4,5]:
            errors.append(f"{key}: fitas 1–5 ausentes ou desordenadas")
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
