#!/usr/bin/env python3
"""Testes de regressão do Missal Diário executados antes de publicar.
Inclui marcadores explícitos de conferência para folhetos incompletos."""
from __future__ import annotations
from datetime import datetime as RealDatetime
from pathlib import Path
import importlib.util
import json
import re
import sys
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
    assert "calendar-responsive-v71" in html,path
    assert "deep-visual-accessibility-fixes-v73" in html,path
    assert "touch-targets-and-missal-ux-v74" in html,path
    assert 'const actualChoice=december24Choice || "combined";' in html,path
    assert 'function refreshChristmasVigil()' not in html,path
    assert 'setInterval(refreshChristmasVigil' not in html,path
    assert 'return december24Choice==="vigil" ? "branco" : "roxo";' in html,path
    assert 'return "Ciclo litúrgico"' in html,path
    assert 'app-icon-180.png' not in html if standalone else 'app-icon-180.png' in html,path
    assert '[{opacity:.35,transform:"translateY(7px)"}' not in html,path
    assert "const titleBottom=drawLines(t.title" in html,path
    assert "drawAllLines(allTapeDetails(t),pad+18,titleBottom+8" in html,path
    assert "titleRows*25" in html,path
    assert "multi-page-values" in html,path
    assert 'menu.setAttribute("aria-modal","true")' in html,path
    assert 'menu.querySelector("#calendarClose")?.focus()' in html,path
    assert "const selected=december24Choice;" in html,path
    assert "Seleção automática da tarde falhou" not in html,path
    assert "body.calendar-open::before" in html,path
    assert "function closeDateMenu()" in html,path
    assert 'aria-expanded="false" aria-controls="dateMenu"' in html,path
    assert 'max-height:calc(100dvh - 24px)' in html,path
    assert 'if(tape.pageUnverified) parts.unshift("Página ainda não conferida no Missal Romano.")' in html,path
    assert 'if(tape.suggestion && !parts.some(t=>/sugestão/i.test(t)))' in html,path
    assert 'const pageText=t.pageUnverified?"PÁGINA A CONFERIR"' in html,path
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
    # Texto do rodapé sobre a atualização automática removido a pedido do usuário (05/11/2026).
    assert 'id="lastUpdateText"' in html,path
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
    assert "2026-10-25" in data,"Domingo 25/10 ausente dos dados"
    class Saturday(RealDatetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,10,24,4,30,tzinfo=tz)
    class Sunday(RealDatetime):
        @classmethod
        def now(cls,tz=None):return cls(2026,10,25,5,0,tzinfo=tz)
    with tempfile.TemporaryDirectory() as folder:
        module.STATUS_FILE=Path(folder)/"status.js"
        module.datetime=Saturday
        module.save_status("2026-10-24",data)
        status=read_js_json(module.STATUS_FILE,"window.MISSAL_STATUS")
        assert status.get("sundayPreview")=="2026-10-25",status
        assert status["availableThrough"]=="2026-10-24"
        assert status.get("contentVersion"),"Publicação sem revisão do conteúdo"
        version=status["contentVersion"]
        publication_time=status["lastSuccessfulUpdateAt"]

        class SaturdayLater(RealDatetime):
            @classmethod
            def now(cls,tz=None):return cls(2026,10,24,7,12,tzinfo=tz)
        module.datetime=SaturdayLater
        module.save_status("2026-10-24",data)
        same=read_js_json(module.STATUS_FILE,"window.MISSAL_STATUS")
        assert same["contentVersion"]==version,"Revisão mudou sem alterações"
        assert same["lastSuccessfulUpdateAt"]==publication_time,"Publicação redundante"

        import copy
        changed=copy.deepcopy(data)
        changed["2026-10-24"]["note"]=str(changed["2026-10-24"].get("note",""))+" (corrigido)"
        module.save_status("2026-10-24",changed)
        updated=read_js_json(module.STATUS_FILE,"window.MISSAL_STATUS")
        assert updated["contentVersion"]!=version,"Correção diária não identificada"
        assert updated["lastSuccessfulUpdateAt"]!=publication_time,"Horário de correção não atualizado"

        class SundayBeforeFive(RealDatetime):
            @classmethod
            def now(cls,tz=None):return cls(2026,10,25,4,15,tzinfo=tz)
        module.datetime=SundayBeforeFive
        module.save_status("2026-10-25",data)
        status=read_js_json(module.STATUS_FILE,"window.MISSAL_STATUS")
        assert status.get("sundayPreview")=="2026-10-25", (
            "A atualização antecipada apagou a prévia liberada no sábado",status
        )
        assert status["availableThrough"]=="2026-10-25"

        module.datetime=Sunday
        module.save_status("2026-10-25",data)
        status=read_js_json(module.STATUS_FILE,"window.MISSAL_STATUS")
        assert "sundayPreview" not in status,status

        # Solenidades e festas substituem o título "Domingo", mas continuam
        # sendo antecipadas no sábado para a missa vespertina.
        for saturday, sunday in (
            ("2026-10-31", "2026-11-01"),  # Todos os Santos
            ("2026-11-21", "2026-11-22"),  # Cristo Rei
            ("2026-12-26", "2026-12-27"),  # Sagrada Família
        ):
            year, month, day = map(int, saturday.split("-"))
            class SpecialSaturday(RealDatetime):
                @classmethod
                def now(cls, tz=None):
                    return cls(year, month, day, 6, 30, tzinfo=tz)
            module.datetime=SpecialSaturday
            module.save_status(saturday,data)
            special=read_js_json(module.STATUS_FILE,"window.MISSAL_STATUS")
            assert special.get("sundayPreview")==sunday, (
                f"Festa ou solenidade de domingo {sunday} indisponível no sábado",
                special,
            )
    print("PASSOU prévias: domingo comum, madrugada, solenidades e festas")

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
        quick_pages=[
            "?" if t.get("pageUnverified") else str(t.get("page","—")).strip() or "—"
            for t in tapes
        ]
        # Páginas seguidas iguais aparecem uma vez só (pedido do usuário).
        sys.path.insert(0, str(ROOT/"scripts"))
        from ritos_texts import quick_from_tapes
        expected=quick_from_tapes(tapes)
        assert entry.get("quick")==expected, f"{key}: separação rápida difere das fitas; quick={entry.get('quick')!r}; esperado={expected!r}; páginas={quick_pages!r}"
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
    assert 'const remoteVersion=raw.match(' in html
    assert 'const versionChanged=Boolean(remoteVersion && remoteVersion!==localVersion);' in html
    # Uma barra invertida duplicada dentro dessas regex impede a
    # leitura do status publicado (erro encontrado na revisão aprofundada).
    status_refresh=html.split("async function refreshIfDailyStatusAdvanced(){",1)[1].split('window.addEventListener("focus"',1)[0]
    for line in status_refresh.splitlines():
        if "raw.match(" in line:
            assert "\\\\s" not in line, "Regex de atualização com barras duplicadas"
    assert "tapes:[]" in html, "Fallback sem dados não deve inventar páginas do Missal"
    assert 'function cacheKey(url)' in sw and 'FILES.has(file)' in sw
    assert 'await store.put(key,res.clone())' in sw
    assert 'missal-romano-2023-pdf-4' not in html
    assert ':focus-visible' in html
    for name in ("scripts/update_folheto.py","scripts/bump_daily_version.py",
                 "scripts/generate_daily.py","scripts/check_publication.py",
                 "scripts/validate_daily.py"):
        compile((ROOT/name).read_text(encoding="utf-8"),name,"exec")
    publication=(ROOT/"scripts"/"check_publication.py").read_text(encoding="utf-8")
    assert "remote_status == local_status" in publication, "Status publicado não é comparado ao validado"
    assert "remote_data == expected_data" in publication, "Dados publicados não são comparados ao arquivo validado"
    print("PASSOU proteção de cache, liberação, atualização PWA e integridade do deploy")

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
if(getDisplayEntry("2026-12-24").celebration!==data["2026-12-24"].celebration) throw Error("Sem escolha explícita não pode forçar a Vigília");
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
        fita1=entry["tapes"][0]
        rows=fita1["details"][:2]
        # A fita pode continuar verificada pelo folheto mesmo quando uma
        # variante incompleta impede marcar o cadastro inteiro como aplicado.
        rites_official = bool(entry.get("officialLeafletApplied") or fita1.get("verifiedByFolheto"))
        for row in rows:
            assert row[1].strip(),f"{key}: abertura ausente"
            assert "P.:" not in row[1] and "T.:" not in row[1], f"{key}: falas adicionais"
            assert "\\n" not in row[1] and (rites_official or len(row[1]) <= 280), f"{key}: rito ainda longo"
            assert "Consultar o texto integral" not in row[1]
            if rites_official:
                assert "sugestão" not in row[0].lower(), f"{key}: folheto com sugestão"
            elif "a conferir" in row[0].lower():
                # Uma variante oficial incompleta pode deixar um marcador de
                # conferência no lugar do texto do rito; ele não é uma sugestão.
                assert "não identificad" in row[1].lower() and "segurança" in row[1].lower(), f"{key}: pendência sem explicação"
            elif any(
                isinstance(item, list) and len(item) >= 2
                and str(item[0]).startswith("Conferência necessária")
                and "precisa ser conferido" in str(item[1]).lower()
                and "antes de substituir" in str(item[1]).lower()
                for item in fita1.get("details", [])
            ):
                # Se o PDF indicar uma fórmula diferente, o texto anterior
                # pode ser preservado somente com um aviso explícito de revisão.
                pass
            else:
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



