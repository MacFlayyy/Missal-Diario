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
    assert 'if(weekdayForKey(key)!==0) continue;' in html,path
    assert 'const url="https://macflayyy.github.io/Missal-Diario/";' in html,path
    assert "const tapeH=tapeHeights[i]" in html,path
    assert "drawAllLines(allTapeDetails(t)" in html,path
    assert "drawInstagramMark(ctx,canvas.width-pad" in html,path
    assert 'id="dec24MassChoice"' in html,path
    assert "december24Choice=" in html,path
    assert "sujeita à conclusão dos testes" in html,path
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

def check_leaflet_fallback():
    """Teste executável: PDFs feriais nunca substituem domingos no fallback."""
    html=INDEX.read_text(encoding="utf-8")
    start=html.index("function getDominicalLeafletUrl(){")
    end=html.index("function openDominicalLeaflet(){",start)
    code=html[start:end]
    stub=r"""
const data={
  "2026-10-05":{folhetoDesktopUrl:"https://example.org/weekday.pdf"}
};
const window={MISSAL_STATUS:{}};
let today="2026-10-08";
function brasiliaTodayKey(){return today;}
function weekdayForKey(key){return new Date(key+"T12:00:00Z").getUTCDay();}
function addDaysKey(key,n){
  const d=new Date(key+"T12:00:00Z");d.setUTCDate(d.getUTCDate()+n);
  return d.toISOString().slice(0,10);
}
function sundayKeyForLeaflet(){return "2026-10-11";}
function isMobileLeafletDevice(){return false;}
"""
    checks=r"""
if(getDominicalLeafletUrl()!=="")throw Error("PDF ferial escolhido como dominical");
data["2026-10-04"]={folhetoDesktopUrl:"https://example.org/sunday.pdf"};
if(getDominicalLeafletUrl()!=="https://example.org/sunday.pdf")throw Error("Fallback do domingo anterior falhou");
data["2026-10-08"]={folhetoDesktopUrl:"https://example.org/special.pdf"};
if(getDominicalLeafletUrl()!=="https://example.org/special.pdf")throw Error("Folheto especial do próprio dia perdeu prioridade");
delete data["2026-10-08"];
window.MISSAL_STATUS={sundayLeafletDate:"2026-10-07",sundayLeafletDesktopUrl:"https://example.org/wrong.pdf"};
if(getDominicalLeafletUrl()!=="https://example.org/sunday.pdf")throw Error("Status semanal com dia ferial interferiu no domingo");
console.log("PASSOU fallback PDF: domingo, folheto ferial do próprio dia, status inválido");
"""
    p=subprocess.run(["node","-e",stub+"\n"+code+"\n"+checks],
                     capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    print(p.stdout.strip())


def check_update_safety():
    import ast
    import copy
    source=(ROOT/"scripts"/"update_folheto.py").read_text(encoding="utf-8")
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=="update_entry")
    mock={
        "classify_saudacao":lambda _:"B",
        "extract_rites_from_leaflet":lambda _: {},
        "opening_from_folheto":lambda text, kind: text,
        "classify_ato":lambda _:"Terceira fórmula, 2ª opção",
        "detect_missal_page":lambda _:"999",
        "detect_prefacio":lambda _:None,
        "detect_eucharistic":lambda _:None,
        "detect_acclamation":lambda _:None,
        "norm":lambda value:str(value).lower(),
    }
    exec(compile(ast.Module(body=[node],type_ignores=[]),"<update_entry>","exec"),mock)
    data=read_js_json(DATA,"window.MISSAL_DATA")
    item=copy.deepcopy(data["2026-10-08"])
    item["tapes"][0]["details"].append(["Outro detalhe","Preservar"])
    page=item["tapes"][1]["page"]
    mock["update_entry"](item,"folheto teste","https://example.org/teste.pdf")
    details=item["tapes"][0]["details"]
    assert ["Outro detalhe","Preservar"] in details,"Detalhe dos Ritos Iniciais perdido"
    assert any(str(d[0]).startswith("Saudação A") for d in details),"Texto pré-existente não preservado"
    assert any("Conferência necessária" in str(d[0]) for d in details),"Divergência sem aviso"
    assert item["tapes"][1]["page"]==page,"Página da Missa substituída por menção genérica do PDF"
    assert item["tapes"][0].get("suggestion") is True,"Fita sem texto declarada completa"
    second=copy.deepcopy(data["2026-10-08"])
    second["tapes"][0]["details"][0][1]="Texto original completo"
    mock["update_entry"](second,"folheto teste","https://example.org/teste.pdf")
    assert second["tapes"][0]["details"][0][0].startswith("Saudação A")
    assert any(str(d[0]).startswith("Conferência necessária") for d in second["tapes"][0]["details"])
    print("PASSOU folheto: orações, páginas e observações preservadas")

