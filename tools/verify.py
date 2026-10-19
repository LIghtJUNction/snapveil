#!/usr/bin/env python3
"""Inspect the real Kam ZIP and its nested APK; fail if a release contract is broken."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path, PurePosixPath
import stat
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    prop = tomllib.loads((ROOT / "kam.toml").read_text())["prop"]
    artifact = ROOT / "dist" / f"snapveil-{prop['version']}.zip"
    required = {"module.prop", "customize.sh", "service.sh", "uninstall.sh", "action.sh", "cli",
                "lib/common.sh", "skip_mount", "app/snapveil.apk", "app/snapveil.apk.sha256",
                "META-INF/com/google/android/update-binary", "META-INF/com/google/android/updater-script"}
    with zipfile.ZipFile(artifact) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP entries")
        if missing := required - set(names):
            raise ValueError(f"Missing package files: {sorted(missing)}")
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Unsafe ZIP path: {path}")
            if set(path.parts) & {".git", ".github", ".cache", ".local", "state", "captures"}:
                raise ValueError(f"Source or private data in flashable ZIP: {path}")
            if path.suffix in {".p12", ".jks", ".keystore"}:
                raise ValueError("A signing key was included in the flashable ZIP")
            if info.filename.endswith(".sh") or info.filename in {"cli", "META-INF/com/google/android/update-binary"}:
                if not (info.external_attr >> 16) & stat.S_IXUSR:
                    raise ValueError(f"Runtime script lacks executable bit: {path}")
                if b"\r" in archive.read(info.filename):
                    raise ValueError(f"CRLF in Android shell script: {path}")
        metadata = dict(line.split("=", 1) for line in archive.read("module.prop").decode().splitlines()
                        if "=" in line and not line.startswith("#"))
        for key in ("id", "version", "versionCode", "author", "description"):
            if metadata.get(key) != str(prop[key]):
                raise ValueError(f"module.prop {key} does not match kam.toml")
        if not 1 <= int(metadata["versionCode"]) <= 2_100_000_000:
            raise ValueError("Invalid versionCode")
        apk_data = archive.read("app/snapveil.apk")
        apk_hash = hashlib.sha256(apk_data).hexdigest()
        expected = archive.read("app/snapveil.apk.sha256").decode().split()[0]
        if apk_hash != expected:
            raise ValueError("Companion APK checksum mismatch")
        with zipfile.ZipFile(BytesIO(apk_data)) as apk:
            for name in ("AndroidManifest.xml", "classes.dex", "assets/xposed_init"):
                if name not in apk.namelist():
                    raise ValueError(f"Companion missing {name}")
            if any(name.startswith("de/robv/") for name in apk.namelist()):
                raise ValueError("Compile-only Xposed implementation was bundled")
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
    print(f"Verified {artifact.name}: root metadata, runtime scripts, APK, checksum, and no private data")


if __name__ == "__main__":
    main()