def check_verified_leaflet_days():
    data=read_js_json(DATA,"window.MISSAL_DATA")
    expected={
        "2026-10-04":("Saudação A","Segunda fórmula, 3ª opção","477","545"),
        "2026-10-11":("Saudação A","Primeira fórmula, 3ª opção","614","614"),
        "2026-10-12":("Saudação E","Primeira fórmula, 2ª opção","828","523"),
        "2026-10-18":("Saudação B","Terceira fórmula, 2ª opção","626","626"),
    }
    for day,(saud,ato,pref,oe) in expected.items():
        item=data[day]
        assert item.get("officialLeafletApplied"),day
        assert item["tapes"][0]["details"][0][0] == saud,day
        assert ato in item["tapes"][0]["details"][1][0],day
        assert item["tapes"][2]["page"] == pref,day
        assert item["tapes"][3]["page"] == oe,day
        blessing=item["tapes"][4]
        assert blessing["page"] == "585",day
        assert blessing.get("suggestion") is True,f"{day}: bênção sem sugestão"
        assert "sugestão" in blessing["details"][0][1].lower(),day
        assert "585" in item["quick"],day
        for tape in item["tapes"][:4]:
            assert not tape.get("suggestion"),f"{day}: fita oficial marcada como sugestão"
        if day == "2026-10-11":
            # O folheto nº 54 (11/10/2026) imprime "Mistério da fé para a salvação do mundo!".
            details=item["tapes"][3]["details"]
            assert any(row[0]=="Aclamação" and row[1]=="Mistério da fé para a salvação do mundo!"
                       for row in details),"Aclamação de 11/10 deve seguir o folheto"
            assert item["tapes"][3].get("verifiedByFolheto"),"Oração Eucarística permanece oficial"
        else:
            assert all("sugestão" not in str(row[1]).lower()
                       for tape in item["tapes"][:4] for row in tape.get("details", []))
    sunday=data["2026-10-18"]
    verified_parts=set(sunday.get("officialVerifiedParts", []))
    assert {1,3,4}.issubset(verified_parts)
    formulary=sunday["tapes"][1]
    # A página 411 é sempre confirmada no índice do Missal. Se o extrator
    # encontrar a indicação expressa no folheto, deve também marcá-la como
    # verificada; caso contrário, precisa deixar explícita a lacuna do folheto.
    if 2 in verified_parts:
        assert formulary.get("verifiedByFolheto")
        assert not formulary.get("folhetoPageNotSpecified")
        assert "indicada e conferida no folheto oficial" in formulary["details"][0][1].lower()
    else:
        assert not formulary.get("verifiedByFolheto")
        assert formulary.get("folhetoPageNotSpecified")
    assert sunday["quick"]=="430 → 411 → 626 → 585"
    assert sunday["tapes"][3]["details"][0][1]=="Mistério da fé e do amor!"
    from update_folheto import leaflet_initial_choices, leaflet_oe_prefacio, detect_acclamation
    scan=("SAUDAÇÃO INICIAL\\n"
          "A graça e a paz de Deus, nosso Pai\\n"
          "ATO PENITENCIAL\\n"
          "Em Jesus Cristo, o justo, que interce- de por nós e nos reconcilia com o Pai\\n"
          "HINO DO GLÓRIA\\n"
          "ORAÇÃO EUCARÍSTICA PARA DIVERSAS CIRCUNTÂNCIAS III - Je- sus, caminho para o Pai\\n"
          "Mistério da fé e do amor!")
    assert leaflet_initial_choices(scan)==("B","Terceira fórmula, 2ª opção")
    pref,oe=leaflet_oe_prefacio(scan)
    assert pref[1]==oe[1]=="626"
    assert detect_acclamation(scan)=="Mistério da fé e do amor!"
    html=INDEX.read_text(encoding="utf-8")
    assert "Abrir o texto original no folheto oficial" not in html
    assert "rites-official-pdf" not in html
    print("PASSOU folhetos: 4 fitas oficiais, bênção sugerida e aclamação parcial")



