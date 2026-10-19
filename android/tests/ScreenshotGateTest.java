package best.lmm.snapveil;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

/** Host checks for activation changes, permission preservation and failure handling. */
public final class ScreenshotGateTest {
    private static int assertions;

    public static void main(String[] args) throws ReflectiveOperationException {
        disabledFlagDoesNotInspectCaller();
        enabledFlagStillRequiresCallerPermission();
        eachCallReadsTheCurrentFlag();
        readFailureAllowsOriginalAndCanRecover();
        permissionFailureAllowsOriginalAndCanRecover();
        expectedReflectionFailuresAllowOriginal();
        unexpectedFailuresAreNotHidden();
        reflectiveInvocationKeepsTheOriginalFailure();
        System.out.println("ScreenshotGate: " + assertions + " checks passed");
    }

    private static void disabledFlagDoesNotInspectCaller() {
        for (String value : new String[] {null, "", "0", "true", " 1", "1 ", "01"}) {
            final int[] checks = {0};
            ScreenshotGate gate = new ScreenshotGate(() -> value, receiver -> {
                checks[0]++;
                return true;
            }, (stage, failure) -> fail("disabled flag must not log a read failure"));
            check(!gate.shouldSuppress(new Object()), "only the exact value 1 may enable protection");
            check(checks[0] == 0, "disabled protection must not invoke the permission method");
        }
    }

    private static void enabledFlagStillRequiresCallerPermission() {
        Object service = new Object();
        ScreenshotGate allowed = new ScreenshotGate(() -> "1", receiver -> {
            check(receiver == service, "permission check must use the original service instance");
            return true;
        }, (stage, failure) -> fail("allowed caller must not log a failure"));
        check(allowed.shouldSuppress(service), "enabled protection should suppress authorized notifications");

        ScreenshotGate denied = new ScreenshotGate(() -> "1", receiver -> false,
                (stage, failure) -> fail("denied caller is not a reflection failure"));
        check(!denied.shouldSuppress(service),
                "denied caller must reach the original method and its permission exception");
    }

    private static void eachCallReadsTheCurrentFlag() {
        final String[] value = {"1"};
        final int[] reads = {0};
        ScreenshotGate gate = new ScreenshotGate(() -> {
            reads[0]++;
            return value[0];
        }, receiver -> true, (stage, failure) -> fail("flag change must not log a failure"));

        check(gate.shouldSuppress(null), "initial enabled flag should suppress");
        value[0] = "0";
        check(!gate.shouldSuppress(null), "disabling the flag must take effect on the next call");
        value[0] = "";
        check(!gate.shouldSuppress(null), "a missing flag must not reuse cached enabled state");
        value[0] = "1";
        check(gate.shouldSuppress(null), "re-enabling must work without reloading the gate");
        check(reads[0] == 4, "the flag must be read for each notification");
    }

    private static void readFailureAllowsOriginalAndCanRecover() {
        final boolean[] broken = {true};
        final int[] permissionChecks = {0};
        List<String> failures = new ArrayList<>();
        ScreenshotGate gate = new ScreenshotGate(() -> {
            if (broken[0]) {
                throw new IllegalAccessException("test read denied");
            }
            return "1";
        }, receiver -> {
            permissionChecks[0]++;
            return true;
        }, (stage, failure) -> failures.add(stage));

        check(!gate.shouldSuppress(null), "property read failure must allow the original method");
        check(!gate.shouldSuppress(null), "repeated property read failure must also allow the original");
        check(permissionChecks[0] == 0, "unreadable activation must not inspect caller permission");
        check(failures.size() == 1 && "activation property".equals(failures.get(0)),
                "read failure must be logged once without flooding screenshot logs");
        broken[0] = false;
        check(gate.shouldSuppress(null), "transient read failure must not permanently disable the hook");
    }

    private static void permissionFailureAllowsOriginalAndCanRecover() {
        final boolean[] broken = {true};
        List<String> failures = new ArrayList<>();
        ScreenshotGate gate = new ScreenshotGate(() -> "1", receiver -> {
            if (broken[0]) {
                throw new NoSuchMethodException("test vendor change");
            }
            return true;
        }, (stage, failure) -> failures.add(stage));

        check(!gate.shouldSuppress(null), "missing permission method must allow the original method");
        check(!gate.shouldSuppress(null), "repeated permission failure must allow the original method");
        check(failures.size() == 1 && "caller permission".equals(failures.get(0)),
                "permission failure must be logged once");
        broken[0] = false;
        check(gate.shouldSuppress(null), "permission check may recover after a transient failure");
    }

    private static void expectedReflectionFailuresAllowOriginal() {
        ScreenshotGate flagSecurity = new ScreenshotGate(() -> {
            throw new SecurityException("hidden API access denied");
        }, receiver -> true, (stage, failure) -> {});
        check(!flagSecurity.shouldSuppress(null), "property SecurityException must allow the original");

        ScreenshotGate flagLinkage = new ScreenshotGate(() -> {
            throw new NoClassDefFoundError("SystemProperties");
        }, receiver -> true, (stage, failure) -> {});
        check(!flagLinkage.shouldSuppress(null), "property LinkageError must allow the original");

        ScreenshotGate permissionSecurity = new ScreenshotGate(() -> "1", receiver -> {
            throw new SecurityException("test access denied");
        }, (stage, failure) -> {});
        check(!permissionSecurity.shouldSuppress(null), "permission SecurityException must allow the original");

        ScreenshotGate permissionLinkage = new ScreenshotGate(() -> "1", receiver -> {
            throw new NoSuchMethodError("test vendor change");
        }, (stage, failure) -> {});
        check(!permissionLinkage.shouldSuppress(null), "permission LinkageError must allow the original");
    }

    private static void unexpectedFailuresAreNotHidden() {
        AssertionError expected = new AssertionError("unexpected programming failure");
        ScreenshotGate gate = new ScreenshotGate(() -> {
            throw expected;
        }, receiver -> true, (stage, failure) -> fail("unexpected errors must not become read failures"));
        try {
            gate.shouldSuppress(null);
            fail("unexpected Error must not be swallowed");
        } catch (AssertionError actual) {
            check(actual == expected, "the original unexpected Error must propagate");
        }
    }

    private static void reflectiveInvocationKeepsTheOriginalFailure()
            throws ReflectiveOperationException {
        Method security = ThrowingMethods.class.getDeclaredMethod("security");
        try {
            ReflectionAccess.invoke(security, null);
            fail("reflective SecurityException must propagate as its original type");
        } catch (SecurityException expected) {
            check(true, "reflective SecurityException preserves its type");
        }

        Method vmError = ThrowingMethods.class.getDeclaredMethod("vmError");
        try {
            ReflectionAccess.invoke(vmError, null);
            fail("reflective VM error must not be treated as an access failure");
        } catch (OutOfMemoryError expected) {
            check(expected == ThrowingMethods.VM_FAILURE, "reflective VM error preserves its instance");
        }
    }

    public static final class ThrowingMethods {
        static final OutOfMemoryError VM_FAILURE = new OutOfMemoryError("synthetic test failure");

        public static void security() {
            throw new SecurityException("synthetic test denial");
        }

        public static void vmError() {
            throw VM_FAILURE;
        }
    }

    private static void check(boolean condition, String message) {
        assertions++;
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    private static void fail(String message) {
        throw new AssertionError(message);
    }
}
