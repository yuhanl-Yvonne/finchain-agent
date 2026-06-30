#!/usr/bin/env python3
"""Download and install SimSun on macOS for Matplotlib use.

This script:
1. Tries one or more public GitHub raw URLs for SimSun.ttf/ttc.
2. Copies the font into ~/Library/Fonts/.
3. Removes Matplotlib cached font list files to force a rescan.
4. Prints a short Matplotlib test snippet.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import ssl
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


FONT_URLS = [
    "https://raw.githubusercontent.com/StellarCN/scp_zh/master/fonts/SimSun.ttf",
    "https://raw.githubusercontent.com/chenyuntc/pytorch-book/master/docs/SimSun.ttf",
]

FONT_FILENAME = "SimSun.ttf"


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def download_first_working(urls: list[str], dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for idx, url in enumerate(urls, start=1):
        target = dest_dir / f"downloaded_font_{idx}"
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) Python Font Installer",
                    "Accept": "*/*",
                },
            )
            try:
                with urlopen(req, timeout=30) as resp, open(target, "wb") as f:
                    shutil.copyfileobj(resp, f)
            except Exception as exc:
                if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
                    raise
                eprint(f"[WARN] Certificate verification failed for {url}; retrying with SSL fallback.")
                insecure_ctx = ssl._create_unverified_context()
                with urlopen(req, context=insecure_ctx, timeout=30) as resp, open(target, "wb") as f:
                    shutil.copyfileobj(resp, f)

            if target.stat().st_size < 1024:
                raise RuntimeError(f"Downloaded file is too small: {target.stat().st_size} bytes")

            return target
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            eprint(f"[WARN] Failed to download from {url}: {exc}")
            if target.exists():
                try:
                    target.unlink()
                except OSError:
                    pass

    raise RuntimeError(f"All download URLs failed. Last error: {last_error}")


def install_font(font_path: Path) -> Path:
    fonts_dir = Path.home() / "Library" / "Fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    if not fonts_dir.exists():
        raise FileNotFoundError(f"Font directory does not exist and could not be created: {fonts_dir}")

    target_path = fonts_dir / FONT_FILENAME
    shutil.copy2(font_path, target_path)
    if not target_path.exists() or target_path.stat().st_size == 0:
        raise RuntimeError(f"Font install failed: {target_path}")
    return target_path


def clear_matplotlib_font_cache() -> list[Path]:
    removed: list[Path] = []
    try:
        import matplotlib
    except Exception as exc:
        eprint(f"[WARN] Matplotlib is not available, skipping cache cleanup: {exc}")
        return removed

    cache_dir = Path(matplotlib.get_cachedir())
    if not cache_dir.exists():
        eprint(f"[WARN] Matplotlib cache directory not found: {cache_dir}")
        return removed

    for path in cache_dir.glob("fontlist-*.json"):
        try:
            path.unlink()
            removed.append(path)
        except OSError as exc:
            eprint(f"[WARN] Could not remove {path}: {exc}")
    return removed


def sha256sum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def print_test_snippet() -> None:
    print("\n" + "=" * 72)
    print("Matplotlib 测试代码：")
    print("=" * 72)
    print(
        """import matplotlib.pyplot as plt
import matplotlib as mpl

mpl.rcParams['font.sans-serif'] = ['SimSun']
mpl.rcParams['axes.unicode_minus'] = False

plt.figure(figsize=(6, 4))
plt.plot([1, 2, 3], [1, -2, 3], marker='o')
plt.title('SimSun 字体测试')
plt.xlabel('横轴')
plt.ylabel('纵轴')
plt.tight_layout()
plt.show()
"""
    )


def main() -> int:
    print("[INFO] Downloading SimSun font...")
    with tempfile.TemporaryDirectory(prefix="simsun_install_") as tmp:
        tmp_dir = Path(tmp)
        downloaded = download_first_working(FONT_URLS, tmp_dir)
        print(f"[INFO] Downloaded: {downloaded}")
        print(f"[INFO] SHA256: {sha256sum(downloaded)}")

        installed = install_font(downloaded)
        print(f"[INFO] Installed to: {installed}")

        removed = clear_matplotlib_font_cache()
        if removed:
            print("[INFO] Removed Matplotlib font cache files:")
            for p in removed:
                print(f"  - {p}")
        else:
            print("[INFO] No Matplotlib font cache files found or Matplotlib unavailable.")

    print_test_snippet()
    print("\n[INFO] Done. Restart Python or Jupyter kernel before re-checking Matplotlib fonts.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        eprint("\n[ERROR] Cancelled by user.")
        raise SystemExit(130)
    except Exception as exc:
        eprint(f"[ERROR] {exc}")
        raise SystemExit(1)
