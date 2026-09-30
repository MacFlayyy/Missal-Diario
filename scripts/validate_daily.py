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
import json
import re

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data.js"
STATUS_FILE = ROOT / "status.js"
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

def save_status(key):
    now = datetime.now(TZ)
    payload = {
        "availableThrough": key,
        "lastSuccessfulUpdateAt": now.isoformat(timespec="seconds"),
        "timezone": "America/Sao_Paulo",
        "validation": "reviewed-and-corrected",
    }
    STATUS_FILE.write_text(
        "window.MISSAL_STATUS = " +
        json.dumps(payload, ensure_ascii=False, indent=2) +
        ";\n",
        encoding="utf-8"
    )

def is_valid_page(page):
    p = str(page or "").strip()
    return bool(re.fullmatch(r"\d{2,4}(?:\s*[-/]\s*\d{2,4})*", p))

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
        entry["celebration"] = "Missa do dia"
        fixes.append("Celebração preenchida.")
    if not str(entry.get("grade","")).strip():
        entry["grade"] = "Dia de semana"
        fixes.append("Grau litúrgico preenchido.")
    if not str(entry.get("season","")).strip():
        entry["season"] = "Tempo Comum"
        fixes.append("Tempo litúrgico preenchido.")
    if entry.get("color") not in VALID_COLORS:
        entry["color"] = "Verde" if entry["season"] == "Tempo Comum" else "Roxa"
        fixes.append("Cor litúrgica corrigida.")
    if not str(entry.get("liturgicalNote","")).strip():
        entry["liturgicalNote"] = "Separação revisada automaticamente antes da publicação."
        fixes.append("Observação litúrgica preenchida.")

    tapes = entry.setdefault("tapes", [])
    by_n = {t.get("n"): t for t in tapes if isinstance(t, dict)}

    # Cria fitas que eventualmente tenham desaparecido.
    defaults = {
        1: {"n":1,"page":"430","title":"Ritos Iniciais","details":[]},
        2: {"n":2,"page":"—","title":"Missa do dia","details":[["Formulário","Missa do dia"]]},
        3: {"n":3,"page":"509","title":"Prefácio Comum I","details":[],"suggestion":True},
        4: {"n":4,"page":"536","title":"Oração Eucarística II","details":[],"suggestion":True},
        5: {"n":5,"page":"585","title":"Bênção Solene — Tempo Comum VI","details":[],"suggestion":True},
    }
    for n in range(1,6):
        if n not in by_n:
            tapes.append(defaults[n].copy())
            by_n[n] = tapes[-1]
            fixes.append(f"Fita {n} recriada.")

    tapes.sort(key=lambda x: x.get("n", 99))

    # Fita 1 — nomenclatura usada no site:
    # "Saudação A" e "Ato Penitencial — Segunda fórmula, 2ª opção".
    f1 = by_n[1]
    f1["page"] = "430"
    f1["title"] = "Ritos Iniciais"

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

    if saud_row is None or not re.search(r"Saudação\\s+[A-H]", str(saud_row[0]), re.I):
        saud_row = ["Saudação A • sugestão", "“A graça de nosso Senhor Jesus Cristo...”"]
        fixes.append("Saudação corrigida para Saudação A como sugestão.")

    if ato_row is None or not re.search(
        r"(Primeira|Segunda|Terceira)\\s+fórmula,\\s*\\dª\\s+opção",
        str(ato_row[0]),
        re.I
    ):
        ato_row = [
            "Ato Penitencial — Segunda fórmula, 2ª opção • sugestão",
            "“No início desta celebração eucarística...”"
        ]
        fixes.append("Ato Penitencial corrigido para fórmula/opção válidas.")

    f1["details"] = [saud_row, ato_row]

    # Fita 2 — página da Missa do dia deve existir no cadastro.
    # Não inventamos página. Se já houver uma página válida, preservamos.
    f2 = by_n[2]
    if not str(f2.get("title","")).strip():
        f2["title"] = entry.get("celebration","Missa do dia")
        fixes.append("Título da Fita 2 corrigido.")
    if not is_valid_page(f2.get("page")):
        # Tenta recuperar de um campo conhecido no próprio título/detalhes.
        text = json.dumps(f2, ensure_ascii=False)
        m = re.search(r"\b(\d{2,4})\b", text)
        if m:
            f2["page"] = m.group(1)
            fixes.append("Página da Fita 2 recuperada do próprio cadastro.")
        else:
            # Último recurso: mantém explícito que precisa do formulário já cadastrado,
            # mas não cria número falso.
            f2["page"] = "430"
            f2["title"] = f"{entry.get('celebration','Missa do dia')} — revisar formulário"
            f2["details"] = [["Aviso","Página do formulário não foi encontrada; usar o Missal do dia antes da celebração."]]
            fixes.append("Fita 2 recebeu fallback seguro por ausência de página cadastrada.")

    # Fita 3
    f3 = by_n[3]
    if not is_valid_page(f3.get("page")) or "prefácio" not in str(f3.get("title","")).lower():
        p, title, sub = infer_preface(entry)
        f3["page"] = p
        f3["title"] = title
        f3["details"] = [["Título",sub],["Uso","Sugestão automática revisada"]]
        f3["suggestion"] = True
        fixes.append("Prefácio corrigido automaticamente.")

    # Fita 4
    f4 = by_n[4]
    if str(f4.get("page","")) not in {"523","536","545","554","564"} or "oração eucarística" not in str(f4.get("title","")).lower():
        solemn = any(x in str(entry.get("grade","")).lower() for x in ["domingo","festa","solenidade"])
        f4["page"] = "545" if solemn else "536"
        f4["title"] = "Oração Eucarística III" if solemn else "Oração Eucarística II"
        f4["suggestion"] = True
        fixes.append("Oração Eucarística corrigida automaticamente.")
    ensure_detail(f4, "Aclamação", "Mistério da fé! • sugestão")

    # Fita 5
    f5 = by_n[5]
    if not is_valid_page(f5.get("page")) or "bênção" not in str(f5.get("title","")).lower():
        p, title = infer_blessing(entry)
        f5["page"] = p
        f5["title"] = title
        f5["details"] = [["Uso","Sugestão automática revisada"]]
        f5["suggestion"] = True
        fixes.append("Bênção corrigida automaticamente.")

    # Reconstrói separação rápida SEMPRE, evitando inconsistência.
    entry["quick"] = " → ".join(
        str(t.get("page","")).strip()
        for t in sorted(tapes, key=lambda x: x.get("n",99))
        if str(t.get("page","")).strip()
    )

    if fixes:
        note = "Revisado automaticamente às 05:00. " + " ".join(fixes)
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

    # Se a data atual estiver cadastrada, corrige e publica.
    if today_key in data:
        fixes = repair_entry(data[today_key])
        save_data(data)
        save_status(today_key)

        if fixes:
            print("Correções automáticas realizadas:")
            for item in fixes:
                print(f"- {item}")
        else:
            print("Nenhuma correção necessária.")

        print(f"Data {today_key} revisada e liberada para publicação.")
        return

    # O calendário do projeto atual vai até 31/12/2026.
    # Se chegar uma data ainda não cadastrada, não inventa uma Missa nova.
    # Mantém a última data válida publicada, mas o workflow segue vivo.
    existing = sorted(data)
    last = existing[-1] if existing else ""
    print(f"Data {today_key} ainda não está cadastrada. Última data disponível: {last}.")
    print("Nenhum dado litúrgico foi inventado.")

if __name__ == "__main__":
    main()
