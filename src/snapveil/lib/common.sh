#!/system/bin/sh
# Shared runtime code. All writable files belong to this module directory.

SV_PACKAGE=best.lmm.snapveil
SV_PROPERTY=sys.snapveil.active

sv_root() {
    [ "$(id -u)" = 0 ] || {
        printf '%s\n' 'Root access is required.' >&2
        return 1
    }
}

sv_enabled() {
    [ ! -e "$MODDIR/disable" ] && [ ! -e "$MODDIR/remove" ] &&
        [ ! -e "$MODDIR/state/paused" ]
}

sv_private_dir() {
    # Never follow an existing symlink when preparing a root-owned directory.
    [ ! -L "$1" ] || {
        printf '%s\n' "Refusing a symbolic-link directory: $1" >&2
        return 1
    }
    (umask 077; mkdir -p "$1") && chmod 700 "$1"
}

sv_set_active() {
    if ! setprop "$SV_PROPERTY" "$1" || [ "$(getprop "$SV_PROPERTY")" != "$1" ]; then
        printf '%s\n' 'Cannot set the activation property. Protection was not confirmed.' >&2
        return 1
    fi
}

sv_install_app() {
    sv_apk="$MODDIR/app/snapveil.apk"
    [ -s "$sv_apk" ] || {
        printf '%s\n' 'Companion APK is missing.' >&2
        return 1
    }
    (cd "$MODDIR/app" && sha256sum -c snapveil.apk.sha256) || return 1
    sv_installed=$(pm path --user 0 "$SV_PACKAGE" 2>/dev/null | sed -n 's/^package://p' | head -n 1)
    if [ -n "$sv_installed" ] && [ -f "$sv_installed" ]; then
        sv_old_hash=$(sha256sum "$sv_installed" | cut -d ' ' -f 1)
        sv_new_hash=$(sha256sum "$sv_apk" | cut -d ' ' -f 1)
        [ "$sv_old_hash" != "$sv_new_hash" ] || return 0
    fi
    # Stream the APK: PackageInstaller cannot always read /data/adb directly.
    sv_size=$(wc -c < "$sv_apk" | tr -d '[:space:]')
    # A pipe also avoids requiring PackageInstaller to read the source inode.
    # shellcheck disable=SC2002
    if sv_install_result=$(cat "$sv_apk" | pm install --user 0 -r -S "$sv_size" 2>&1); then
        sv_install_status=0
    else
        sv_install_status=1
    fi
    printf '%s\n' "$sv_install_result"
    [ "$sv_install_status" = 0 ] &&
        printf '%s\n' "$sv_install_result" | grep -qx 'Success'
}

sv_status() {
    printf 'SnapVeil %s\n' "$(sed -n 's/^version=//p' "$MODDIR/module.prop")"
    if sv_enabled; then
        printf '%s\n' 'Module switch: enabled'
    else
        printf '%s\n' 'Module switch: disabled or paused'
    fi
    printf 'Requested activation: %s\n' "$(getprop "$SV_PROPERTY")"
    if pm path --user 0 "$SV_PACKAGE" 2>/dev/null | grep -q '^package:'; then
        printf '%s\n' 'Companion APK: installed'
    else
        printf '%s\n' 'Companion APK: missing'
    fi
    printf '%s\n' \
        'System hook: verify in LSPosed logs and the callback test; installation is not proof.' \
        'Coverage: standard Android screenshot notifications. Gallery and vendor detection may remain.'
}

sv_capture() (
    sv_delay=${1:-0}
    case "$sv_delay" in
        ''|*[!0-9]*) printf '%s\n' 'Delay must be 0..30 seconds.' >&2; return 1 ;;
    esac
    if [ "${#sv_delay}" -gt 2 ] || [ "$sv_delay" -gt 30 ]; then
        printf '%s\n' 'Delay must be 0..30 seconds.' >&2
        return 1
    fi
    sv_private_dir "$MODDIR/captures" || return 1
    sv_count=0
    for sv_file in "$MODDIR/captures/"*.png; do
        [ -f "$sv_file" ] && sv_count=$((sv_count + 1))
    done
    sv_kib=$(du -sk "$MODDIR/captures" | cut -f 1)
    if [ "$sv_count" -ge 100 ] || [ "$sv_kib" -ge 262144 ]; then
        printf '%s\n' 'Private capture storage is full (100 images or 256 MiB). Export or remove images first.' >&2
        return 1
    fi
    [ "$sv_delay" = 0 ] || sleep "$sv_delay"
    # mktemp creates a new private file and does not follow pre-existing symlinks.
    sv_tmp=$(mktemp "$MODDIR/captures/.capture.XXXXXXXX") || return 1
    trap 'rm -f "$sv_tmp"' 0
    trap 'exit 1' HUP INT TERM
    if ! screencap -p > "$sv_tmp"; then
        rm -f "$sv_tmp"
        printf '%s\n' 'screencap failed. No image was kept.' >&2
        return 1
    fi
    sv_magic=$(od -An -tx1 -N8 "$sv_tmp" | tr -d ' \n')
    sv_header=$(od -An -tx1 -j8 -N8 "$sv_tmp" | tr -d ' \n')
    sv_end=$(tail -c 12 "$sv_tmp" | od -An -tx1 | tr -d ' \n')
    if [ "$sv_magic" != 89504e470d0a1a0a ] || [ "$sv_header" != 0000000d49484452 ] ||
        [ "$sv_end" != 0000000049454e44ae426082 ]; then
        rm -f "$sv_tmp"
        printf '%s\n' 'screencap did not return a PNG. No image was kept.' >&2
        return 1
    fi
    if [ "$(du -sk "$MODDIR/captures" | cut -f 1)" -gt 262144 ]; then
        rm -f "$sv_tmp"
        printf '%s\n' 'This image would exceed the 256 MiB capture limit. No image was kept.' >&2
        return 1
    fi
    sv_suffix=${sv_tmp##*.}
    sv_final="$MODDIR/captures/$(date -u +%Y%m%dT%H%M%SZ)-$sv_suffix.png"
    if ! chmod 600 "$sv_tmp" || ! mv "$sv_tmp" "$sv_final"; then
        rm -f "$sv_tmp"
        return 1
    fi
    printf '%s\n' "$sv_final"
)

sv_export() {
    # Deliberately export bytes to stdout; do not choose a shared-storage path.
    case "$1" in
        ''|.*|*[!a-zA-Z0-9._-]*) printf '%s\n' 'Use an image basename from cli list.' >&2; return 1 ;;
        *.png) ;;
        *) printf '%s\n' 'Only PNG images can be exported.' >&2; return 1 ;;
    esac
    [ ! -L "$MODDIR/captures" ] && [ ! -L "$MODDIR/captures/$1" ] &&
        [ -f "$MODDIR/captures/$1" ] || return 1
    cat "$MODDIR/captures/$1"
}