def check_cache_safety():
    html=INDEX.read_text(encoding="utf-8")
    sw=(ROOT/"sw.js").read_text(encoding="utf-8")
    assert 'k.startsWith("missal-diario-")' in sw
    assert "prepareEscapeHtml(page)" in html
    assert "const statusDate=window.MISSAL_STATUS?.availableThrough || addDaysKey(today,-1);" in html
    assert "remote[1]!==local[1]" in html
    for name in ("scripts/update_folheto.py","scripts/bump_daily_version.py"):
        compile((ROOT/name).read_text(encoding="utf-8"),name,"exec")
    print("PASSOU proteção de cache, liberação e atualização PWA")

def check_christmas_choice():
    """Modo geral precisa ser selecionável mesmo em 24/12 à tarde."""
    html=INDEX.read_text(encoding="utf-8")
    start=html.index("function getDisplayEntry(dateKey){")
    end=html.index('document.getElementById("dec24MassChoice")?.addEventListener',start)
    code=html[start:end]
    data=read_js_json(DATA,"window.MISSAL_DATA")
    sample=json.dumps(data["2026-12-24"],ensure_ascii=False)
    stub=(
        'const data={"2026-12-24":'+sample+'};\n'
        'let hour=13;\n'
        'function brasiliaTodayKey(){return "2026-12-24";}\n'
        'function brasiliaClockParts(){return {hour:String(hour)};}\n'
        'let december24Choice=null;\n'
    )
    checks="""
if(!/Vigília/.test(getDisplayEntry("2026-12-24").celebration)) throw Error("Seleção automática da tarde falhou");
december24Choice="combined";
if(getDisplayEntry("2026-12-24").celebration!==data["2026-12-24"].celebration) throw Error("Visão geral não respeitada");
hour=10;
if(getDisplayEntry("2026-12-24").celebration!==data["2026-12-24"].celebration) throw Error("Visão geral trocou pela hora");
december24Choice="morning";
if(!/manhã/.test(getDisplayEntry("2026-12-24").celebration)) throw Error("Missa da manhã não respeitada");
december24Choice="vigil";
if(!/Vigília/.test(getDisplayEntry("2026-12-24").celebration)) throw Error("Vigília explícita não respeitada");
console.log("PASSOU 24/12: geral, manhã, vigília e horário");
"""
    p=subprocess.run(["node","-e",stub+code+checks],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    print(p.stdout.strip())


def check_rites_texts():
    from datetime import date
    data=read_js_json(DATA,"window.MISSAL_DATA")
    assert len(data)>90
    for key,entry in data.items():
        rows=entry["tapes"][0]["details"][:2]
        for row in rows:
            assert row[1].strip(),f"{key}: abertura ausente"
            assert "P.:" not in row[1] and "T.:" not in row[1], f"{key}: falas adicionais"
            assert "\\n" not in row[1] and len(row[1]) <= 280, f"{key}: rito ainda longo"
            assert "Consultar o texto integral" not in row[1]
            assert " • sugestão" in row[0], f"{key}: sugestão sem identificação"
    assert "3ª opção" in data["2026-10-04"]["tapes"][0]["details"][1][0]
    assert "2ª opção" in data["2026-10-09"]["tapes"][0]["details"][1][0]
    assert 'class="detail-text"' in INDEX.read_text(encoding="utf-8")
    print(f"PASSOU: {len(data)} datas com textos escritos e legíveis no celular")


def check_official_leaflet_extraction():
    import ast
    import unicodedata
    source=(ROOT/"scripts"/"update_folheto.py").read_text(encoding="utf-8")
    nodes=[node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef)
           and node.name == "extract_rites_from_leaflet"]
    def normalized(value):
        s=unicodedata.normalize("NFD", str(value))
        s="".join(c for c in s if unicodedata.category(c)!="Mn")
        return " ".join(s.replace("–","-").replace("—","-").lower().split())
    ns={"re":re, "norm":normalized}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),"<pdf-sections>","exec"), ns)
    sample=(
        "RITOS INICIAIS\n"
        "2 SAUDAÇÃO INICIAL\n"
        "P.: Em nome do Pai e do Filho e do Espírito Santo.\n"
        "T.: Amém.\n"
        "P.: Que Deus acompanhe esta comunidade na celebração.\n"
        "T.: Bendito seja Deus.\n"
        "3 ATO PENITENCIAL\n"
        "P.: Irmãos e irmãs, reconheçamos nossos pecados nesta celebração.\n"
        "P.: Tende compaixão de nós, Senhor.\n"
        "T.: Porque somos pecadores.\n"
        "4 HINO DO GLÓRIA – canto próprio\n"
        "P.: Este conteúdo pertence ao hino e não pode ser capturado.\n"
    )
    parsed=ns["extract_rites_from_leaflet"](sample)
    assert "Que Deus acompanhe" in parsed.get("saudacao",""),parsed
    assert "Porque somos pecadores" in parsed.get("ato",""),parsed
    assert "Este conteúdo" not in parsed.get("ato",""),parsed
    assert ns["extract_rites_from_leaflet"]("2 SAUDAÇÃO INICIAL\nP.: só uma linha")=={}
    noisy=(
        "27º Domingo - RITOS INICIAIS\\n"
        "2 SAUDAÇÃO INICIAL - MR\\n"
        "P: Celebrante cumprimenta a assembleia neste dia.\\n"
        "T: Assembleia responde ao celebrante.\\n"
        "3 ATO PENITENCIAL - MR\\n"
        "P: Iniciamos juntos nossa celebração e pedimos o perdão.\\n"
        "T: A comunidade faz sua resposta penitencial.\\n"
        "4 HINO DO GLÓRIA - Canto\\n"
        "P: Esta parte não pode entrar no texto anterior.\\n"
    ).replace("\\n","\n")
    noisy_result=ns["extract_rites_from_leaflet"](noisy)
    assert "P.:" in noisy_result.get("saudacao",""),noisy_result
    assert "T.:" in noisy_result.get("ato",""),noisy_result
    print("PASSOU extração por seção: saudação, penitencial, limites e PDF incompleto")


