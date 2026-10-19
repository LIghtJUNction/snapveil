package best.lmm.snapveil;

/** This check reports only whether LSPosed loaded the companion app's own scope. */
final class ModuleState {
    private ModuleState() {}

    static boolean isOwnProcessHooked() {
        return false;
    }
}
