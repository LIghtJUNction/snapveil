package best.lmm.snapveil;

import java.util.concurrent.atomic.AtomicBoolean;

/** Decides whether a screenshot notification can be suppressed safely. */
final class ScreenshotGate {
    interface ActivationSource {
        String read() throws ReflectiveOperationException;
    }

    interface CallerPermission {
        boolean isAllowed(Object service) throws ReflectiveOperationException;
    }

    interface FailureLog {
        void report(String stage, Throwable failure);
    }

    private final ActivationSource activation;
    private final CallerPermission permission;
    private final FailureLog log;
    private final AtomicBoolean activationFailureReported = new AtomicBoolean();
    private final AtomicBoolean permissionFailureReported = new AtomicBoolean();

    ScreenshotGate(ActivationSource activation, CallerPermission permission, FailureLog log) {
        this.activation = activation;
        this.permission = permission;
        this.log = log;
    }

    boolean shouldSuppress(Object service) {
        // Read on every screenshot. Do not cache an enabled state across disable operations.
        try {
            if (!"1".equals(activation.read())) {
                return false;
            }
        } catch (ReflectiveOperationException | SecurityException | LinkageError failure) {
            reportOnce(activationFailureReported, "activation property", failure);
            return false;
        }

        try {
            // A denied caller must reach the original method and its SecurityException.
            return permission.isAllowed(service);
        } catch (ReflectiveOperationException | SecurityException | LinkageError failure) {
            reportOnce(permissionFailureReported, "caller permission", failure);
            return false;
        }
    }

    private void reportOnce(AtomicBoolean reported, String stage, Throwable failure) {
        if (reported.compareAndSet(false, true)) {
            log.report(stage, failure);
        }
    }
}