def check_folheto_gap_fallbacks():
    import copy
    from ritos_texts import fill_folheto_gaps
    data=read_js_json(DATA,"window.MISSAL_DATA")
    # Ao reler um folheto, a bênção ausente deve voltar como sugestão.
    sample=copy.deepcopy(data["2026-10-04"])
    original=copy.deepcopy(sample["tapes"][:4])
    sample["tapes"][4].update({
        "page": "—", "title": "Bênção Solene — não indicada no folheto",
        "notIndicated": True,
        "details": [["Indicação", "O folheto não apresenta uma bênção solene específica."]],
    })
    sample["tapes"][4].pop("suggestion",None)
    sample["tapes"][4].pop("verifiedByFolheto",None)
    assert fill_folheto_gaps(sample)
    assert sample["tapes"][4]["page"]=="—"
    assert "não indicada no folheto" in sample["tapes"][4]["title"].lower()
    assert "suggestion" not in sample["tapes"][4]
    assert sample["tapes"][:4]==original
    assert not fill_folheto_gaps(sample),"Aplicação de sugestões deve ser idempotente"

    # Uma aclamação já marcada como verificada não deve ser substituída.
    partial=copy.deepcopy(data["2026-10-11"])
    partial["tapes"][3]["details"]=[["Aclamação","Não identificada no folheto; conferir antes da celebração"]]
    before_partial=copy.deepcopy(partial)
    before_acclamation=copy.deepcopy(partial["tapes"][3]["details"])
    fill_folheto_gaps(partial)
    assert partial["tapes"][3]["details"]==before_acclamation, (
        "A aclamação já verificada foi substituída durante o preenchimento de outras lacunas"
    )
    # Outras fitas ainda não verificadas podem ser marcadas como pendentes;
    # a garantia importante é preservar integralmente a parte oficial já confirmada.

    # Quando o OCR não confirma um prefácio, não inventar página nem escolha.
    missing=copy.deepcopy(data["2026-10-11"])
    missing["tapes"][2].update({
        "title": "Prefácio — não identificado no folheto", "page": "—",
        "notIndicated": True
    })
    missing["tapes"][2].pop("verifiedByFolheto",None)
    assert fill_folheto_gaps(missing)
    assert missing["tapes"][2]["page"]=="—"
    assert "sugestão" not in missing["tapes"][2]
    assert "não identificado com segurança" in missing["tapes"][2]["details"][0][1].lower()
    assert not fill_folheto_gaps(missing)

    print("PASSOU: lacunas oficiais ficam pendentes e escolhas verificadas são preservadas")



