#!/usr/bin/env python3
"""Completar Ritos Iniciais quando a escolha é apenas uma sugestão."""
SAUDACOES = {"A": "P.: Em nome do Pai e do Filho e do Espírito Santo.\nT.: Amém.\nP.: A graça de nosso Senhor Jesus Cristo, o amor do Pai e a comunhão do Espírito Santo estejam convosco.\nT.: Bendito seja Deus, que nos reuniu no amor de Cristo."}
ATO_PENITENCIAL = {
    "Segunda fórmula, 2ª opção": "P.: No início desta celebração eucarística, peçamos a conversão do coração, fonte de reconciliação e comunhão com Deus e com os irmãos e irmãs.\n(breve silêncio)\nP.: Tende compaixão de nós, Senhor.\nT.: Porque somos pecadores.\nP.: Manifestai, Senhor, a vossa misericórdia.\nT.: E dai-nos a vossa salvação.\nP.: Deus todo-poderoso tenha compaixão de nós, perdoe os nossos pecados e nos conduza à vida eterna.\nT.: Amém.\nP.: Senhor, tende piedade de nós.\nT.: Senhor, tende piedade de nós.\nP.: Cristo, tende piedade de nós.\nT.: Cristo, tende piedade de nós.\nP.: Senhor, tende piedade de nós.\nT.: Senhor, tende piedade de nós.",
    "Segunda fórmula, 3ª opção": "P.: De coração contrito e humilde, aproximemo-nos do Deus justo e santo, para que tenha piedade de nós, pecadores.\n(breve silêncio)\nP.: Tende compaixão de nós, Senhor.\nT.: Porque somos pecadores.\nP.: Manifestai, Senhor, a vossa misericórdia.\nT.: E dai-nos a vossa salvação.\nP.: Deus todo-poderoso tenha compaixão de nós, perdoe os nossos pecados e nos conduza à vida eterna.\nT.: Amém.\nP.: Senhor, tende piedade de nós.\nT.: Senhor, tende piedade de nós.\nP.: Cristo, tende piedade de nós.\nT.: Cristo, tende piedade de nós.\nP.: Senhor, tende piedade de nós.\nT.: Senhor, tende piedade de nós.",
}
def apply_rite_suggestions(entry):
    tape=next((x for x in entry.get("tapes",[]) if x.get("n")==1),None)
    if not tape: return False
    changed=False
    for row in tape.get("details",[]):
        if not isinstance(row,list) or len(row)<2: continue
        text=str(row[1] or "").lower()
        if not any(x in text for x in (
            "consultar o texto integral", "texto da oração não transcrito", "texto nao transcrito"
        )): continue
        label=str(row[0]).split(" • ")[0]
        if label.startswith("Saudação "):
            suggestion=SAUDACOES.get(label.removeprefix("Saudação "))
        elif label.startswith("Ato Penitencial — "):
            suggestion=ATO_PENITENCIAL.get(label.removeprefix("Ato Penitencial — "))
        else: suggestion=None
        if not suggestion: continue
        row[1]=suggestion
        if " • sugestão" not in row[0]: row[0]=label+" • sugestão"
        changed=True
    if changed:
        tape["suggestion"]=True
        if "folheto oficial" in str(entry.get("source","")).lower():
            entry["ritesPendingOfficial"]=True
    return changed
