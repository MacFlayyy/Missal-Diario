#!/usr/bin/env python3
"""Testes de regressão do Missal Diário executados antes de publicar."""
from __future__ import annotations
from datetime import datetime as RealDatetime
from pathlib import Path
import importlib.util
import json
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/"index.html"
STANDALONE=ROOT/"Missal-Diario-Standalone.html"
DATA=ROOT/"data.js"

def read_js_json(path,variable):
    text=path.read_text(encoding="utf-8")
    m=re.search(rf"{re.escape(variable)}\s*=\s*(\{{.*\}})\s*;\s*$",text,re.S)
    assert m, f"{path.name}: dados ausentes"
    return json.loads(m.group(1))

def verify_html(path,standalone=False):
    html=path.read_text(encoding="utf-8")
    assert html.count("<html")==1 and html.strip().endswith("</html>"),path
    assert "</head>" in html and "</body>" in html,path
    assert not re.search(r"</html>\s*<(?:style|script)\b",html,re.I),path
    assert "accessibility-and-stability-v65" in html,path
    assert "layout-regression-fixes-v67" in html,path
    assert "grid-template-columns:repeat(5,minmax(0,1fr))" in html,path
    assert "const heroY=160, heroH=475+heroExtra" in html,path
    assert "const quickY=660+heroExtra" in html,path
    assert "const sectionY=835+heroExtra" in html,path
    assert "madrugada de domingo" in html,path
    assert "effectiveLiturgicalColorName" in html,path
    assert 'if(!url){alert("O folheto em PDF' in html,path
    assert 'bottomExit.textContent="Sair do modo celebração"' in html,path
    assert 'madrugada de domingo' in html,path
    assert 'if(weekday===0)' in html,path
    assert 'configured===today && published>=saturday' in html,path
    if standalone:
        assert html.count("window.MISSAL_DATA =")==1, "data.js não incorporado"
        assert html.count("window.MISSAL_STATUS =")==1, "status.js não incorporado"
        assert not re.search(r'<script\s+src="(?:data|status)\.js',html,re.I), "Scripts locais externos"
    else:
        assert '<script src="data.js?' in html
        assert '<script src="status.js?' in html
    for i,m in enumerate(re.finditer(r"<script\b([^>]*)>(.*?)</script>",html,re.I|re.S)):
        if re.search(r"\bsrc\s*=",m.group(1)):continue
        script=m.group(2).strip()
        if not script:continue
        with tempfile.NamedTemporaryFile("w",encoding="utf-8",suffix=".js") as temp:
            temp.write(script)
            temp.flush()
            result=subprocess.run(["node","--check",temp.name],capture_output=True,text=True)
            assert result.returncode==0,f"{path.name} script {i}: {result.stderr[:1500]}"
    print(f"PASSOU HTML/scripts: {path.name}")

def check_saturday_preview():
    spec=importlib.util.spec_from_file_location("validate_daily",ROOT/"scripts"/"validate_daily.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data=read_js_json(DATA,"window.MISSAL_DATA")
    assert "2026-10-11" in data,"Domingo 11/10 ausente dos dados"
    class Saturday(RealDatetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,10,10,4,30,tzinfo=tz)
    class Sunday(RealDatetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,10,11,5,0,tzinfo=tz)
    with tempfile.TemporaryDirectory() as folder:
        module.STATUS_FILE=Path(folder)/"status.js"
        module.datetime=Saturday
        module.save_status("2026-10-10",data)
        status=read_js_json(module.STATUS_FILE,"window.MISSAL_STATUS")
        assert status.get("sundayPreview")=="2026-10-11",status
        assert status["availableThrough"]=="2026-10-10"
        module.datetime=Sunday
        module.save_status("2026-10-11",data)
        status=read_js_json(module.STATUS_FILE,"window.MISSAL_STATUS")
        assert "sundayPreview" not in status,status
    print("PASSOU prévia dominical: sábado sim, domingo não")

def check_liturgical_integrity():
    import copy
    import datetime
    data=read_js_json(DATA,"window.MISSAL_DATA")
    assert data, "Calendário vazio"
    for key,entry in sorted(data.items()):
        for tape in entry.get("tapes",[]):
            for row in tape.get("details",[]):
                if isinstance(row,list) and len(row)>=2:
                    assert not str(row[1]).strip().endswith(("...","…")), f"{key}: oração truncada"
        date=datetime.date.fromisoformat(key)
        tapes=entry.get("tapes",[])
        assert len(tapes)==5, f"{key}: cinco fitas são obrigatórias"
        assert [t.get("n") for t in tapes]==[1,2,3,4,5],f"{key}: ordem de fitas"
        expected=" → ".join(str(t.get("page","")).strip() for t in tapes)
        assert entry.get("quick")==expected,f"{key}: separação rápida difere das fitas"
        for tape in tapes:
            assert tape.get("page"),f"{key}: fita sem página"
            assert str(tape.get("title","")).strip(),f"{key}: fita sem título"
            for detail in tape.get("details",[]):
                assert not any(x in str(detail[1]) for x in (
                    "“A graça de nosso Senhor Jesus Cristo...”",
                    "“No início desta celebração eucarística...”")), f"{key}: texto abreviado"
        if date.weekday()==6:
            assert entry.get("cycle") in {"Ano A","Ano B","Ano C"},f"{key}: ciclo dominical não definido"

    christmas=data["2026-12-24"]
    assert "/" in christmas["tapes"][2]["page"] and "/" in christmas["tapes"][4]["page"]
    assert data["2026-12-27"]["cycle"]=="Ano B"

    spec=importlib.util.spec_from_file_location("validate_daily",ROOT/"scripts"/"validate_daily.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.is_valid_page("817–818"),"Intervalo com en dash não aceito"
    assert module.is_valid_page("823 / 939 ou 952"),"Alternativas não aceitas"
    assert not module.is_valid_page("430 texto arbitrário"),"Página sem referência passou"
    sample=copy.deepcopy(data["2026-10-08"])
    before=copy.deepcopy(sample["tapes"][0]["details"])
    module.repair_entry(sample)
    assert sample["tapes"][0]["details"]==before,"As opções litúrgicas existentes foram modificadas"

    invalid=copy.deepcopy(data["2026-10-08"])
    invalid["tapes"][1]["page"]="—"
    try:
        module.repair_entry(invalid)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Página da Fita 2 inventada em vez de bloquear publicação")
    missing=copy.deepcopy(data["2026-10-08"])
    missing["tapes"]=[t for t in missing["tapes"] if t["n"] != 3]
    try:
        module.repair_entry(missing)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Fita faltante foi recriada com página fictícia")
    print(f"PASSOU integridade litúrgica: {len(data)} datas, ciclos e páginas sem invenções")

def main():
    verify_html(INDEX)
    verify_html(STANDALONE,standalone=True)
    check_saturday_preview()
    check_liturgical_integrity()
    print("TODOS OS TESTES PASSARAM")

if __name__=="__main__":
    main()
