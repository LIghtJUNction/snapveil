"""Exercise the publish script against a temporary Git repository and fake gh CLI."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str, cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="snapveil-release-")
        self.addCleanup(self.directory.cleanup)
        temp = Path(self.directory.name)
        self.remote = temp / "remote.git"
        self.repo = temp / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        git("init", "-b", "main", cwd=self.repo)
        git("config", "user.name", "Release test", cwd=self.repo)
        git("config", "user.email", "ci@example.invalid", cwd=self.repo)
        (self.repo / "tools").mkdir()
        (self.repo / "src/snapveil").mkdir(parents=True)
        shutil.copy(ROOT / "tools/publish.sh", self.repo / "tools/publish.sh")
        (self.repo / "kam.toml").write_text('[prop]\nid = "snapveil"\nversion = "v0.1.0"\nversionCode = 1\n')
        (self.repo / "src/snapveil/module.prop").write_text('id=snapveil\nversion=v0.1.0\nversionCode=1\n')
        (self.repo / ".gitignore").write_text('dist/\n')
        git("add", ".", cwd=self.repo)
        git("commit", "-m", "initial version", cwd=self.repo)
        git("remote", "add", "origin", str(self.remote), cwd=self.repo)
        git("push", "-u", "origin", "main", cwd=self.repo)
        self.bin = temp / "bin"
        self.bin.mkdir()
        self.gh_log = temp / "gh.log"
        gh = self.bin / "gh"
        gh.write_text('#!/bin/sh\n'
                      'printf "%s\\n" "$*" >> "$GH_TEST_LOG"\n'
                      'if [ "$1 $2" = "release view" ]; then\n'
                      '  if [ "${GH_RELEASE_EXISTS:-0}" = "1" ]; then exit 0; fi\n'
                      '  exit 1\n'
                      'fi\n'
                      '[ "$1 $2" = "release create" ]\n')
        gh.chmod(0o755)
        self.initial = git("rev-parse", "HEAD", cwd=self.repo)

    def artifact(self, version="v0.1.0", corrupt=False):
        dist = self.repo / "dist"
        dist.mkdir(exist_ok=True)
        zip_path = dist / f"snapveil-{version}.zip"
        apk_path = dist / "snapveil.apk"
        zip_path.write_bytes(b"test-zip-for-" + version.encode())
        apk_path.write_bytes(b"test-apk-for-" + version.encode())
        sums = [(hashlib.sha256(p.read_bytes()).hexdigest(), p.name) for p in (zip_path, apk_path)]
        (dist / "SHA256SUMS").write_text("".join(f"{h}  {name}\n" for h, name in sums))
        if corrupt:
            zip_path.write_bytes(b"tampered")

    def create_bump_patch(self):
        prop = self.repo / "kam.toml"
        module = self.repo / "src/snapveil/module.prop"
        prop.write_text(prop.read_text().replace('v0.1.0', 'v0.1.1').replace('versionCode = 1', 'versionCode = 2'))
        module.write_text(module.read_text().replace('v0.1.0', 'v0.1.1').replace('versionCode=1', 'versionCode=2'))
        git("add", "kam.toml", "src/snapveil/module.prop", cwd=self.repo)
        diff = subprocess.check_output(["git", "diff", "--cached", "--binary", "--", "kam.toml", "src/snapveil/module.prop"], cwd=self.repo)
        (self.repo / "dist/bump.patch").write_bytes(diff)
        git("reset", "--hard", "HEAD", cwd=self.repo)

    def publish(self, *, bump="none", release="true", prerelease="false", version="v0.1.0", release_exists=False):
        env = dict(os.environ,
                   BUMP_MODE=bump,
                   PUBLISH_RELEASE=release,
                   PRERELEASE=prerelease,
                   BUILD_VERSION=version,
                   GITHUB_REF="refs/heads/main",
                   GH_TEST_LOG=str(self.gh_log),
                   GH_RELEASE_EXISTS="1" if release_exists else "0",
                   PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}")
        return subprocess.run(["bash", "tools/publish.sh"], cwd=self.repo, env=env, capture_output=True, text=True)

    def test_release_existing_version_creates_tag_and_calls_gh(self):
        self.artifact()
        p = self.publish()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(git("rev-parse", "v0.1.0^{commit}", cwd=self.repo), self.initial)
        self.assertIn("release create v0.1.0", self.gh_log.read_text())
        self.assertIn("--verify-tag", self.gh_log.read_text())
        self.assertEqual(git("rev-parse", "refs/tags/v0.1.0", cwd=self.remote), git("rev-parse", "refs/tags/v0.1.0", cwd=self.repo))

    def test_bump_only_commits_to_main_without_creating_tag(self):
        self.artifact("v0.1.1")
        self.create_bump_patch()
        p = self.publish(bump="patch", release="false", version="v0.1.1")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotEqual(git("rev-parse", "HEAD", cwd=self.repo), self.initial)
        self.assertEqual(git("rev-parse", "refs/heads/main", cwd=self.remote), git("rev-parse", "HEAD", cwd=self.repo))
        self.assertEqual(git("tag", "--list", cwd=self.repo), "")
        self.assertFalse(self.gh_log.exists())

    def test_bump_and_prerelease_publish_same_commit(self):
        self.artifact("v0.1.1")
        self.create_bump_patch()
        p = self.publish(bump="patch", version="v0.1.1", prerelease="true")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(git("rev-parse", "v0.1.1^{commit}", cwd=self.repo), git("rev-parse", "HEAD", cwd=self.repo))
        self.assertIn("--prerelease", self.gh_log.read_text())

    def test_failed_checksum_cannot_commit_or_tag(self):
        self.artifact("v0.1.1", corrupt=True)
        self.create_bump_patch()
        p = self.publish(bump="patch", version="v0.1.1")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("checksum mismatch", p.stderr)
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.repo), self.initial)
        self.assertEqual(git("tag", "--list", cwd=self.repo), "")

    def test_existing_release_is_not_overwritten(self):
        self.artifact()
        p = self.publish(release_exists=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("already exists", p.stderr)
        self.assertEqual(git("tag", "--list", cwd=self.repo), "")

    def test_version_mismatch_cannot_commit(self):
        self.artifact("v0.1.1")
        p = self.publish(version="v0.1.1")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("differs from source", p.stderr)

    def test_release_requires_bump_if_version_tag_exists_on_another_commit(self):
        self.artifact("v0.1.1")
        self.create_bump_patch()
        git("tag", "v0.1.1", cwd=self.repo)
        p = self.publish(bump="patch", version="v0.1.1")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("tag v0.1.1 already exists", p.stderr)
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.repo), self.initial)

    def test_prerelease_without_release_is_rejected(self):
        self.artifact()
        p = self.publish(release="false", prerelease="true")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("invalid release/prerelease combination", p.stderr)

    def test_non_main_branch_cannot_publish(self):
        self.artifact()
        env = dict(os.environ, BUMP_MODE="none", PUBLISH_RELEASE="true", PRERELEASE="false", BUILD_VERSION="v0.1.0", GITHUB_REF="refs/heads/test")
        p = subprocess.run(["bash", "tools/publish.sh"], cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("main branch", p.stderr)


if __name__ == "__main__":
    unittest.main()
