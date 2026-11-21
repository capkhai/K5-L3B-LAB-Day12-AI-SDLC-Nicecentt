"""Đóng gói bản phát hành chạy được cho GitHub Release v1.0.0 (`dist/chonoi-v1.0.0.zip` & `.tar.gz`)."""

import os
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
INCLUDE_FILES = [
    "README.md",
    "CHANGELOG.md",
    "CREDITS.md",
    "LICENSE",
    "TEAM.md",
    "game.contract.json",
]
INCLUDE_DIRS = ["chonoi"]


def iter_release_files():
    for rel in INCLUDE_FILES:
        p = ROOT / rel
        if p.is_file():
            yield p, rel
    for d in INCLUDE_DIRS:
        base = ROOT / d
        for path in sorted(base.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                yield path, path.relative_to(ROOT).as_posix()


def build_release(version="v1.0.0"):
    DIST.mkdir(exist_ok=True)
    zip_path = DIST / f"chonoi-{version}.zip"
    tgz_path = DIST / f"chonoi-{version}.tar.gz"
    prefix = f"chonoi-{version}/"

    files = list(iter_release_files())
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, rel in files:
            zf.write(src, prefix + rel)
    with tarfile.open(tgz_path, "w:gz") as tf:
        for src, rel in files:
            tf.add(src, arcname=prefix + rel)

    print(f"Created {zip_path} ({zip_path.stat().st_size} bytes)")
    print(f"Created {tgz_path} ({tgz_path.stat().st_size} bytes)")


if __name__ == "__main__":
    build_release()