def check_incomplete_leaflet_variant_protection():
    """Uma versão mobile sem texto não deve apagar a escolha oficial do PDF."""
    import ast
    import copy
    updater=(ROOT/"scripts"/"update_folheto.py").read_text(encoding="utf-8")
    node=next(n for n in ast.parse(updater).body if isinstance(n,ast.FunctionDef)
              and n.name=="update_entry_verified")
    names={
        "json":json,
        "fill_folheto_gaps":lambda entry: False,
        "leaflet_initial_choices":lambda text: (None,None),
        "leaflet_oe_prefacio":lambda text: (None,None),
        "detect_missal_page":lambda text: None,
    }
    exec(compile(ast.Module(body=[node],type_ignores=[]),"<verified-guard>","exec"),names)
    data=read_js_json(DATA,"window.MISSAL_DATA")
    item=copy.deepcopy(data["2026-10-04"])
    before=copy.deepcopy(item)
    changed=names["update_entry_verified"](item,"", "https://example.org/04_10-Versao-Celular.pdf")
    assert not changed
    assert item==before,"PDF alternativo vazio apagou escolhas oficiais"
    assert item["tapes"][0]["details"][1][0]=="Ato Penitencial — Segunda fórmula, 3ª opção"

    # A mesma proteção deve funcionar quando o folheto confirmou apenas
    # as fitas 1, 3 e 4, mas a página 2 foi confirmada independentemente.
    partial=copy.deepcopy(data["2026-10-18"])
    partial["folhetoDesktopUrl"]="https://example.org/18-10-Prova-Final.pdf"
    partial["officialLeafletApplied"]=True
    partial["officialVerifiedParts"]=[1,3,4]
    partial_before=copy.deepcopy(partial)
    changed=names["update_entry_verified"](
        partial,"","https://example.org/18-10-Versao-Celular.pdf"
    )
    assert not changed
    assert partial==partial_before,"PDF alternativo apagou fitas oficiais parciais"
    print("PASSOU: PDF alternativo incompleto preserva fitas oficiais completas e parciais")



def check_known_sunday_page_survives_leaflet_ocr():
    """Página do formulário no Missal não pode virar '?' por OCR incompleto."""
    import ast
    import copy
    data=read_js_json(DATA,"window.MISSAL_DATA")
    record=data["2026-10-18"]
    reference=json.loads((ROOT/"missal-date-formulary-map.json").read_text(encoding="utf-8"))
    registered=reference["entries"]["2026-10-18"]["missal_formulary_page"]
    tape=record["tapes"][1]
    assert registered=="411" and tape["page"]==registered
    assert not tape.get("pageUnverified"),"Fita 2 ocultou página confirmada no Missal"
    if tape.get("verifiedByFolheto"):
        assert 2 in record.get("officialVerifiedParts", [])
        assert not tape.get("folhetoPageNotSpecified")
    else:
        assert 2 not in record.get("officialVerifiedParts", [])
        assert tape.get("folhetoPageNotSpecified"),"Lacuna do folheto não sinalizada"
    assert record["quick"].split(" → ")[1]=="411",record["quick"]
    assert "?" not in record["quick"],record["quick"]

    source=(ROOT/"scripts"/"update_folheto.py").read_text(encoding="utf-8")
    nodes=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)
           and n.name in ("formulary_page_confirmed_in_missal","update_entry_verified")]
    assert len(nodes)==2,"Atualizador perdeu a separação entre Missal e folheto"
    ns={
        "json":json,"re":re,"FORMULARY_INDEX_FILE":ROOT/"missal-date-formulary-map.json",
        "leaflet_initial_choices":lambda _: (None,None),
        "leaflet_oe_prefacio":lambda _: (None,None),
        "detect_acclamation":lambda _: None,
        "detect_missal_page":lambda _: None,
        "norm":lambda _: "",
        "fill_folheto_gaps":lambda _: False,
    }
    exec(compile(ast.Module(body=nodes,type_ignores=[]),"<folheto-page-regression>","exec"),ns)
    assert ns["formulary_page_confirmed_in_missal"](record,"411")
    assert not ns["formulary_page_confirmed_in_missal"](record,"412")
    old=copy.deepcopy(record)
    if tape.get("verifiedByFolheto"):
        original_tape=copy.deepcopy(old["tapes"][1])
        ns["update_entry_verified"](old,"","https://example.org/18-10-Versao-Celular.pdf")
        assert old["tapes"][1]==original_tape,"PDF alternativo vazio apagou confirmação do folheto"
    else:
        old["tapes"][1]["pageUnverified"]=True
        old["tapes"][1]["suggestion"]=True
        old["quick"]="430 → ? → 477 → 536 → 585"
        same_url=old.get("folhetoDesktopUrl") or old.get("folhetoUrl") or "https://example.org/18-10-folheto.pdf"
        ns["update_entry_verified"](old,"",same_url)
        assert old["tapes"][1]["page"]=="411"
        assert not old["tapes"][1].get("pageUnverified")
        assert not old["tapes"][1].get("suggestion")
        assert not old["tapes"][1].get("verifiedByFolheto")
        assert old["tapes"][1].get("folhetoPageNotSpecified")
    unknown=copy.deepcopy(record)
    unknown["celebration"]="Celebração ainda sem referência conferida"
    assert not ns["formulary_page_confirmed_in_missal"](unknown,"411")
    print("PASSOU: Fita 2 do domingo preserva p. 411 mesmo sem OCR do folheto")


