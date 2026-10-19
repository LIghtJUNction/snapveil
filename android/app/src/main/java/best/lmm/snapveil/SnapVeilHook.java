package best.lmm.snapveil;

import java.lang.reflect.Method;
import java.util.Collections;
import java.util.List;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

public final class SnapVeilHook implements IXposedHookLoadPackage {
    private static final String PACKAGE_NAME = "best.lmm.snapveil";
    private static final String WINDOW_MANAGER = "com.android.server.wm.WindowManagerService";
    private static final String STATUS_BAR_SERVICE = "android.permission.STATUS_BAR_SERVICE";

    @Override
    public void handleLoadPackage(XC_LoadPackage.LoadPackageParam loaded) {
        if (PACKAGE_NAME.equals(loaded.packageName)) {
            installOwnProcessCheck(loaded.classLoader);
            return;
        }
        if (!"android".equals(loaded.packageName)) {
            return;
        }

        try {
            Class<?> service = Class.forName(WINDOW_MANAGER, false, loaded.classLoader);
            Method notification = service.getDeclaredMethod("notifyScreenshotListeners", int.class);
            if (notification.getReturnType() != List.class) {
                throw new NoSuchMethodException("notifyScreenshotListeners(int): List");
            }
            Method permission = service.getDeclaredMethod(
                    "checkCallingPermission", String.class, String.class);
            if (permission.getReturnType() != boolean.class) {
                throw new NoSuchMethodException("checkCallingPermission(String, String): boolean");
            }
            permission.setAccessible(true);

            ScreenshotGate gate = new ScreenshotGate(
                    new RuntimeFlag(loaded.classLoader),
                    receiver -> (Boolean) ReflectionAccess.invoke(permission, receiver,
                            STATUS_BAR_SERVICE, "notifyScreenshotListeners()"),
                    (stage, failure) -> logFailure(stage + " failed; original method allowed", failure));

            XposedBridge.hookMethod(notification, new XC_MethodHook() {
                @Override
                protected void beforeHookedMethod(MethodHookParam call) {
                    if (gate.shouldSuppress(call.thisObject)) {
                        // Also return no notified apps, so SystemUI does not claim they were told.
                        call.setResult(Collections.emptyList());
                    }
                }
            });
            XposedBridge.log("SnapVeil: system_server screenshot hook installed; "
                    + "protection requires " + RuntimeFlag.NAME + "=1");
        } catch (ReflectiveOperationException | SecurityException | LinkageError
                | IllegalArgumentException failure) {
            logFailure("system_server hook unavailable; system behavior unchanged", failure);
        }
    }

    private static void installOwnProcessCheck(ClassLoader classLoader) {
        try {
            Class<?> state = Class.forName(PACKAGE_NAME + ".ModuleState", false, classLoader);
            XposedBridge.hookMethod(state.getDeclaredMethod("isOwnProcessHooked"), new XC_MethodHook() {
                @Override
                protected void beforeHookedMethod(MethodHookParam call) {
                    call.setResult(Boolean.TRUE);
                }
            });
        } catch (ReflectiveOperationException | SecurityException | LinkageError
                | IllegalArgumentException failure) {
            logFailure("companion process check unavailable", failure);
        }
    }

    private static void logFailure(String message, Throwable failure) {
        XposedBridge.log("SnapVeil: " + message + " (" + failure.getClass().getSimpleName() + ")");
        XposedBridge.log(failure);
    }
}
