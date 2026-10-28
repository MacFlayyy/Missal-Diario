#!/usr/bin/env python3
"""Ritos Iniciais: exibir só a saudação ou a introdução do Ato Penitencial."""
SAUDACOES = {"A": "A graça de nosso Senhor Jesus Cristo, o amor do Pai e a comunhão do Espírito Santo estejam convosco."}
ATO_PENITENCIAL = {
    "Segunda fórmula, 2ª opção": "No início desta celebração eucarística, peçamos a conversão do coração, fonte de reconciliação e comunhão com Deus e com os irmãos e irmãs.",
    "Segunda fórmula, 3ª opção": "De coração contrito e humilde, aproximemo-nos do Deus justo e santo, para que tenha piedade de nós, pecadores.",
}

def apply_rite_suggestions(entry):
    fita = next((t for t in entry.get("tapes", []) if t.get("n") == 1), None)
    if fita is None:
        return False
    changed = False
    for row in fita.get("details", []):
        if not isinstance(row, list) or len(row) < 2:
            continue
        label = str(row[0]).split(" • ")[0].strip()
        if label.startswith("Saudação "):
            opening = SAUDACOES.get(label.removeprefix("Saudação "))
        elif label.startswith("Ato Penitencial — "):
            opening = ATO_PENITENCIAL.get(label.removeprefix("Ato Penitencial — "))
        else:
            continue
        if not opening:
            continue
        prior = str(row[1] or "")
        previously_generated = (
            "T.: Porque somos pecadores" in prior
            or "T.: Bendito seja Deus, que nos reuniu no amor de Cristo" in prior
            or "consultar o texto integral" in prior.lower()
            or "texto da oração não transcrito" in prior.lower()
        )
        if not previously_generated:
            continue
        row[1] = opening
        if " • sugestão" not in row[0]:
            row[0] = label + " • sugestão"
        changed = True
    if changed:
        fita["suggestion"] = True
        if "folheto oficial" in str(entry.get("source", "")).lower():
            entry["ritesPendingOfficial"] = True
    return changed

# Regra para os dias com folheto: quando uma parte não é indicada,
# sugerir uma alternativa liturgicamente adequada, identificada como tal.
def suggested_blessing(entry):
    celebration = str(entry.get("celebration", "")).lower()
    saint = str(entry.get("saint", "")).lower()
    season = str(entry.get("season", "")).lower()
    grade = str(entry.get("grade", "")).lower()
    if any(word in celebration + " " + saint for word in (
        "maria", "nossa senhora", "aparecida", "imaculada", "assunção"
    )):
        return "585", "Bênção Solene — Bem-aventurada Virgem Maria"
    if "advento" in season:
        return "578", "Bênção Solene — Advento"
    if "natal" in season:
        return "579", "Bênção Solene — Natal"
    if "tempo comum" in season and "domingo" in (celebration+" "+grade):
        return "585", "Bênção Solene — Tempo Comum VI"
    if any(word in grade for word in ("memória", "festa", "solenidade")):
        return "587", "Bênção Solene — Na festa de um Santo"
    return "585", "Bênção Solene — Tempo Comum VI"

def suggested_preface(entry):
    season = str(entry.get("season", "")).lower()
    sunday = "domingo" in (str(entry.get("celebration", "")) + " " + str(entry.get("grade", ""))).lower()
    if "advento" in season:
        return "451", "Prefácio do Advento I"
    if "natal" in season:
        return "455", "Prefácio do Natal do Senhor I"
    if "tempo comum" in season and sunday:
        return "477", "Prefácio dos Domingos do Tempo Comum IV"
    return "509", "Prefácio Comum I"