def check_pending_page_copy():
    html=INDEX.read_text(encoding="utf-8")
    assert "existe página do Missal ainda não conferida" in html
    assert 't.pageUnverified ? "Página a conferir"' in html
    assert 'return lines.join("\\n")' in html
    # o texto copiado sai limpo, sem símbolos de formatação (###, **)
    assert "Texto limpo para colar" in html and '.replace(/\\*\\*/g,"")' in html
    print("PASSOU: páginas sem verificação explícitas também no conteúdo copiado")


def check_on_demand_calendar():
    """Calendário litúrgico perpétuo: qualquer dia sai completo, com as páginas do Missal."""
    from datetime import date, timedelta
    import re as _re
    sys.path.insert(0, str(ROOT / "scripts"))
    import liturgical_calendar as lc
    from generate_daily import ensure_dates, liturgical_year
    from validate_daily import repair_entry
    from check_missal_references import check_perpetual_day

    # 1) Datas móveis conferidas de forma independente (tabelas de Páscoa).
    for year, (m, d) in {2024: (3, 31), 2025: (4, 20), 2026: (4, 5), 2027: (3, 28), 2028: (4, 16),
                         2029: (4, 1), 2030: (4, 21), 2031: (4, 13), 2035: (3, 25), 2038: (4, 25)}.items():
        assert lc.easter(year) == date(year, m, d), year
    assert lc.advent_start(2026) == date(2026, 11, 29) and lc.advent_start(2027) == date(2027, 11, 28)
    assert liturgical_year(date(2027, 11, 28)) == "Ano C" and liturgical_year(date(2027, 11, 27)) == "Ano B"

    # 2) O motor reproduz os dias de 2026 já conferidos com o Missal.
    data = read_js_json(DATA,"window.MISSAL_DATA")
    known_differences = {
        "2026-10-02", "2026-10-05", "2026-10-06",   # cadastro antigo divergia do Calendário do Missal
        "2026-10-12", "2026-12-08", "2026-12-12",   # página do título × página das orações
        "2026-12-24", "2026-12-25",                 # formato com várias Missas (tratado à parte)
    }
    compared = 0
    for key, old in data.items():
        if key > "2026-12-31" or key in known_differences:
            continue
        info = lc.liturgical_day(date.fromisoformat(key))
        assert info["page"] == old["tapes"][1]["page"], (key, info["page"], old["tapes"][1]["page"])
        assert info["color"] == old["color"], (key, info["color"], old["color"])
        if old["grade"] != "Memória facultativa" or info["grade"] != "Dia de semana":
            assert info["grade"] == old["grade"], (key, info["grade"], old["grade"])
        compared += 1
    assert compared >= 80, compared
    for key in ("2026-12-24", "2026-12-25"):
        new = lc.build_entry(date.fromisoformat(key))
        assert [t["page"] for t in new["tapes"]] == [t["page"] for t in data[key]["tapes"]], key

    # 3) Casos de precedência e transferências (Normas do Ano Litúrgico e Brasil).
    def day(y, m, d):
        e = lc.build_entry(date(y, m, d))
        return e["celebration"], e["grade"], e["tapes"][1]["page"]
    expected = {
        (2027, 1, 1): ("Santa Maria, Mãe de Deus", "Solenidade", "138"),
        (2027, 1, 3): ("Epifania do Senhor", "Solenidade", "144"),
        (2027, 1, 10): ("Batismo do Senhor", "Festa", "158"),
        (2029, 1, 8): ("Batismo do Senhor", "Festa", "158"),            # Epifania em 7/1 → segunda-feira
        (2027, 2, 10): ("Quarta-feira de Cinzas", "Quarta-feira de Cinzas", "163"),
        (2027, 3, 21): ("Domingo de Ramos da Paixão do Senhor", "Domingo de Ramos", "216"),
        (2027, 3, 25): ("Quinta-feira da Ceia do Senhor", "Tríduo Pascal", "246"),
        (2027, 3, 26): ("Sexta-feira da Paixão do Senhor", "Tríduo Pascal", "257"),
        (2027, 3, 28): ("Domingo da Páscoa na Ressurreição do Senhor", "Solenidade", "313"),
        (2027, 4, 5): ("Anunciação do Senhor", "Solenidade", "693"),     # transferida da Semana Santa
        (2035, 3, 17): ("São José, Esposo da Bem-aventurada Virgem Maria", "Solenidade", "689"),
        (2028, 3, 20): ("São José, Esposo da Bem-aventurada Virgem Maria", "Solenidade", "689"),
        (2027, 5, 9): ("Ascensão do Senhor", "Solenidade", "358"),
        (2027, 5, 16): ("Domingo de Pentecostes", "Solenidade", "378"),
        (2027, 5, 17): ("Bem-aventurada Virgem Maria, Mãe da Igreja", "Memória", "720"),
        (2027, 5, 23): ("Santíssima Trindade", "Solenidade", "417"),
        (2027, 5, 27): ("Santíssimo Corpo e Sangue de Cristo", "Solenidade", "420"),
        (2027, 6, 4): ("Sagrado Coração de Jesus", "Solenidade", "422"),
        (2022, 6, 23): ("Natividade de São João Batista", "Solenidade", "734"),  # coincidiu com o Sagrado Coração
        (2027, 7, 4): ("Santos Pedro e Paulo, Apóstolos", "Solenidade", "740"),
        (2027, 8, 15): ("Assunção da Bem-aventurada Virgem Maria", "Solenidade", "780"),
        (2028, 8, 20): ("Assunção da Bem-aventurada Virgem Maria", "Solenidade", "780"),
        (2027, 11, 7): ("Todos os Santos", "Solenidade", "842"),
        (2031, 11, 1): ("Todos os Santos", "Solenidade", "842"),         # 2/11 no domingo → sábado
        (2031, 11, 2): ("Comemoração de Todos os Fiéis Defuntos", "Comemoração", "846 / 847 / 848"),
        (2027, 11, 21): ("Nosso Senhor Jesus Cristo, Rei do Universo", "Solenidade", "425"),
        (2027, 11, 28): ("1º Domingo do Advento", "Domingo do Advento", "96"),
        (2030, 12, 9): ("Imaculada Conceição da Bem-aventurada Virgem Maria", "Solenidade", "872"),
        (2033, 12, 30): ("Sagrada Família de Jesus, Maria e José", "Festa", "134"),
        (2027, 2, 7): ("5º Domingo do Tempo Comum", "Domingo do Tempo Comum", "387"),
        (2027, 5, 30): ("9º Domingo do Tempo Comum", "Domingo do Tempo Comum", "391"),
    }
    for (y, m, d), want in expected.items():
        assert day(y, m, d) == want, ((y, m, d), day(y, m, d), want)
    # Festa de santo cede ao domingo; memória cede à Quaresma (só comemoração).
    assert lc.build_entry(date(2027, 4, 25))["celebration"] == "5º Domingo da Páscoa"
    lent = lc.build_entry(date(2027, 3, 8))
    assert lent["grade"] == "Dia de semana" and "comemoração" in lent["note"]

    # O Missal só depende do Ano A/B/C nos 3º, 4º e 5º Domingos da Quaresma (prefácio).
    year_a, year_b = lc.build_entry(date(2029, 3, 4)), lc.build_entry(date(2027, 2, 28))
    assert year_a["cycle"] == "Ano A" and year_a["tapes"][2]["page"] == "187", year_a["tapes"][2]
    assert year_b["cycle"] == "Ano B" and year_b["tapes"][2]["page"] == "459", year_b["tapes"][2]
    assert "p. 187" in str(year_b["tapes"][2]["details"]) and year_b["tapes"][1]["page"] == "186"
    for (y, m, d), page in {(2029, 3, 11): "196", (2029, 3, 18): "204", (2028, 3, 26): "459", (2028, 4, 2): "459"}.items():
        assert lc.build_entry(date(y, m, d))["tapes"][2]["page"] == page, (y, m, d)

    # Outras rubricas que dependem da data.
    pref = lambda y, m, d: lc.build_entry(date(y, m, d))["tapes"][2]["page"]
    assert pref(2027, 1, 2) == "455" and pref(2027, 1, 5) == "458"       # antes / depois da Epifania
    assert pref(2028, 12, 17) == "453" and pref(2027, 12, 12) == "451"   # 3º Dom. do Advento em 17/12
    assert pref(2027, 5, 6) == "466" and pref(2027, 5, 13) == "473"      # antes / depois da Ascensão
    assert lc._kind("Santos Joaquim e Ana, pais da Bem-aventurada Virgem Maria") == "saint"
    assert lc._kind("Nossa Senhora do Carmo") == "mary"

    # 4) Dez anos inteiros: todo dia tem as cinco fitas, página numérica da Missa,
    #    nenhum "?", e passa nas mesmas verificações usadas na publicação.
    current, total = date(2027, 1, 1), 0
    while current < date(2037, 1, 1):
        probe = {}
        ensure_dates(probe, current, 0)
        entry = probe[current.isoformat()]
        repair_entry(entry)
        assert not check_perpetual_day(current.isoformat(), entry), check_perpetual_day(current.isoformat(), entry)
        assert "?" not in entry["quick"], (current, entry["quick"])
        assert _re.fullmatch(r"\d{2,3}( / \d{2,3})*", entry["tapes"][1]["page"]), (current, entry["tapes"][1])
        total += 1
        current += timedelta(days=1)
    assert total == 3653, total
    data2 = {}
    assert ensure_dates(data2, date(2027, 1, 1), 1) == ["2027-01-01", "2027-01-02"]
    assert ensure_dates(data2, date(2027, 1, 1), 1) == [], "Data duplicada"
    print("PASSOU calendário litúrgico perpétuo: 2026 reproduzido, precedências e 10 anos completos sem '?'")


