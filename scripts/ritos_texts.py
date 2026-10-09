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
