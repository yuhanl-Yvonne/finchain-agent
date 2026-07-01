#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path

from backend.repository import DemoRepository


ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
SITE_DIR = ROOT_DIR / "site"
DATA_DIR = SITE_DIR / "data"
COMPANY_DIR = DATA_DIR / "company"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_frontend_assets() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FRONTEND_DIR / "index.html", SITE_DIR / "index.html")
    shutil.copy2(FRONTEND_DIR / "styles.css", SITE_DIR / "styles.css")
    shutil.copy2(FRONTEND_DIR / "app.js", SITE_DIR / "app.js")
    frontend_assets_dir = FRONTEND_DIR / "assets"
    if frontend_assets_dir.exists():
        shutil.copytree(frontend_assets_dir, SITE_DIR / "assets", dirs_exist_ok=True)
    index_path = SITE_DIR / "index.html"
    html = index_path.read_text(encoding="utf-8")
    html = html.replace('window.APP_DATA_MODE = window.APP_DATA_MODE || "api";', 'window.APP_DATA_MODE = window.APP_DATA_MODE || "static";')
    index_path.write_text(html, encoding="utf-8")


def build_site() -> None:
    repository = DemoRepository.load()
    payloads = repository.export_static_payloads()

    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)

    copy_frontend_assets()
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
    write_json(DATA_DIR / "summary.json", payloads["summary"])
    write_json(DATA_DIR / "companies.json", payloads["companies"])

    for company_id, detail in payloads["company_details"].items():
        write_json(COMPANY_DIR / f"{company_id}.json", detail)

    print(f"Static site generated at {SITE_DIR}")


if __name__ == "__main__":
    build_site()