def check_specific_missal_pages():
    """Uma página trocada por outra da mesma seção também deve falhar."""
    path=ROOT/"missal-date-formulary-map.json"
    ref=json.loads(path.read_text(encoding="utf-8"))
    pages=read_js_json(DATA,"window.MISSAL_DATA")
    assert ref["reference_pdf_sha256"] == json.loads(
        (ROOT/"missal-reference-index.json").read_text(encoding="utf-8")
    )["source_pdf_sha256"]
    for key,record in ref["entries"].items():
        assert key in pages,key
        assert pages[key]["tapes"][1]["page"]==record["missal_formulary_page"],key
    original=pages["2026-10-15"]["tapes"][1]["page"]
    assert original=="830",original
    changed="831"
    assert changed!=ref["entries"]["2026-10-15"]["missal_formulary_page"]
    assert len(ref["entries"])>=93
    manifest=json.loads((ROOT/"manifest.webmanifest").read_text(encoding="utf-8"))
    icons={x["src"] for x in manifest["icons"]}
    assert {"app-icon-192.png","app-icon-512.png","app-icon.svg"}<=icons
    print("PASSOU índice litúrgico por celebração e manifesto PWA com PNGs")

def check_corrective_audit_2026():
    """Regras do Missal conferidas e requisitos de acessibilidade/SEO."""
    import json
    data=read_js_json(DATA,"window.MISSAL_DATA")
    seed=json.loads((ROOT/"calendar_seed.json").read_text(encoding="utf-8"))
    rubrics=json.loads((ROOT/"missal-rubrics-verified.json").read_text(encoding="utf-8"))
    assert len(rubrics["blessings"])==4
    for day,rule in rubrics["blessings"].items():
        for entries in (data,seed):
            tape=entries[day]["tapes"][4]
            if not entries[day].get("officialLeafletApplied"):
                assert tape["page"]==str(rule["blessing_page"]),day
                assert tape["suggestion"] is True,day
                assert str(rule["blessing_page"]) in entries[day]["quick"],day
    # Contra erros de data civil, Advento e perda de dados do backup.
    assert data["2026-11-30"]["season"]=="Advento"
    assert seed["2026-11-30"]["season"]=="Advento"
    assert data["2026-12-25"]["tapes"][1]["page"]=="128 / 130 / 132"
    assert data["2026-11-02"]["tapes"][1]["page"]=="846 / 847 / 848"
    assert seed["2026-12-25"]["tapes"][1]["page"]=="128 / 130 / 132"
    assert seed["2026-11-02"]["tapes"][1]["page"]=="846 / 847 / 848"
    for date_key,backup in seed.items():
        original = data[date_key]
        # Os ritos podem vir do folheto mesmo quando outra parte dele não foi
        # identificada (folheto parcial): nesse caso não precisam bater com o backup.
        rites_from_leaflet = bool(original["tapes"][0].get("verifiedByFolheto")
                                  or original["tapes"][0].get("ritesOfficialUrl"))
        if (not original.get("officialLeafletApplied") and not original.get("ritesPendingOfficial")
                and not rites_from_leaflet):
            assert backup["tapes"][0]["details"]==original["tapes"][0]["details"], date_key
        for line in backup["tapes"][0]["details"]:
            assert "Consultar o texto integral no Missal Romano" not in str(line[1]), date_key
    assert "function scheduleNextFiveAMRelease()" in INDEX.read_text(encoding="utf-8")
    assert "dateChangeAnnouncement" in INDEX.read_text(encoding="utf-8")
    assert "aria-modal" in INDEX.read_text(encoding="utf-8")
    assert data["2026-11-02"]["tapes"][4]["page"]=="588"
    for entries in (data, seed):
        finados_blessing=entries["2026-11-02"]["tapes"][4]
        assert finados_blessing["page"]=="588"
        assert finados_blessing["title"]=="Bênção Solene — Celebração pelos Fiéis Defuntos"
    if data["2026-11-02"].get("folhetoUrl"):
        # O folheto de Finados (02/11/2026) indica "BÊNÇÃO FINAL — MR, p. 588":
        # é indicação oficial, não sugestão.
        finados=data["2026-11-02"]["tapes"][4]
        assert finados.get("verifiedByFolheto") is True and not finados.get("suggestion")
        assert "indicada no folheto" in str(finados.get("details", [])).lower()
    assert data["2026-10-28"]["tapes"][4]["page"]=="586"
    assert data["2026-11-30"]["tapes"][4]["page"]=="586"
    assert data["2026-12-12"]["tapes"][4]["page"]=="585"
    idx=INDEX.read_text(encoding="utf-8")
    standalone=STANDALONE.read_text(encoding="utf-8")
    assert '<main id="mainContent">' in idx and '</main>' in idx
    assert '<footer class="footer">' in idx and '</footer>' in idx
    assert '<meta name="description"' in idx and 'rel="canonical"' in idx
    assert 'property="og:image"' in idx
    assert 'id="mobileMoreSheet" role="dialog" aria-modal="true"' in idx
    assert "event.key!==\"Tab\"" in idx and "last.focus()" in idx
    assert 'quick-markers-mobile-grid-v76' in idx
    assert '<img src="brand-logo.png"' in idx and '<img src="data:image/png;base64,' in standalone
    assert 'brand-logo.webp' in idx and 'brand-logo.webp' not in standalone
    assert 'app-icon-512.png' in idx
    assert 'technical-checks-passed' in (ROOT/"status.js").read_text(encoding="utf-8")
    assert len((ROOT/"brand-logo.png").read_bytes()) > 1000
    assert (ROOT/"robots.txt").exists() and (ROOT/"sitemap.xml").exists()
    sw=(ROOT/"sw.js").read_text(encoding="utf-8")
    for icon in ("app-icon-180.png","app-icon-192.png","app-icon-512.png","brand-logo.png"):
        assert icon in sw
    print("PASSOU correções de liturgia, SEO, landmarks, logo e menu mobile")

