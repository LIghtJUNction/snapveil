#!/system/bin/sh
MODDIR=${0%/*}
# shellcheck source=src/snapveil/lib/common.sh
. "$MODDIR/lib/common.sh"
umask 077
sv_private_dir "$MODDIR/state" || exit 1
[ ! -L "$MODDIR/state/service.log" ] || exit 1
exec > "$MODDIR/state/service.log" 2>&1
sv_root || exit 1

# Do not use setprop in post-fs-data: it can hold up Android boot.
# This is a bounded boot wait, not a resident polling service.
sv_wait=0
until [ "$(getprop sys.boot_completed)" = 1 ]; do
    sv_wait=$((sv_wait + 1))
    [ "$sv_wait" -le 120 ] || {
        printf '%s\n' 'Boot did not finish within 240 seconds. Leaving protection inactive.'
        exit 1
    }
    sleep 2
done

if ! sv_enabled; then
    sv_set_active 0
    exit $?
fi
if ! pm path --user 0 "$SV_PACKAGE" 2>/dev/null | grep -q '^package:'; then
    sv_set_active 0
    printf '%s\n' 'Companion missing. Run cli install-app, enable its LSPosed scope, then reboot.'
    exit 1
fi
sv_set_active 1 || exit 1
printf '%s\n' \
    'Activation requested for this boot.' \
    'Enable SnapVeil in LSPosed for System Framework, then reboot.' \
    'Confirm behavior with the callback test. A property is not proof that the hook loaded.'
