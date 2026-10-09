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
    """Não confundir escolhas do folheto com sugestões nos itens não indicados.

    A decisão é feita por fita e, na oração eucarística, por aclamação.
    Funciona também para dados antigos já confirmados parcialmente.
    """
    if not any(entry.get(field) for field in ("folhetoDesktopUrl", "folhetoUrl", "folhetoMobileUrl")):
        return False
    before = __import__("json").dumps(entry, sort_keys=True, ensure_ascii=False)
    tapes = {t.get("n"): t for t in entry.get("tapes", [])}
    if not all(number in tapes for number in (1, 2, 3, 4, 5)):
        return False

    t1 = tapes[1]
    if not t1.get("verifiedByFolheto"):
        previous = t1.get("details") or []
        valid_saud = next(
            (row for row in previous
             if isinstance(row, list) and len(row) >= 2 and row[0].startswith("Saudação ")
             and "a conferir" not in row[0] and str(row[1]).strip()), None
        )
        valid_ato = next(
            (row for row in previous
             if isinstance(row, list) and len(row) >= 2 and row[0].startswith("Ato Penitencial — ")
             and "a conferir" not in row[0] and str(row[1]).strip()), None
        )
        saad = valid_saud or ["Saudação A", SAUDACOES["A"]]
        ato = valid_ato or ["Ato Penitencial — Segunda fórmula, 2ª opção",
                            ATO_PENITENCIAL["Segunda fórmula, 2ª opção"]]
        t1["details"] = [
            [saad[0].split(" • ")[0] + " • sugestão", saad[1]],
            [ato[0].split(" • ")[0] + " • sugestão", ato[1]],
        ]
        t1["suggestion"] = True
    else:
        t1.pop("suggestion", None)

    t3 = tapes[3]
    if not t3.get("verifiedByFolheto"):
        if (t3.get("notIndicated") or str(t3.get("page", "—")) == "—"
                or "não identificado" in str(t3.get("title", "")).lower()):
            t3["page"], t3["title"] = suggested_preface(entry)
        t3["details"] = [["Uso", "Sugestão: o folheto não indicou este prefácio."]]
        t3["suggestion"] = True
        t3.pop("notIndicated", None)
    else:
        t3.pop("suggestion", None)

    t4 = tapes[4]
    if not t4.get("verifiedByFolheto"):
        if (t4.get("notIndicated") or str(t4.get("page", "—")) == "—"
                or "não identificada" in str(t4.get("title", "")).lower()):
            t4["page"], t4["title"] = "536", "Oração Eucarística II"
        t4["details"] = [
            ["Aclamação", "Mistério da fé! • sugestão"],
            ["Resposta", "Anunciamos, Senhor, a vossa morte e proclamamos a vossa ressurreição. Vinde, Senhor Jesus!"],
            ["Uso", "Oração Eucarística e aclamação sugeridas: não identificadas no folheto."],
        ]
        t4["suggestion"] = True
        t4.pop("notIndicated", None)
    else:
        t4.pop("suggestion", None)
        rows = t4.setdefault("details", [])
        acclamation = next((r for r in rows if isinstance(r, list) and len(r) >= 2
                            and r[0] == "Aclamação"), None)
        if not acclamation or any(word in str(acclamation[1]).lower()
                                  for word in ("não identificada", "a conferir")):
            if acclamation:
                acclamation[1] = "Mistério da fé! • sugestão"
            else:
                rows.append(["Aclamação", "Mistério da fé! • sugestão"])
            if not any(r[0] == "Resposta" for r in rows if isinstance(r, list) and len(r) >= 2):
                rows.append(["Resposta", "Anunciamos, Senhor, a vossa morte e proclamamos a vossa ressurreição. Vinde, Senhor Jesus!"])
            if not any(r[0] == "Uso" for r in rows if isinstance(r, list) and len(r) >= 2):
                rows.append(["Uso", "Somente a aclamação é sugestão; a Oração Eucarística segue o folheto."])

    t5 = tapes[5]
    if not t5.get("verifiedByFolheto"):
        t5["page"], t5["title"] = suggested_blessing(entry)
        t5["details"] = [
            ["Uso", "Sugestão: o folheto oficial não indica bênção solene específica."],
        ]
        t5["suggestion"] = True
        t5.pop("notIndicated", None)
    else:
        t5.pop("suggestion", None)

    entry["quick"] = " → ".join(
        str(t["page"]) for t in entry["tapes"]
        if str(t.get("page", "—")).strip() not in ("", "—")
    )
    if entry.get("officialLeafletApplied"):
        entry["note"] = (
            "Indicações do folheto oficial aplicadas. Onde o folheto não especifica "
            "uma parte, a marcação é sugestão, não escolha oficial."
        )
    return __import__("json").dumps(entry, sort_keys=True, ensure_ascii=False) != before
