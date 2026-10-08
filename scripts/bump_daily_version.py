#!/usr/bin/env python3
"""Atualiza a versão diária dos recursos para evitar cache antigo no site/PWA."""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
SW = ROOT / "sw.js"
TZ = ZoneInfo("America/Sao_Paulo")


def main():
    token = datetime.now(TZ).strftime("%Y%m%d")

    html = INDEX.read_text(encoding="utf-8")
    html = re.sub(
        r'<script src="data\.js(?:\?[^"]*)?"></script>',
        f'<script src="data.js?v={token}"></script>',
        html,
    )
    html = re.sub(
        r'<script src="status\.js(?:\?[^"]*)?"></script>',
        f'<script src="status.js?v={token}"></script>',
        html,
    )
    html = re.sub(
        r'\.\/sw\.js\?v=[^"\']+',
        f'./sw.js?v={token}',
        html,
    )
    INDEX.write_text(html, encoding="utf-8")

    sw = SW.read_text(encoding="utf-8")
    sw = re.sub(
        r'const CACHE_NAME = "missal-diario-[^"]+";',
        f'const CACHE_NAME = "missal-diario-{token}";',
        sw,
    )
    SW.write_text(sw, encoding="utf-8")

    print(f"Versão diária aplicada: {token}")


if __name__ == "__main__":
    main()