def check_leaflet_ocr_tolerance():
    """Erros reais de OCR dos folhetos escaneados não podem impedir a leitura."""
    import importlib, sys as _sys
    _sys.path.insert(0, str(ROOT / "scripts"))
    u = importlib.import_module("update_folheto")
    casos = {
        # 08/11/2026: "EUCARIÍSTICA", "Ill" e "M." no lugar de "MR"
        "ORAÇÃO EUCARIÍSTICA Ill - M., p.545 - Prefácio dos domingos do Tempo Comum X: A ação do Espirito Santo na Igreja - MR., p.483": ("545", "483"),
        "ORAÇÃO EUCARÍSTICA II – MR, p. 536\nPrefácio Comum IV – MR, p. 512": ("536", "512"),
        "ORACAO EUCARISTICA I - M R p 523. Prefácio da Quaresma I - UR, p.459": ("523", "459"),
        "ORAÇÃO EUCARÍSTICA IV — MR, p. 554": ("554", "554"),
        # nome do prefácio truncado: a página identifica
        "ORAÇÃO EUCARÍSTICA III - MR, p. 545 - Prefácio dos domin - MR, p. 516": ("545", "516"),
    }
    for texto, (oe_page, pref_page) in casos.items():
        pref, oe = u.leaflet_oe_prefacio(texto)
        assert oe and oe[1] == oe_page, (texto, oe)
        assert pref and pref[1] == pref_page, (texto, pref)
    assert u.detect_acclamation("Mistério da fé para a salvação do mun-\ndo!") == "Mistério da fé para a salvação do mundo!"
    assert u.detect_acclamation("Mistério da fé para a salvação do mun do!") == "Mistério da fé para a salvação do mundo!"
    # Todos os prefácios do Ordinário do Missal (p. 451–522) estão conferidos.
    import json
    pref = json.loads((ROOT / "missal-prefaces-verified.json").read_text(encoding="utf-8"))["prefaces"]
    assert len(pref) >= 72, len(pref)
    print("PASSOU folheto: leitura tolerante a erros de OCR e lista completa de prefácios")


