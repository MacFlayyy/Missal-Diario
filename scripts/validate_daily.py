#!/usr/bin/env python3
"""
Revisão e correção automática do Missal Diário antes da publicação das 05:00.

Fluxo:
1) lê os dados atualizados;
2) confere o dia atual;
3) corrige automaticamente campos ausentes/inconsistentes com regras conservadoras;
4) reconstrói a separação rápida;
5) libera a data e permite a publicação.

A prioridade é:
- usar o que veio do folheto oficial quando identificado;
- preservar dados já válidos do Missal;
- quando faltar uma escolha discricionária, inserir uma sugestão segura e marcada como tal;
- nunca inventar uma página específica da Missa do dia quando ela não estiver previamente cadastrada.
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from ritos_texts import apply_rite_suggestions, fill_folheto_gaps
import json
import re

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data.js"
STATUS_FILE = ROOT / "status.js"
SEED_FILE = ROOT / "calendar_seed.json"
TZ = ZoneInfo("America/Sao_Paulo")

VALID_COLORS = {
    "Verde", "Branca", "Vermelha", "Roxa",
    "Roxa (ou rósea)", "Preta ou roxa",
    "Roxa de manhã / Branca à tarde"
}

def load_js_object(path: Path, var_name: str):
    raw = path.read_text(encoding="utf-8")
    m = re.search(
        rf"{re.escape(var_name)}\s*=\s*(\{{.*\}})\s*;\s*$",
        raw,
        re.S
    )
    if not m:
        raise RuntimeError(f"Não foi possível ler {path.name}")
    return json.loads(m.group(1))

def save_data(data):
    DATA_FILE.write_text(
        "window.MISSAL_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8"
    )

def save_status(key, data):
    now = datetime.now(TZ)

    # Preserva os dados do folheto dominical gravados por update_folheto.py.
    existing = {}
    if STATUS_FILE.exists():
        try:
            existing = load_js_object(STATUS_FILE, "window.MISSAL_STATUS")
        except Exception:
            existing = {}

    already_current = existing.get("availableThrough") == key
    last_update = (
        existing.get("lastSuccessfulUpdateAt")
        if already_current and existing.get("lastSuccessfulUpdateAt")
        else now.isoformat(timespec="seconds")
    )

    payload = {
        "availableThrough": key,
        "lastSuccessfulUpdateAt": last_update,
        "timezone": "America/Sao_Paulo",
        "validation": "reviewed-and-corrected",
    }

    # Aos sábados, deixa o domingo seguinte preparado para liberação
    # APENAS após 05:00, quando status do sábado já estiver publicado.
    # O front-end também verifica o horário e availableThrough.
    if now.weekday() == 5:
        from datetime import timedelta
        sunday_key = (now.date() + timedelta(days=1)).isoformat()
        sunday = data.get(sunday_key)
        tapes = sunday.get("tapes", []) if isinstance(sunday, dict) else []
        if (sunday and len(tapes) >= 5
                and "domingo" in (str(sunday.get("celebration",""))+" "+str(sunday.get("grade",""))).lower()
                and all(is_valid_page(t.get("page")) or (t.get("notIndicated") and t.get("page") == "—") for t in tapes[:5])):
            payload["sundayPreview"] = sunday_key

    # Avisa com antecedência quando o cadastro litúrgico futuro está acabando.
    # Nunca gera páginas do Missal por adivinhação.
    from datetime import date, timedelta
    if data:
        calendar_end = max(data.keys())
        payload["calendarDataThrough"] = calendar_end
        if date.fromisoformat(calendar_end) < now.date() + timedelta(days=30):
            payload["calendarWarning"] = (
                f"O calendário está cadastrado somente até {calendar_end}. "
                "Novas datas precisam ser preparadas e revisadas para continuar a publicação."
            )
            print("::warning title=Calendário litúrgico próximo do fim::" + payload["calendarWarning"])

    for field in (
        "sundayLeafletDate",
        "sundayLeafletDesktopUrl",
        "sundayLeafletMobileUrl",
        "sundayLeafletUrl",
    ):
        value = existing.get(field)
        if value:
            payload[field] = value

    STATUS_FILE.write_text(
        "window.MISSAL_STATUS = " +
        json.dumps(payload, ensure_ascii=False, indent=2) +
        ";\n",
        encoding="utf-8"
    )

def is_valid_page(page):
    p = str(page or "").strip()
    return bool(re.fullmatch(r"\d{2,4}(?:\s*(?:[-–/]|\bou\b)\s*\d{2,4})*", p, re.I))

def ensure_detail(tape, label, value):
    details = tape.setdefault("details", [])
    for row in details:
        if isinstance(row, list) and len(row) >= 2 and row[0] == label:
            if not str(row[1]).strip() or str(row[1]).strip() == "—":
                row[1] = value
            return
    details.append([label, value])

def infer_preface(entry):
    season = str(entry.get("season",""))
    celebration = str(entry.get("celebration","")).lower()
    grade = str(entry.get("grade","")).lower()
    subtitle = str(entry.get("subtitle","")).lower()

    if "advento" in season.lower():
        if any(x in celebration for x in ["4º domingo", "17 de dezembro", "18 de dezembro",
                                           "19 de dezembro", "20 de dezembro", "21 de dezembro",
                                           "22 de dezembro", "23 de dezembro", "24 de dezembro"]):
            return "453", "Prefácio do Advento II", "A dupla espera de Cristo"
        return "451", "Prefácio do Advento I", "As duas vindas de Cristo"

    if "natal" in season.lower():
        return "455", "Prefácio do Natal do Senhor I", "Cristo luz"

    if "domingo" in grade or "domingo" in celebration or "ano a" in subtitle or "ano b" in subtitle:
        return "477", "Prefácio dos Domingos do Tempo Comum IV", "A história da salvação"

    if "mártir" in celebration or "martir" in celebration:
        return "502", "Prefácio dos Santos Mártires I", "O testemunho do martírio"

    if "doutor" in celebration:
        return "506", "Prefácio dos Santos Doutores da Igreja I", "Os Doutores da Igreja, reflexo da sabedoria"

    if "religios" in celebration or "virgem" in celebration:
        return "508", "Prefácio das Santas Virgens e Religiosos", "O sinal da vida consagrada a Deus"

    if "apóstol" in celebration or "apostol" in celebration or "evangelista" in celebration:
        return "498", "Prefácio dos Apóstolos I", "Os Apóstolos, pastores do povo de Deus"

    if "bispo" in celebration or "papa" in celebration or "presbítero" in celebration or "presbitero" in celebration:
        return "504", "Prefácio dos Santos Pastores I", "A presença dos Santos Pastores na Igreja"

    return "509", "Prefácio Comum I", "A restauração universal em Cristo"

def infer_blessing(entry):
    season = str(entry.get("season","")).lower()
    grade = str(entry.get("grade","")).lower()

    if "advento" in season:
        return "578", "Bênção Solene — Advento"
    if "natal" in season:
        return "579", "Bênção Solene — Natal"
    if any(x in grade for x in ["memória", "festa", "solenidade"]):
        return "587", "Bênção Solene — Na festa de um Santo"
    return "585", "Bênção Solene — Tempo Comum VI"

def repair_entry(entry):
    fixes = []

    # Cabeçalho: só corrige campos em branco usando dados coerentes e genéricos.
    if not str(entry.get("celebration","")).strip():
        raise RuntimeError("Celebração litúrgica não cadastrada.")
    if not str(entry.get("grade","")).strip():
        raise RuntimeError("Grau litúrgico não cadastrado.")
    if not str(entry.get("season","")).strip():
        raise RuntimeError("Tempo litúrgico não cadastrado.")
    if entry.get("color") not in VALID_COLORS:
        raise RuntimeError("Cor litúrgica não reconhecida; confirmar celebração.")
    if not str(entry.get("liturgicalNote","")).strip():
        entry["liturgicalNote"] = "Separação revisada automaticamente antes da publicação."
        fixes.append("Observação litúrgica preenchida.")

    tapes = entry.setdefault("tapes", [])
    by_n = {t.get("n"): t for t in tapes if isinstance(t, dict)}

    # Não inventa fitas ausentes: qualquer lacuna bloqueia a publicação.
    if len(tapes) != 5 or set(by_n) != {1, 2, 3, 4, 5}:
        raise RuntimeError("Cinco fitas numeradas de 1 a 5 devem estar cadastradas e revisadas.")
    tapes.sort(key=lambda x: x.get("n", 99))

    # Fita 1 — nomenclatura usada no site:
    # "Saudação A" e "Ato Penitencial — Segunda fórmula, 2ª opção".
    f1 = by_n[1]
    if not is_valid_page(f1.get("page")):
        raise RuntimeError("Página dos Ritos Iniciais ausente ou inválida.")
    if not str(f1.get("title","")).strip():
        raise RuntimeError("Título dos Ritos Iniciais ausente.")

    details = f1.get("details", [])
    saud_row = next(
        (r for r in details
         if isinstance(r, list) and len(r) >= 2 and str(r[0]).startswith("Saudação ")),
        None
    )
    ato_row = next(
        (r for r in details
         if isinstance(r, list) and len(r) >= 2 and str(r[0]).startswith("Ato Penitencial —")),
        None
    )

    if saud_row is None or not re.search(r"Saudação\s+[A-H]", str(saud_row[0]), re.I):
        raise RuntimeError("Saudação não identificada: conferir a fórmula indicada no folheto.")

    if ato_row is None or not re.search(
        r"(Primeira|Segunda|Terceira)\s+fórmula(?:,\s*\dª\s+opção)?",
        str(ato_row[0]),
        re.I
    ):
        if not (ato_row and "Invocações alternativas para os diversos tempos" in str(ato_row[0])):
            raise RuntimeError("Ato Penitencial não identificado: conferir fórmula ou invocações.")

    # Preserva outros detalhes e fórmulas oficiais existentes.
    # As referências abreviadas são corrigidas no cadastro, nunca inventadas aqui.
    f1["details"] = details

    # Fita 2 — página da Missa do dia deve existir no cadastro.
    # Não inventamos página. Se já houver uma página válida, preservamos.
    f2 = by_n[2]
    if not str(f2.get("title","")).strip():
        f2["title"] = entry.get("celebration","Missa do dia")
        fixes.append("Título da Fita 2 corrigido.")
    if not is_valid_page(f2.get("page")):
        raise RuntimeError("Página da Missa do dia inválida: cadastrar a página correta antes de publicar.")

    # Fita 3
    f3 = by_n[3]
    if not (is_valid_page(f3.get("page")) or (f3.get("notIndicated") and f3.get("page") == "—")) or "prefácio" not in str(f3.get("title","")).lower():
        raise RuntimeError("Prefácio ausente/inválido: conferir o Missal ou folheto antes de publicar.")

    # Fita 4
    f4 = by_n[4]
    if not (str(f4.get("page","")) in {"523","536","545","554","564","614"} or (f4.get("notIndicated") and f4.get("page") == "—")) or "oração eucarística" not in str(f4.get("title","")).lower():
        raise RuntimeError("Oração Eucarística ausente/inválida: conferir o folheto.")
    if not entry.get("officialLeafletApplied"):
        ensure_detail(f4, "Aclamação", "Mistério da fé! • sugestão")

    # Fita 5 — Bênção
    f5 = by_n[5]
    if not (is_valid_page(f5.get("page")) or (f5.get("notIndicated") and f5.get("page") == "—")) or "bênção" not in str(f5.get("title","")).lower():
        raise RuntimeError("Bênção ausente/inválida: conferir antes de publicar.")

    # Reconstrói separação rápida SEMPRE, evitando inconsistência.
    entry["quick"] = " → ".join(
        str(t.get("page","")).strip()
        for t in sorted(tapes, key=lambda x: x.get("n",99))
        if str(t.get("page","")).strip() and str(t.get("page","")).strip() != "—"
    )

    if fixes:
        note = "Conferência automática registrada. " + " ".join(fixes)
        entry["note"] = note
        entry["autoReview"] = {
            "reviewed": True,
            "corrections": fixes,
        }
    else:
        entry["autoReview"] = {
            "reviewed": True,
            "corrections": [],
        }

    return fixes

def main():
    now = datetime.now(TZ)
    today_key = now.strftime("%Y-%m-%d")
    data = load_js_object(DATA_FILE, "window.MISSAL_DATA")

    print(f"Revisando o Missal de {today_key} antes da publicação...")

    # Se a data sumiu de data.js, recupera automaticamente do calendário-base.
    if today_key not in data:
        if not SEED_FILE.exists():
            raise RuntimeError(
                f"Data {today_key} ausente e calendar_seed.json não existe. "
                "A publicação foi interrompida para não fingir sucesso."
            )

        seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
        if today_key not in seed:
            raise RuntimeError(
                f"Data {today_key} ausente em data.js e no calendário-base. "
                "A publicação foi interrompida para revisão."
            )

        data[today_key] = seed[today_key]
        print(f"Data {today_key} recuperada automaticamente do calendário-base.")

    apply_rite_suggestions(data[today_key])
    fill_folheto_gaps(data[today_key])
    fixes = repair_entry(data[today_key])
    save_data(data)
    save_status(today_key, data)

    if fixes:
        print("Correções automáticas realizadas:")
        for item in fixes:
            print(f"- {item}")
    else:
        print("Nenhuma correção necessária.")

    print(f"Data {today_key} revisada e liberada para publicação.")

if __name__ == "__main__":
    main()
