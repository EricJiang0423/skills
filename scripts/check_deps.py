#!/usr/bin/env python3
"""Check trip-design runtime dependencies. Output JSON status to stdout."""
import json
import shutil
import subprocess
import sys
from importlib import metadata


PYTHON_PACKAGES = [
    ("exiftool", "PyExifTool", ">=0.5.6"),
    ("osxphotos", "osxphotos", ">=0.68.0"),
    ("geopy", "geopy", ">=2.4.0"),
    ("PIL", "Pillow", ">=10.0.0"),
]

SYSTEM_BINARIES = [
    ("exiftool", "brew install exiftool",
     "EXIF / HEIC / RAW 提取的核心二进制"),
]

SYSTEM_LIBRARIES = [
    ("libheif", "brew install libheif",
     "HEIC 解码（Pillow 通过 pyheif/pillow-heif 调用）"),
]


def check_python_package(import_name, dist_name):
    try:
        __import__(import_name)
    except ImportError:
        return None
    try:
        return metadata.version(dist_name)
    except metadata.PackageNotFoundError:
        return "unknown"


def check_binary(name):
    return shutil.which(name) is not None


def check_libheif():
    if not shutil.which("brew"):
        return None
    try:
        result = subprocess.run(
            ["brew", "list", "libheif"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return None


def main():
    report = {
        "ok": True,
        "python": {},
        "binaries": {},
        "libraries": {},
        "install_commands": [],
    }

    pip_missing = []
    for import_name, dist_name, spec in PYTHON_PACKAGES:
        version = check_python_package(import_name, dist_name)
        report["python"][dist_name] = {
            "installed": version is not None,
            "version": version,
            "spec": spec,
        }
        if version is None:
            pip_missing.append(f"{dist_name}{spec}")
            report["ok"] = False

    if pip_missing:
        report["install_commands"].append(
            "pip install " + " ".join(f"'{p}'" for p in pip_missing)
        )

    for name, install_cmd, desc in SYSTEM_BINARIES:
        present = check_binary(name)
        report["binaries"][name] = {
            "installed": present,
            "description": desc,
        }
        if not present:
            report["install_commands"].append(install_cmd)
            report["ok"] = False

    for name, install_cmd, desc in SYSTEM_LIBRARIES:
        present = check_libheif() if name == "libheif" else None
        report["libraries"][name] = {
            "installed": present,
            "description": desc,
            "note": "未检测到 brew 时无法判断；HEIC 解码失败再装也可" if present is None else None,
        }
        if present is False:
            report["install_commands"].append(install_cmd)

    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
