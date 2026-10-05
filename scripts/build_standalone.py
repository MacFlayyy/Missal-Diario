#!/usr/bin/env python3
"""Gera a versão HTML única usada para abrir o Missal dentro do ChatGPT."""

from pathlib import Path
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

    html = html.replace(
        '<script src="data.js"></script>',
        '<script>\n' + data + '\n</script>'
    )
    html = html.replace(
        '<script src="status.js"></script>',
        '<script>\n' + status + '\n</script>'
    )

    # Recursos locais do PWA não são necessários no visualizador HTML.
    html = re.sub(r'\s*<link rel="manifest" href="manifest\.webmanifest"\s*/?>', '', html)
    html = re.sub(r'\s*<link rel="icon" href="app-icon\.svg"[^>]*>', '', html)
    html = re.sub(r'\s*<link rel="apple-touch-icon" href="app-icon\.svg"\s*/?>', '', html)

    # O standalone não registra service worker relativo.
    html = html.replace(
        'if("serviceWorker" in navigator){',
        'if(false && "serviceWorker" in navigator){'
    )
    html = html.replace(
        'if(location.protocol !== "file:" && "serviceWorker" in navigator){',
        'if(false && "serviceWorker" in navigator){'
    )

    marker = '<!-- Versão standalone: dados e status incorporados no próprio HTML -->'
    if marker not in html:
        html = html.replace(
            '<title>Missal Diário</title>',
            '<title>Missal Diário</title>\n  ' + marker
        )

    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Standalone atualizado: {OUTPUT.name}")


if __name__ == "__main__":
    main()
