#!/usr/bin/env python3
"""Confere no GitHub Pages se os arquivos públicos já são os do dia."""

from datetime import datetime
from zoneinfo import ZoneInfo
import json
import re
import time
from urllib.request import Request, urlopen

TZ = ZoneInfo("America/Sao_Paulo")
BASE = "https://macflayyy.github.io/Missal-Diario"


def fetch(path, attempt):
    url = f"{BASE}/{path}?health={int(time.time())}-{attempt}"
    req = Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "MissalDiarioHealth/1.0"})
    with urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def status_date(raw):
    m = re.search(r'window\.MISSAL_STATUS\s*=\s*(\{.*\})\s*;\s*$', raw, re.S)
    if not m:
        return ""
    return str(json.loads(m.group(1)).get("availableThrough") or "")


def main():
    today = datetime.now(TZ).strftime("%Y-%m-%d")

    for attempt in range(1, 7):
        try:
            status_raw = fetch("status.js", attempt)
            data_raw = fetch("data.js", attempt)
            if status_date(status_raw) == today and f'"{today}"' in data_raw:
                print(f"GitHub Pages confirmado para {today} na tentativa {attempt}.")
                return
            print(f"Tentativa {attempt}: Pages ainda não refletiu {today}.")
        except Exception as exc:
            print(f"Tentativa {attempt}: {exc}")

        if attempt < 6:
            time.sleep(10)

    raise SystemExit(f"GitHub Pages ainda não publicou corretamente {today}.")


if __name__ == "__main__":
    main()
