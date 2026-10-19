package best.lmm.snapveil;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

final class ReflectionAccess {
    private ReflectionAccess() {}

    static Object invoke(Method method, Object receiver, Object... args)
            throws ReflectiveOperationException {
        try {
            return method.invoke(receiver, args);
        } catch (InvocationTargetException failure) {
            // A reflective wrapper must not turn a VM failure into a recoverable read error.
            Throwable cause = failure.getCause();
            if (cause instanceof Error) {
                throw (Error) cause;
            }
            if (cause instanceof RuntimeException) {
                throw (RuntimeException) cause;
            }
            throw failure;
        }
    }
}
