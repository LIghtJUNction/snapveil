"""Host behavior tests for the shipped shell scripts, using fake Android commands.

These tests execute the actual scripts with /bin/sh. They verify file handling,
boot order and failures; they do not claim Android, SELinux or LSPosed coverage.
Run with: python -m unittest discover -s tests -p 'test_runtime.py' -v
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "src" / "snapveil"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8A"
    "AwMCAO+a7WQAAAAASUVORK5CYII="
)
APK = b"synthetic-apk-used-only-by-mocked-package-installer\n"

# All writes performed by these fake OS commands stay inside the test fixture.
ANDROID_MOCK = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time
root = pathlib.Path(os.environ["SV_TEST_ROOT"])
command = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
ready_file = root / "boot.ready"
props_file = root / "props.json"
props = json.loads(props_file.read_text()) if props_file.exists() else {}
after = int(os.environ.get("MOCK_BOOT_READY_AFTER", "0"))
ready = after == 0 or ready_file.exists()
event = {"command": command, "args": args, "boot_ready": ready}
output = ""
code = 0
if command == "id":
    output = os.environ.get("MOCK_UID", "0") + "\n"
elif command == "getprop":
    if args[0] == "sys.boot_completed":
        count_file = root / "boot.reads"
        count = int(count_file.read_text()) if count_file.exists() else 0
        ready = ready or count >= after
        if ready:
            ready_file.touch()
        count_file.write_text(str(count + 1))
        output = "1\n" if ready else "0\n"
    else:
        output = props.get(args[0], "") + "\n"
    event["value"] = output.strip()
elif command == "setprop":
    code = int(os.environ.get("MOCK_SETPROP_EXIT", "0"))
    if not code and os.environ.get("MOCK_SETPROP_LIE") != "1":
        props[args[0]] = args[1]
        props_file.write_text(json.dumps(props))
elif command == "pm":
    installed = root / "installed.apk"
    if args[0] == "path":
        if installed.exists():
            output = "package:" + str(installed) + "\n"
        else:
            code = 1
    elif args[0] == "install":
        payload = sys.stdin.buffer.read()
        event["stream_size"] = len(payload)
        output = os.environ.get("MOCK_PM_OUTPUT", "Success") + "\n"
        code = int(os.environ.get("MOCK_PM_EXIT", "0"))
        if output.strip() == "Success" and code == 0:
            installed.write_bytes(payload)
    elif args[0] == "uninstall":
        installed.unlink(missing_ok=True)
        output = "Success\n"
    else:
        code = 2
elif command == "screencap":
    kind = os.environ.get("MOCK_CAPTURE", "ok")
    payload = (root / "capture.png").read_bytes()
    if kind == "text":
        payload = b"screenshot unavailable\n"
    elif kind == "truncated":
        payload = payload[:8]
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()
    code = 1 if kind == "fail" else 0
elif command == "sleep":
    time.sleep(float(os.environ.get("MOCK_SLEEP_SECONDS", "0")))
elif command == "am":
    output = "Starting: Intent\n"
else:
    raise SystemExit("Unexpected mock command: " + command)
with (root / "events.jsonl").open("a") as log:
    log.write(json.dumps(event) + "\n")
if output:
    sys.stdout.write(output)
raise SystemExit(code)
'''


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="snapveil-runtime-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = self.root / "module"
        shutil.copytree(SOURCE, self.module)
        app = self.module / "app"
        app.mkdir(exist_ok=True)
        (app / "snapveil.apk").write_bytes(APK)
        (app / "snapveil.apk.sha256").write_text(
            hashlib.sha256(APK).hexdigest() + "  snapveil.apk\n"
        )
        (self.module / "module.prop").write_text("id=snapveil\nversion=0.1.0\n")
        (self.root / "capture.png").write_bytes(PNG)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        mock = self.bin / "android-mock"
        mock.write_text(ANDROID_MOCK)
        mock.chmod(0o755)
        for name in ("id", "getprop", "setprop", "pm", "screencap", "sleep", "am"):
            (self.bin / name).symlink_to(mock)
        self.env = dict(os.environ)
        self.env.update(
            PATH=str(self.bin) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            SV_TEST_ROOT=str(self.root),
            MODDIR=str(self.module),
        )
        # Read the module's declared property, so renaming that interface does not
        # alter these behavioral checks.
        declaration = re.search(
            r"^SV_PROPERTY=(.+)$", (self.module / "lib/common.sh").read_text(), re.M
        )
        self.assertIsNotNone(declaration)
        self.property = declaration.group(1).strip("\"'")

    def run_script(self, name, *args, **changes):
        return subprocess.run(
            ["/bin/sh", str(self.module / name), *args],
            env={**self.env, **changes},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )

    def cli(self, *args, **changes):
        return self.run_script("cli", *args, **changes)

    def events(self, command=None):
        path = self.root / "events.jsonl"
        events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [e for e in events if command is None or e["command"] == command]

    def property_value(self):
        path = self.root / "props.json"
        return json.loads(path.read_text()).get(self.property, "") if path.exists() else ""

    def set_property(self, value):
        (self.root / "props.json").write_text(json.dumps({self.property: value}))

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))

    def assert_no_images(self):
        path = self.module / "captures"
        self.assertFalse(path.exists() and list(path.iterdir()), "A failed capture left an image or temporary file")

    def test_non_root_cannot_create_a_capture(self):
        result = self.cli("capture", MOCK_UID="2000")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.events("screencap"))
        self.assert_no_images()

    def test_private_capture_is_valid_private_and_exported_byte_for_byte(self):
        result = self.cli("capture")
        self.assert_ok(result)
        image = Path(result.stdout.decode().strip())
        self.assertEqual(image.parent, self.module / "captures")
        self.assertEqual(image.read_bytes(), PNG)
        self.assertEqual(stat.S_IMODE(image.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(image.parent.stat().st_mode), 0o700)
        self.assertEqual(self.cli("export", image.name).stdout, PNG)
        self.assertEqual(self.cli("list").stdout.decode().splitlines(), [image.name])
        self.assertEqual(self.events("screencap")[0]["args"], ["-p"])

    def test_failed_or_non_png_capture_keeps_no_file(self):
        for mode in ("fail", "text", "truncated"):
            with self.subTest(mode=mode):
                result = self.cli("capture", MOCK_CAPTURE=mode)
                self.assertNotEqual(result.returncode, 0, "Invalid screenshot output was accepted")
                self.assert_no_images()

    def test_capture_arguments_cannot_run_commands_or_escape_bounds(self):
        for delay in ("-1", "31", "100", "1;touch injected", "$(touch injected)", "../outside"):
            with self.subTest(delay=delay):
                self.assertNotEqual(self.cli("capture", delay).returncode, 0)
        self.assertNotEqual(self.cli("capture", "0", "extra").returncode, 0)
        self.assertFalse(self.events("screencap"))
        self.assertFalse(self.events("sleep"))
        self.assert_no_images()

    def test_delay_runs_before_capture(self):
        self.assert_ok(self.cli("capture", "2"))
        commands = [e["command"] for e in self.events()]
        self.assertLess(commands.index("sleep"), commands.index("screencap"))

    def test_capture_directory_symlink_cannot_write_outside_module(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.module / "captures").symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.cli("capture").returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(self.events("screencap"))

    def test_export_rejects_paths_options_and_symlinks(self):
        captures = self.module / "captures"
        captures.mkdir()
        secret = self.root / "secret.png"
        secret.write_bytes(b"secret-do-not-export")
        (captures / "linked.png").symlink_to(secret)
        for name in ("../secret.png", str(secret), "-n", ".hidden.png", "linked.png", "file.txt"):
            with self.subTest(name=name):
                result = self.cli("export", name)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b"secret-do-not-export", result.stdout)
        self.assertEqual(secret.read_bytes(), b"secret-do-not-export")

    def test_full_image_count_does_not_start_a_capture(self):
        captures = self.module / "captures"
        captures.mkdir()
        for i in range(100):
            (captures / f"{i}.png").write_bytes(PNG)
        self.assertNotEqual(self.cli("capture").returncode, 0)
        self.assertFalse(self.events("screencap"))
        self.assertEqual(len(list(captures.iterdir())), 100)

    def test_package_installer_cannot_report_failure_as_success(self):
        for output, status in (("Failure [INSTALL_FAILED_INVALID_APK]", "0"), ("Failure", "1"), ("Success", "1")):
            with self.subTest(output=output, status=status):
                result = self.cli("install-app", MOCK_PM_OUTPUT=output, MOCK_PM_EXIT=status)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / "installed.apk").exists())

    def test_installer_streams_verified_apk_and_does_not_reinstall_same_bytes(self):
        self.assert_ok(self.cli("install-app"))
        self.assertEqual((self.root / "installed.apk").read_bytes(), APK)
        installs = [e for e in self.events("pm") if e["args"][0] == "install"]
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0]["stream_size"], len(APK))
        self.assert_ok(self.cli("install-app"))
        self.assertEqual(len([e for e in self.events("pm") if e["args"][0] == "install"]), 1)

    def test_checksum_failure_does_not_invoke_package_installer(self):
        (self.module / "app/snapveil.apk").write_bytes(b"tampered")
        self.assertNotEqual(self.cli("install-app").returncode, 0)
        self.assertFalse(self.events("pm"))

    def test_disable_and_enable_keep_persistent_pause_and_runtime_flag_consistent(self):
        self.set_property("1")
        self.assert_ok(self.cli("disable"))
        self.assertEqual(self.property_value(), "0")
        self.assertTrue((self.module / "state/paused").exists())
        self.assert_ok(self.cli("enable"))
        self.assertEqual(self.property_value(), "1")
        self.assertFalse((self.module / "state/paused").exists())
        (self.module / "disable").touch()
        self.set_property("0")
        self.assertNotEqual(self.cli("enable").returncode, 0)
        self.assertEqual(self.property_value(), "0")

    def test_disable_marker_symlink_cannot_modify_an_outside_file(self):
        state = self.module / "state"
        state.mkdir()
        outside = self.root / "outside-file"
        outside.write_bytes(b"keep-me")
        (state / "paused").symlink_to(outside)
        self.set_property("1")
        self.cli("disable")
        self.assertEqual(outside.read_bytes(), b"keep-me")
        self.assertEqual(self.property_value(), "0", "An explicit pause must stop the active hook even if persistence fails")

    def test_unconfirmed_property_write_is_not_reported_as_success(self):
        self.assertNotEqual(self.cli("enable", MOCK_SETPROP_EXIT="1").returncode, 0)
        self.assertNotEqual(self.cli("enable", MOCK_SETPROP_LIE="1").returncode, 0)
        self.assertNotEqual(self.property_value(), "1")

    def test_boot_service_waits_for_android_before_package_or_property_operations(self):
        (self.root / "installed.apk").write_bytes(APK)
        self.assert_ok(self.run_script("service.sh", MOCK_BOOT_READY_AFTER="2"))
        operations = [e for e in self.events() if e["command"] in ("pm", "setprop")]
        self.assertTrue(operations)
        self.assertTrue(all(e["boot_ready"] for e in operations), operations)
        self.assertEqual(self.property_value(), "1")

    def test_missing_or_failed_companion_cannot_activate_service(self):
        result = self.run_script("service.sh", MOCK_PM_OUTPUT="Failure [INSTALL_FAILED_INVALID_APK]", MOCK_PM_EXIT="0")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(self.property_value(), "1")
        log = (self.module / "state/service.log").read_text()
        self.assertNotIn("Activation requested for this boot.", log)

    def test_paused_boot_does_not_install_or_reenable(self):
        state = self.module / "state"
        state.mkdir()
        (state / "paused").touch()
        self.set_property("1")
        self.assert_ok(self.run_script("service.sh"))
        self.assertEqual(self.property_value(), "0")
        self.assertFalse([e for e in self.events("pm") if e["args"][0] == "install"])

    def test_uninstall_waits_for_boot_without_blocking_its_caller(self):
        (self.root / "installed.apk").write_bytes(APK)
        self.set_property("1")
        process = subprocess.Popen(
            ["/bin/sh", str(self.module / "uninstall.sh")],
            env={**self.env, "MOCK_BOOT_READY_AFTER": "10", "MOCK_SLEEP_SECONDS": "0.1"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            process.wait(timeout=0.7)
        except subprocess.TimeoutExpired:
            (self.root / "boot.ready").touch()
            process.wait(timeout=5)
            self.fail("Uninstall blocked the boot-stage caller while waiting for Android")
        # Finish any detached cleanup worker before the fixture is removed.
        (self.root / "boot.ready").touch()
        deadline = time.monotonic() + 5
        while (self.root / "installed.apk").exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        operations = [e for e in self.events() if e["command"] in ("pm", "setprop")]
        self.assertTrue(operations)
        self.assertTrue(all(e["boot_ready"] for e in operations), operations)
        self.assertEqual(self.property_value(), "0")
        self.assertFalse((self.root / "installed.apk").exists())

    def test_upgrade_preserves_capture_contents_and_pause_with_private_modes(self):
        old = self.root / "old-module"
        (old / "captures").mkdir(parents=True)
        (old / "state").mkdir()
        (old / "captures/kept.png").write_bytes(PNG)
        (old / "state/paused").touch()
        # Map only Android's fixed module-root path into this host fixture.
        # The installer logic and all file operations are otherwise unchanged.
        installer = self.root / "customize.sh"
        installer.write_text((self.module / "customize.sh").read_text().replace(
            "/data/adb/modules/snapveil", str(old)
        ))
        wrapper = r'''
abort() { printf '%s\n' "$*" >&2; exit 1; }
ui_print() { printf '%s\n' "$*"; }
set_perm() { chmod "$4" "$1"; }
set_perm_recursive() {
    find "$1" -type d -exec chmod "$4" '{}' +
    find "$1" -type f -exec chmod "$5" '{}' +
}
. "$INSTALLER"
'''
        result = subprocess.run(
            ["/bin/sh", "-c", wrapper],
            env={**self.env, "BOOTMODE": "true", "API": "34", "MODPATH": str(self.module), "INSTALLER": str(installer)},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
        self.assert_ok(result)
        kept = self.module / "captures/kept.png"
        self.assertEqual(kept.read_bytes(), PNG)
        self.assertEqual(stat.S_IMODE(kept.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(kept.parent.stat().st_mode), 0o700)
        self.assertTrue((self.module / "state/paused").exists())
        self.assertEqual((old / "captures/kept.png").read_bytes(), PNG)


if __name__ == "__main__":
    unittest.main()