def fill_folheto_gaps(entry):
    """Não preencher lacunas de um folheto oficial com escolhas genéricas.

    Para dias com PDF oficial vinculado, só as partes marcadas como
    verifiedByFolheto podem ser apresentadas como oficiais. Partes já
    verificadas nunca são alteradas; o processamento repetido deve ser
    idempotente. O que o leitor automático não reconhecer fica pendente de
    conferência, sem página/texto inventado. Dias sem folheto continuam usando
    as sugestões existentes no cadastro-base, fora desta função.
    """
    if not any(entry.get(field) for field in (
        "folhetoDesktopUrl", "folhetoUrl", "folhetoMobileUrl"
    )):
        return False

    import json
    before = json.dumps(entry, sort_keys=True, ensure_ascii=False)
    tapes = {t.get("n"): t for t in entry.get("tapes", [])}
    verified_parts = entry.get("officialVerifiedParts")
    for number, title, detail in (
        (1, "Ritos Iniciais — a conferir no folheto",
         "Saudação e Ato Penitencial não identificados com segurança no folheto."),
        (3, "Prefácio — a conferir no folheto",
         "Prefácio não identificado com segurança no folheto."),
        (4, "Oração Eucarística — a conferir no folheto",
         "Oração Eucarística/aclamação não identificada com segurança no folheto."),
        (5, "Bênção Solene — conferir folheto",
         "Indicação de bênção solene ainda não confirmada na leitura do folheto."),
    ):
        tape = tapes.get(number)
        if not tape:
            continue

        # Uma bênção conferida diretamente no índice do Missal Romano é
        # válida mesmo quando o folheto do dia não a menciona. Não a apagar
        # apenas porque o folheto está incompleto ou não foi possível ler.
        if number == 5 and tape.get("suggestion"):
            try:
                rubric_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "missal-rubrics-verified.json"
                blessings = json.loads(rubric_path.read_text(encoding="utf-8")).get("blessings", {})
                title = str(tape.get("title", "")).strip()
                page = str(tape.get("page", "")).strip()
                if any(
                    str(rule.get("blessing_page", "")).strip() == page
                    and str(rule.get("blessing_title", "")).strip() == title
                    for rule in blessings.values()
                ):
                    continue
            except (OSError, ValueError, TypeError):
                pass

        # Quando há uma lista explícita de partes verificadas, ela prevalece
        # sobre flags antigas que possam ter ficado na fita após trocar de PDF.
        tape_verified = bool(tape.get("verifiedByFolheto"))
        if isinstance(verified_parts, list):
            tape_verified = tape_verified and number in verified_parts
        if tape_verified:
            continue
        tape.pop("verifiedByFolheto", None)

        # Se o leitor identificou explicitamente que a bênção não está indicada,
        # manter essa informação, sem substituí-la por uma bênção sugerida.
        if number == 5 and (tape.get("notIndicated") or "não indicada no folheto" in str(tape.get("title", "")).lower()):
            tape["title"] = "Bênção Solene — não indicada no folheto"
            tape["page"] = "—"
            tape["details"] = [[
                "Indicação",
                "O folheto não apresenta uma bênção solene específica."
            ]]
        else:
            tape["title"] = title
            tape["page"] = "—"
            tape["details"] = [["Conferência", detail]]
        tape.pop("suggestion", None)
        tape.pop("pageSuggestion", None)
        tape.pop("notIndicated", None)

    # A página da Missa pode estar confirmada no índice do Missal mesmo se
    # o PDF não a reproduzir; não alterar essa fita.
    entry["quick"] = " → ".join(
        ("?" if t.get("pageUnverified") else str(t.get("page", "—")))
        for t in entry.get("tapes", [])
        if str(t.get("page", "—")).strip() not in ("", "—") or t.get("pageUnverified")
    )
    entry["note"] = (
        "Folheto oficial vinculado. Somente partes verificadas no folheto "
        "são tratadas como oficiais; partes não reconhecidas ficam pendentes "
        "de conferência, sem sugestões substitutas."
    )
    return json.dumps(entry, sort_keys=True, ensure_ascii=False) != before
