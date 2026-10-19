#!/system/bin/sh
# Used by the root manager after this script is sourced.
# shellcheck disable=SC2034
SKIPUNZIP=0
[ "$BOOTMODE" = true ] || abort 'Install SnapVeil from a root manager while Android is running.'
[ "$API" -ge 34 ] || abort 'SnapVeil requires Android 14 or later (API 34+).'
ui_print 'SnapVeil: standard screenshot notification blocking'
ui_print 'Requires LSPosed. Enable System Framework after installation.'
ui_print 'Gallery-based and vendor-specific detection are outside the global hook.'
ui_print 'The companion app will be installed now. Enable its LSPosed scope before reboot.'
[ -s "$MODPATH/app/snapveil.apk" ] || abort 'Missing companion APK.'
(cd "$MODPATH/app" && sha256sum -c snapveil.apk.sha256) || abort 'Companion APK checksum mismatch.'

# Preserve only our user-owned data on upgrades; never create loose /data/adb files.
sv_old=/data/adb/modules/snapveil
if [ "$MODPATH" != "$sv_old" ] && [ -d "$sv_old" ] && [ ! -L "$sv_old" ]; then
    for sv_part in captures state; do
        [ ! -L "$sv_old/$sv_part" ] || abort "Refusing symlink in existing $sv_part."
        if [ -d "$sv_old/$sv_part" ]; then
            cp -a "$sv_old/$sv_part" "$MODPATH/" || abort "Cannot preserve $sv_part."
        fi
    done
fi
set_perm_recursive "$MODPATH" 0 0 0755 0644
for sv_script in cli service.sh action.sh uninstall.sh; do
    set_perm "$MODPATH/$sv_script" 0 0 0755
done
for sv_part in captures state; do
    if [ -d "$MODPATH/$sv_part" ]; then
        set_perm_recursive "$MODPATH/$sv_part" 0 0 0700 0600
    fi
done
touch "$MODPATH/skip_mount"
MODDIR=$MODPATH
# shellcheck source=src/snapveil/lib/common.sh
. "$MODDIR/lib/common.sh"
sv_install_app || abort 'Companion installation failed; the module was not installed.'
ui_print 'Open LSPosed: enable SnapVeil for System Framework and SnapVeil, then reboot.'