def check_design_v3():
    """Design v3 (11/2026): a tela nova usa as rotinas existentes e mantém o que o autor pediu."""
    html=INDEX.read_text(encoding="utf-8")
    start=html.index("<!-- design-v3:início -->"); end=html.index("<!-- design-v3:fim -->")
    markup=html[start:end]
    script=html[html.index('<script id="design-v3-js">'):]
    style=html[html.index('<style id="design-v3">'):html.index("</head>")]
    assert "if(window.v3Render) window.v3Render(dateKey);" in html,"render() deve atualizar a tela nova"
    for tab in ("cel","cal","home","leaflet","more"):
        assert f'data-v3-tab="{tab}"' in markup,f"aba ausente na barra: {tab}"
    order=[markup.index(f'data-v3-tab="{t}"') for t in ("cel","cal","home","leaflet","more")]
    assert order==sorted(order),"Início deve ficar no centro da barra"
    assert "Preparar o Missal" not in markup and "prepare" not in markup.lower(),"Preparação rápida foi removida do design novo"
    assert 'href="mailto:macflay.contact@gmail.com"' in markup and "instagram.com/macflayyy" in markup,"contatos do autor no rodapé"
    assert "Site criado por Ronielly Macflay" in markup
    for label in ("Conferido no folheto","Própria do dia","Missa do domingo da semana","Sugestão"):
        assert label in script,f"etiqueta de origem ausente: {label}"
    assert "window.buildShareImageBlob=v3ShareImage" in script,"imagem gerada deve seguir o visual novo"
    assert "getVisibleDates()" in script and "getSundayPreview()" in script,"a semana e o calendário respeitam a liberação das 05h"
    assert "december24Choice=b.dataset.dec24Mass" in script,"24/12 continua exigindo escolha explícita"
    assert "body.v3 .shell" in style and "prefers-reduced-motion" in style
    assert "--v-num:#fff" in style,"números brancos no modo escuro"
    assert "-webkit-text-stroke:1.2px" in style,"título do dia com traço reforçado"
    standalone=STANDALONE.read_text(encoding="utf-8")
    assert 'id="design-v3-js"' in standalone and "<!-- design-v3:início -->" in standalone,"standalone deve trazer o design novo"
    print("PASSOU design v3: barra, etiquetas, contatos, imagem e regras de liberação preservadas")

def main():
    verify_html(INDEX)
    verify_html(STANDALONE,standalone=True)
    check_saturday_preview()
    check_liturgical_integrity()
    check_leaflet_fallback()
    check_update_safety()
    check_cache_safety()
    check_christmas_choice()
    check_corrective_audit_2026()
    check_leaflet_ocr_tolerance()
    check_specific_missal_pages()
    check_rites_texts()
    check_official_leaflet_extraction()
    check_filename_filter_and_ocr()
    check_only_openings_from_folheto()
    check_verified_leaflet_days()
    check_folheto_gap_fallbacks()
    check_incomplete_leaflet_variant_protection()
    check_on_demand_calendar()
    check_pending_page_copy()
    check_known_sunday_page_survives_leaflet_ocr()
    check_design_v3()
    print("TODOS OS TESTES PASSARAM")

if __name__=="__main__":
    main()
