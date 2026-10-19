#!/system/bin/sh
MODDIR=${0%/*}
"$MODDIR/cli" status
am start --user 0 -n best.lmm.snapveil/.MainActivity || {
    printf '%s\n' 'Open SnapVeil from the launcher after reboot. Check state/service.log if it is missing.'
    exit 1
}
