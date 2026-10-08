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
    assert "effectiveLiturgicalColorName" in html,path
    assert 'if(!url){alert("O folheto em PDF' in html,path
    assert 'bottomExit.textContent="Sair do modo celebração"' in html,path
    assert 'if(getAvailableThrough()<today) return null;' in html,path
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

def main():
    verify_html(INDEX)
    verify_html(STANDALONE,standalone=True)
    check_saturday_preview()
    print("TODOS OS TESTES PASSARAM")

if __name__=="__main__":
    main()
