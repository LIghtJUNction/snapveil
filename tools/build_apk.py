#!/usr/bin/env python3
"""Build the small Java companion with official Android SDK tools, without Gradle."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tomllib
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SDK_VERSION = "35.0.0"
XPOSED_URL = "https://api.xposed.info/de/robv/android/xposed/api/82/api-82.jar"
XPOSED_SHA256 = "f48c635f1c7469fdec0e00ad2ea0b7a6b2f5b55065784a35b7ca3a84615e8e25"


def run(*args: object, **kwargs: object) -> None:
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    prop = tomllib.loads((ROOT / "kam.toml").read_text())["prop"]
    if not 1 <= prop["versionCode"] <= 2_100_000_000:
        raise SystemExit("versionCode must fit Android APK limits: 1..2100000000")
    sdk_value = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk_value:
        raise SystemExit("Set ANDROID_HOME to an SDK with platforms;android-35 and build-tools;35.0.0")
    sdk = Path(sdk_value).resolve()
    android_jar = sdk / "platforms/android-35/android.jar"
    sdk_tools = sdk / "build-tools" / SDK_VERSION
    for needed in [android_jar, *(sdk_tools / name for name in ("aapt2", "d8", "zipalign", "apksigner"))]:
        if not needed.is_file():
            raise SystemExit(f"Missing Android SDK tool: {needed}")
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    xposed = Path(os.environ.get("XPOSED_API_JAR", str(cache / "xposed-api-82.jar"))).resolve()
    if not xposed.exists():
        with urllib.request.urlopen(XPOSED_URL, timeout=30) as response:
            data = response.read(1_000_000)
        if hashlib.sha256(data).hexdigest() != XPOSED_SHA256:
            raise SystemExit("Xposed API download checksum mismatch")
        xposed.write_bytes(data)
    if digest(xposed) != XPOSED_SHA256:
        raise SystemExit("Xposed API82 checksum mismatch")

    work = ROOT / "build/android"
    if work.exists():
        shutil.rmtree(work)
    classes = work / "classes"
    dex = work / "dex"
    generated = work / "generated"
    for folder in (classes, dex, generated):
        folder.mkdir(parents=True, exist_ok=True)
    source = ROOT / "android/app/src/main"
    resources = work / "resources.zip"
    unsigned = work / "unsigned.apk"
    run(sdk_tools / "aapt2", "compile", "--dir", source / "res", "-o", resources)
    run(sdk_tools / "aapt2", "link", "-I", android_jar, "--manifest", source / "AndroidManifest.xml",
        "--java", generated, "--min-sdk-version", 34, "--target-sdk-version", 35,
        "--version-code", prop["versionCode"], "--version-name", prop["version"],
        "-A", source / "assets", resources, "-o", unsigned)
    java_sources = sorted((source / "java").rglob("*.java")) + sorted(generated.rglob("*.java"))
    run("javac", "-encoding", "UTF-8", "--release", 8, "-Xlint:all", "-Werror",
        "-classpath", f"{android_jar}{os.pathsep}{xposed}", "-d", classes, *java_sources)
    run(sdk_tools / "d8", "--release", "--min-api", 34, "--lib", android_jar,
        "--classpath", xposed, "--output", dex, *sorted(classes.rglob("*.class")))
    with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_DEFLATED) as apk:
        for dex_file in sorted(dex.glob("*.dex")):
            apk.write(dex_file, dex_file.name)
    aligned = work / "aligned.apk"
    run(sdk_tools / "zipalign", "-f", "4", unsigned, aligned)

    supplied_key = os.environ.get("SNAPVEIL_KEYSTORE")
    keystore = Path(supplied_key or str(ROOT / ".local/signing/snapveil.p12")).resolve()
    alias = os.environ.get("SNAPVEIL_KEY_ALIAS", "snapveil")
    password = os.environ.get("SNAPVEIL_KEYSTORE_PASSWORD", "android")
    if not keystore.exists():
        if supplied_key:
            raise SystemExit("The supplied signing keystore does not exist")
        keystore.parent.mkdir(parents=True, exist_ok=True)
        keystore.parent.chmod(0o700)
        # The local development key is private and excluded from Git. Keep it for APK updates.
        env = dict(os.environ, SNAPVEIL_SIGN_PASS=password)
        run("keytool", "-genkeypair", "-noprompt", "-storetype", "PKCS12", "-keystore", keystore,
            "-storepass:env", "SNAPVEIL_SIGN_PASS", "-keypass:env", "SNAPVEIL_SIGN_PASS",
            "-alias", alias, "-keyalg", "RSA", "-keysize", 3072, "-validity", 10000,
            "-dname", "CN=SnapVeil Development, O=LIghtJUNction", env=env)
        keystore.chmod(0o600)
    payload = ROOT / "src/snapveil/app"
    payload.mkdir(parents=True, exist_ok=True)
    output = payload / "snapveil.apk"
    env = dict(os.environ, SNAPVEIL_SIGN_PASS=password)
    run(sdk_tools / "apksigner", "sign", "--ks", keystore, "--ks-key-alias", alias,
        "--ks-pass", "env:SNAPVEIL_SIGN_PASS", "--key-pass", "env:SNAPVEIL_SIGN_PASS",
        "--v4-signing-enabled", "false", "--out", output, aligned, env=env)
    run(sdk_tools / "apksigner", "verify", "--verbose", output)
    run(sdk_tools / "zipalign", "-c", "4", output)
    (payload / "snapveil.apk.sha256").write_text(f"{digest(output)}  snapveil.apk\n")
    print(f"Built companion: {output.name}; version={prop['version']}; versionCode={prop['versionCode']}")


if __name__ == "__main__":
    main()
