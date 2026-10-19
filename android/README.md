# SnapVeil Android companion

This is the LSPosed companion for the SnapVeil root module. It uses the legacy
Xposed API, with API 82 as the minimum. It has no external UI libraries.

## Build inputs

- JDK 17 or newer.
- Android SDK platform 35 and its build tools.
- Xposed API 82 as a **compile-only** dependency. Do not put Xposed API classes
  inside the APK.
- Version name and version code from the project's generated `module.prop`.

The project build script compiles `app/src/main/java`, links the manifest and
resources from `app/src/main`, includes `assets/xposed_init`, and signs the APK.
The manifest sets minimum Android API 34 and target API 35. Source verification
covers the notification method in AOSP Android 14, 15, and 16. This is not a
claim that every device on those versions has passed a device test.

## Hook behavior

The scope is `android` (System Framework) plus `best.lmm.snapveil` for the
companion's own load check. There is no need to select every application.

`SnapVeilHook` finds the exact
`WindowManagerService.notifyScreenshotListeners(int): List` method. Before each
call it reads the non-persistent `sys.snapveil.active` property. Only the exact
value `1` enables interception. A missing property or a failed read leaves the
original method in charge.

An enabled call still runs the same
`checkCallingPermission("android.permission.STATUS_BAR_SERVICE", ...)` check as
AOSP. A caller without that permission reaches the original method, which
rejects the caller as usual. If this permission method is missing, the module
does not install the hook. This prevents the early return from bypassing the
original permission check.

An enabled, permitted call returns an empty list before the activity callbacks
are sent. The empty list also avoids telling SystemUI that an application was
notified. The hook does not change screenshot files, media access, protected
windows, SELinux, AppOps, or screen recording detection.

## Device verification

The companion declares `DETECT_SCREEN_CAPTURE` and registers Android's real
`Activity.ScreenCaptureCallback` while its page is started. It displays the
registration state, the received callback count, and the most recent time.

1. Disable the SnapVeil **root module** and reboot.
2. Open the companion. Keep it visible and take a screenshot with the hardware
   buttons. Confirm that the callback count increases.
3. Enable the root module. Enable the companion in LSPosed with System Framework
   and SnapVeil selected, then reboot.
4. Repeat the same screenshot test. The callback count should remain at zero.
5. Check the LSPosed log for `system_server screenshot hook installed`. A missing
   method or unreadable property is logged as a failure and leaves the original
   behavior in place.

Zero callbacks alone do not prove success. A vendor screenshot path can skip
the standard API, and a page which is not visible may receive no callback.
The companion's own LSPosed status only proves that LSPosed loaded this app's
process. It does not prove that the system process hook was installed.

Applications can also detect new screenshot files in shared storage. A vendor
can implement a separate notification path. These paths are outside this
companion's scope.

## Host checks

From the repository root:

```sh
sh android/tests/run.sh
```

These checks cover activation changes, original permission handling, failed
reads, recovery, and reflective error handling. They run with the JDK alone.
They do not emulate LSPosed, Binder, Android lifecycle events, or an actual
screenshot. The device test above is still required.

## Source references

The method and its permission check were checked in the following AOSP files:

- [Android 14 WindowManagerService](https://android.googlesource.com/platform/frameworks/base/+/android-14.0.0_r1/services/core/java/com/android/server/wm/WindowManagerService.java)
- [Android 15 WindowManagerService](https://android.googlesource.com/platform/frameworks/base/+/android-15.0.0_r1/services/core/java/com/android/server/wm/WindowManagerService.java)
- [Android 16 WindowManagerService](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r1/services/core/java/com/android/server/wm/WindowManagerService.java)
- [Android screenshot detection API](https://developer.android.com/about/versions/14/features/screenshot-detection)