def check_filename_filter_and_ocr():
    import ast
    from datetime import date, datetime
    from zoneinfo import ZoneInfo
    source=(ROOT/"scripts"/"update_folheto.py").read_text(encoding="utf-8")
    func=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)
              and n.name=="leaflet_date_from_filename")
    ns={"re":re,"date":date,"datetime":datetime,"ZoneInfo":ZoneInfo}
    exec(compile(ast.Module(body=[func],type_ignores=[]),"<filename-date>","exec"),ns)
    ok=ns["leaflet_date_from_filename"](
        "https://site.com/wp-content/uploads/2026/09/53-Povo-Deus-61-04_10_27o-Domingo-TC-Prova-Final.pdf"
    )
    assert ok=="2026-10-04",ok
    assert ns["leaflet_date_from_filename"]("https://site.com/sem-data.pdf") is None
    assert "allow_ocr=True" in source
    assert "ocr_scanned_folheto" in source
    print("PASSOU OCR seletivo: datas corretas e PDF sem data rejeitado")


def check_only_openings_from_folheto():
    import ast
    import unicodedata
    source=(ROOT/"scripts"/"update_folheto.py").read_text(encoding="utf-8")
    helper=next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name=="opening_from_folheto")
    def norm(value):
        source=unicodedata.normalize("NFD",str(value))
        source="".join(c for c in source if unicodedata.category(c)!="Mn")
        return source.lower().strip()
    ns={"norm":norm}
    exec(compile(ast.Module(body=[helper],type_ignores=[]),"<opening>","exec"),ns)
    choose=ns["opening_from_folheto"]
    greeting=(
        "P.: Em nome do Pai e do Filho e do Espírito Santo.\n"
        "T.: Amém.\n"
        "P.: Saudação inicial para todos os participantes presentes hoje.\n"
        "T.: Resposta da comunidade."
    )
    assert choose(greeting,"saudacao")=="Saudação inicial para todos os participantes presentes hoje."
    act=(
        "P.: No início da celebração, pedimos perdão e conversão.\n"
        "T.: Resposta do povo.\n"
        "P.: Continuação do rito que não deve aparecer."
    )
    assert choose(act,"ato")=="No início da celebração, pedimos perdão e conversão."
    assert choose("T.: Só a assembleia","ato")==""
    print("PASSOU: somente a frase inicial de cada rito")


def main():
    verify_html(INDEX)
    verify_html(STANDALONE,standalone=True)
    check_saturday_preview()
    check_liturgical_integrity()
    check_leaflet_fallback()
    check_update_safety()
    check_cache_safety()
    check_christmas_choice()
    check_rites_texts()
    check_official_leaflet_extraction()
    check_filename_filter_and_ocr()
    check_only_openings_from_folheto()
    print("TODOS OS TESTES PASSARAM")

if __name__=="__main__":
    main()
