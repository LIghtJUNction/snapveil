#!/usr/bin/env bash
# Apply a tested version bump and optionally publish the exact verified build.
set -euo pipefail

cd "$(dirname "$0")/.."
: "${BUMP_MODE:?}"
: "${PUBLISH_RELEASE:?}"
: "${PRERELEASE:?}"
: "${BUILD_VERSION:?}"

fail() { echo "ERROR: $*" >&2; exit 1; }
case "$BUMP_MODE" in none|patch|minor|major) ;; *) fail "invalid bump mode" ;; esac
case "$PUBLISH_RELEASE:$PRERELEASE" in
  true:true|true:false|false:false) ;;
  *) fail "invalid release/prerelease combination" ;;
esac
[[ "${GITHUB_REF:-refs/heads/main}" == refs/heads/main ]] || fail 'publication requires main branch'
[[ "$BUILD_VERSION" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] || fail 'invalid release version'
[[ -f dist/SHA256SUMS && -s dist/snapveil-${BUILD_VERSION}.zip && -s dist/snapveil.apk ]] || fail 'build artifacts are missing'
(cd dist && sha256sum --check --status SHA256SUMS) || fail 'build artifact checksum mismatch'

if [[ "$BUMP_MODE" != none ]]; then
  [[ -s dist/bump.patch ]] || fail 'missing version bump patch'
  git apply --check dist/bump.patch || fail 'version bump no longer applies cleanly'
  git apply --index dist/bump.patch
  git diff --cached --check
  changed="$(git diff --cached --name-only)"
  [[ "$changed" == $'kam.toml\nsrc/snapveil/module.prop' ]] || fail "unexpected files in version bump: $changed"
else
  [[ ! -e dist/bump.patch ]] || fail 'bump patch present when bump=none'
fi
version="$(python3 -c 'import tomllib; print(tomllib.load(open("kam.toml", "rb"))["prop"]["version"])')"
[[ "$version" == "$BUILD_VERSION" ]] || fail "built version $BUILD_VERSION differs from source $version"

if [[ "$PUBLISH_RELEASE" == true ]]; then
  # Never overwrite a published version. Retries may reuse an existing tag
  # only if it already points to the precise commit being published.
  if gh release view "$version" >/dev/null 2>&1; then
    fail "GitHub Release $version already exists; bump to another version"
  fi
  if [[ "$BUMP_MODE" != none ]] && git show-ref --verify --quiet "refs/tags/$version"; then
    fail "tag $version already exists; refusing a new commit with that version"
  fi
fi

if [[ "$BUMP_MODE" != none ]]; then
  git config user.name 'github-actions[bot]'
  git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
  git commit -m "chore(release): bump SnapVeil to $version [skip ci]"
  # Fast-forward only. If main moved, fail instead of overwriting changes.
  git push origin HEAD:refs/heads/main
fi

if [[ "$PUBLISH_RELEASE" == true ]]; then
  if git show-ref --verify --quiet "refs/tags/$version"; then
    [[ "$(git rev-parse "refs/tags/$version^{commit}")" == "$(git rev-parse HEAD)" ]] || \
      fail "tag $version belongs to another commit"
  else
    git config user.name 'github-actions[bot]'
    git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
    git tag -a "$version" -m "SnapVeil $version"
    git push origin "refs/tags/$version"
  fi
  options=(--verify-tag --title "SnapVeil $version" --generate-notes \
    --notes 'Android 14+ and LSPosed required. Real-device compatibility has not been verified.')
  if [[ "$PRERELEASE" == true ]]; then
    options+=(--prerelease)
  fi
  gh release create "$version" "dist/snapveil-${version}.zip" dist/snapveil.apk dist/SHA256SUMS "${options[@]}"
fi
