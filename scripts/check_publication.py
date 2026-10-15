#!/usr/bin/env python3
"""Valida publicação pública da versão correta (dados, status e HTML), não só HTTP 200."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("America/Sao_Paulo")
BASE = "https://macflayyy.github.io/Missal-Diario"


def fetch(path, attempt):
    url = f"{BASE}/{path}?health={int(time.time())}-{attempt}"
    req = Request(url, headers={
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": "MissalDiarioHealth/2.0",
    })
    with urlopen(req, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"{path}: HTTP {response.status}")
        return response.read().decode("utf-8", errors="replace")


def status_obj(raw):
    m = re.search(r'window\.MISSAL_STATUS\s*=\s*(\{.*\})\s*;\s*$', raw, re.S)
    if not m:
        raise RuntimeError("status.js inválido ou vazio")
    return json.loads(m.group(1))


def app_version(raw):
    m = re.search(r'<script\s+src="data\.js\?v=([^"]+)"', raw, re.I)
    if not m:
        raise RuntimeError("index.html não contém versão dos dados")
    return m.group(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expected-from-local", action="store_true",
        help="Validar contra o commit que está sendo implantado, inclusive antes das 05h."
    )
    args = parser.parse_args()
    local_status = status_obj((ROOT / "status.js").read_text(encoding="utf-8"))
    local_date = str(local_status.get("availableThrough") or "")
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    expected_date = local_date if args.expected_from_local else today
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", expected_date):
        raise SystemExit(f"Data esperada inválida: {expected_date!r}")
    if not args.expected_from_local and local_date != expected_date:
        raise SystemExit(
            f"Dados locais desatualizados: status {local_date}, esperado {expected_date}"
        )
    expected_version = app_version((ROOT / "index.html").read_text(encoding="utf-8"))
    expected_data = (ROOT / "data.js").read_text(encoding="utf-8")
    if f'"{expected_date}"' not in expected_data:
        raise SystemExit(f"data.js local não contém a data de publicação {expected_date}")

    for attempt in range(1, 7):
        try:
            remote_status = status_obj(fetch("status.js", attempt))
            remote_date = remote_status.get("availableThrough")
            remote_data = fetch("data.js", attempt)
            remote_html = fetch("index.html", attempt)
            actual_version = app_version(remote_html)
            # Uma URL HTTP 200 com a data certa não basta: uma publicação
            # parcial pode misturar HTML novo, status antigo e data.js obsoleto.
            # Os arquivos remotos precisam corresponder aos revisados no job.
            ok = (
                remote_date == expected_date
                and remote_status == local_status
                and remote_data == expected_data
                and actual_version == expected_version
            )
            if ok:
                # Não confirmar PWA enquanto faltar o ícone Android/iOS publicado.
                icons = ("app-icon-180.png", "app-icon-192.png", "app-icon-512.png")
                for icon_name in icons:
                    icon_url = f"{BASE}/{icon_name}?health={int(time.time())}-{attempt}"
                    req = Request(icon_url, method="HEAD", headers={"Cache-Control":"no-cache"})
                    with urlopen(req, timeout=18) as icon_response:
                        icon_type = str(icon_response.headers.get("Content-Type","")).lower()
                        if icon_response.status != 200 or "image/png" not in icon_type:
                            raise RuntimeError(
                                f"Ícone PWA {icon_name} ausente ou inválido: "
                                f"HTTP {icon_response.status}, {icon_type}"
                            )
                logo_req = Request(
                    f"{BASE}/brand-logo.webp?health={int(time.time())}-{attempt}",
                    method="HEAD", headers={"Cache-Control": "no-cache"}
                )
                with urlopen(logo_req,timeout=18) as logo_res:
                    if logo_res.status!=200 or "image/webp" not in str(logo_res.headers.get("Content-Type","")).lower():
                        raise RuntimeError("Logo WebP não publicada corretamente.")
                print(
                    f"GitHub Pages confirmado: {expected_date}, versão "
                    f"{expected_version}, tentativa {attempt}; PNGs e logo WebP disponíveis."
                )
                return
            print(
                f"Tentativa {attempt}: status={remote_date}, "
                f"versão={actual_version}, esperado={expected_version}; "
                f"status idêntico={remote_status == local_status}; "
                f"dados idênticos={remote_data == expected_data}."
            )
        except Exception as exc:
            print(f"Tentativa {attempt}: {exc}")

        if attempt < 6:
            time.sleep(10)

    raise SystemExit(
        f"GitHub Pages não confirmou a data {expected_date} "
        f"e a versão {expected_version}."
    )


if __name__ == "__main__":
    main()
