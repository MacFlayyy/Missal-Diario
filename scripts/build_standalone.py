#!/usr/bin/env python3
"""Cria um HTML autossuficiente para visualização e arquivo do Missal Diário."""
from pathlib import Path
import base64
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
DATA = ROOT / "data.js"
STATUS = ROOT / "status.js"
OUTPUT = ROOT / "Missal-Diario-Standalone.html"

def main():
    html = INDEX.read_text(encoding="utf-8")
    data = DATA.read_text(encoding="utf-8").strip()
    status = STATUS.read_text(encoding="utf-8").strip()

    # O site online usa um logo PNG externo, armazenável em cache;
    # a versão HTML para abrir no chat incorpora o mesmo PNG para ser autossuficiente.
    logo_file = ROOT / "brand-logo.png"
    if not logo_file.is_file():
        raise RuntimeError("Logo original do site ausente")
    logo_b64 = base64.b64encode(logo_file.read_bytes()).decode("ascii")
    html, found = re.subn(
        r'(<img[^>]*\bsrc=")brand-logo\.png(")',
        lambda m: m.group(1) + "data:image/png;base64," + logo_b64 + m.group(2),
        html, count=1,
    )
    if found != 1:
        raise RuntimeError("Não foi possível incorporar a logomarca à versão completa")

    for name, contents in (("data.js", data), ("status.js", status)):
        pattern = r'<script\s+src="' + re.escape(name) + r'(?:\?[^"]*)?"\s*></script>'
        html, replacements = re.subn(
            pattern, lambda _m: "<script>\n" + contents + "\n</script>",
            html, count=1, flags=re.I,
        )
        if replacements != 1:
            raise RuntimeError(f"Falha ao incorporar {name}: encontrado {replacements} vezes")

    # HTML avulso precisa usar PNG incorporado, não o WebP externo.
    html = re.sub(
        r'<source[^>]*srcset="brand-logo\.webp"[^>]*>',
        "", html, flags=re.I
    )

    for tag in (
        r'<link\s+rel="manifest"\s+href="manifest\.webmanifest"\s*/?>',
        r'<link\s+rel="icon"\s+href="app-icon\.svg"[^>]*>',
        r'<link\s+rel="apple-touch-icon"[^>]*>',
    ):
        html = re.sub(tag, "", html, flags=re.I)

    # O arquivo é aberto localmente e não pode registrar o SW do GitHub Pages.
    html = html.replace(
        'if("serviceWorker" in navigator){',
        'if(false && "serviceWorker" in navigator){'
    )

    marker = '<!-- Versão standalone: dados e status incorporados no próprio HTML -->'
    if marker not in html:
        html = html.replace('<title>Missal Diário</title>',
                            '<title>Missal Diário</title>\n  ' + marker)

    if 'src="data.js' in html or 'src="status.js' in html:
        raise RuntimeError("HTML gerado ainda depende de dados externos")
    if html.count("window.MISSAL_DATA =") != 1 or html.count("window.MISSAL_STATUS =") != 1:
        raise RuntimeError("Dados/status ausentes ou repetidos no HTML")
    if not html.strip().endswith("</html>"):
        raise RuntimeError("HTML gerado não termina com </html>")
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"HTML autossuficiente gerado: {OUTPUT.name} ({OUTPUT.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
