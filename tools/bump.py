#!/usr/bin/env python3
"""Bump the module and APK together, once, without timestamp overflow."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")


def next_version(current: str, requested: str) -> str:
    match = VERSION.fullmatch(current)
    if not match:
        raise ValueError("Current version must be a three-part release version")
    parts = tuple(map(int, match.groups()))
    if requested in ("major", "minor", "patch"):
        major, minor, patch = parts
        return {"major": f"v{major + 1}.0.0", "minor": f"v{major}.{minor + 1}.0",
                "patch": f"v{major}.{minor}.{patch + 1}"}[requested]
    match = VERSION.fullmatch(requested)
    if not match or tuple(map(int, match.groups())) <= parts:
        raise ValueError("The new version must be a greater X.Y.Z version")
    return "v" + requested.removeprefix("v")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="major, minor, patch, or an explicit X.Y.Z")
    args = parser.parse_args()
    config = ROOT / "kam.toml"
    old_text = config.read_text()
    prop = tomllib.loads(old_text)["prop"]
    version = next_version(prop["version"], args.version)
    code = prop["versionCode"] + 1
    if not 1 < code <= 2_100_000_000:
        raise ValueError("Next versionCode would exceed the Android APK limit")
    # Restrict replacements to the authoritative [prop] section.
    start = old_text.index("[prop]") + len("[prop]")
    next_section = re.search(r"^\[", old_text[start:], re.M)
    end = start + next_section.start() if next_section else len(old_text)
    section = old_text[start:end]
    section, n_version = re.subn(r'^version\s*=.*$', f'version = "{version}"', section, flags=re.M)
    section, n_code = re.subn(r'^versionCode\s*=.*$', f'versionCode = {code}', section, flags=re.M)
    if (n_version, n_code) != (1, 1):
        raise ValueError("Expected one version and versionCode in [prop]")
    new_text = old_text[:start] + section + old_text[end:]
    metadata = ROOT / "src/snapveil/module.prop"
    old_metadata = metadata.read_bytes() if metadata.exists() else None
    config.write_text(new_text)
    try:
        subprocess.run(["kam", "export", "prop", "src/snapveil/module.prop"], cwd=ROOT, check=True)
    except (OSError, subprocess.CalledProcessError):
        config.write_text(old_text)
        if old_metadata is None:
            metadata.unlink(missing_ok=True)
        else:
            metadata.write_bytes(old_metadata)
        raise
    print(f"{prop['version']} -> {version}; versionCode {prop['versionCode']} -> {code}")


if __name__ == "__main__":
    main()
