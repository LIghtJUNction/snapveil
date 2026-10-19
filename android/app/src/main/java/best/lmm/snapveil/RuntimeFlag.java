package best.lmm.snapveil;

import java.lang.reflect.Method;

/** The root module sets this non-persistent flag only while enabled for this boot. */
final class RuntimeFlag implements ScreenshotGate.ActivationSource {
    static final String NAME = "sys.snapveil.active";
    private final Method getter;

    RuntimeFlag(ClassLoader classLoader) throws ReflectiveOperationException {
        Class<?> properties = Class.forName("android.os.SystemProperties", false, classLoader);
        getter = properties.getDeclaredMethod("get", String.class, String.class);
        if (getter.getReturnType() != String.class) {
            throw new NoSuchMethodException("SystemProperties.get(String, String): String");
        }
        getter.setAccessible(true);
    }

    @Override
    public String read() throws ReflectiveOperationException {
        return (String) ReflectionAccess.invoke(getter, null, NAME, "");
    }
}
