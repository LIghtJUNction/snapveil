#!/system/bin/sh
# The manager may call this before Android services exist. Do not hold up boot.
# The non-persistent activation property is already absent at a new boot.
(
    sv_wait=0
    until [ "$(getprop sys.boot_completed)" = 1 ]; do
        sv_wait=$((sv_wait + 1))
        [ "$sv_wait" -le 120 ] || exit 1
        sleep 2
    done
    setprop sys.snapveil.active 0
    pm uninstall best.lmm.snapveil
) </dev/null >/dev/null 2>&1 &
# The root manager removes the module directory, including its private captures.
