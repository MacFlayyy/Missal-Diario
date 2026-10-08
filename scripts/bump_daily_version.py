#!/usr/bin/env python3
"""Versão diária pelo conteúdo: sem cache obsoleto nem commits redundantes."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
SW = ROOT / "sw.js"
TZ = ZoneInfo("America/Sao_Paulo")

def main():
    html = INDEX.read_text(encoding="utf-8")
    sw = SW.read_text(encoding="utf-8")
    clean_html = re.sub(r'((?:data|status)\.js\?v=)[^"]+', r'\1', html)
    clean_html = re.sub(r'(\./sw\.js\?v=)[^"\']+', r'\1', clean_html)
    clean_sw = re.sub(
        r'const CACHE_NAME = "missal-diario-[^"]+";',
        'const CACHE_NAME = "missal-diario-VERSION";', sw
    )
    payload = clean_html + clean_sw + (
        ROOT / "data.js"
    ).read_text(encoding="utf-8") + (
        ROOT / "status.js"
    ).read_text(encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    token = datetime.now(TZ).strftime("%Y%m%d") + "-" + digest

    html = re.sub(
        r'<script src="data\.js(?:\?[^"]*)?"></script>',
        f'<script src="data.js?v={token}"></script>', html,
    )
    html = re.sub(
        r'<script src="status\.js(?:\?[^"]*)?"></script>',
        f'<script src="status.js?v={token}"></script>', html,
    )
    html = re.sub(
        r'\./sw\.js\?v=[^"\']+', f'./sw.js?v={token}', html,
    )
    INDEX.write_text(html, encoding="utf-8")

    sw = re.sub(
        r'const CACHE_NAME = "missal-diario-[^"]+";',
        f'const CACHE_NAME = "missal-diario-{token}";', sw,
    )
    SW.write_text(sw, encoding="utf-8")
    print(f"Versão aplicada: {token}")

if __name__ == "__main__":
    main()
