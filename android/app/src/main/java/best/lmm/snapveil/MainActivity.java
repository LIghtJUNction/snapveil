package best.lmm.snapveil;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.util.Log;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.text.DateFormat;
import java.util.Date;

public final class MainActivity extends Activity {
    private static final String TAG = "SnapVeil";
    private static final String COUNT_KEY = "screenshot_count";
    private static final String TIME_KEY = "last_screenshot_time";

    private TextView moduleStatus;
    private TextView callbackStatus;
    private int callbackCount;
    private long lastCallbackTime;
    private boolean callbackRegistered;
    private String registrationFailure;
    private final ScreenCaptureCallback screenshotCallback = () -> {
        callbackCount++;
        lastCallbackTime = System.currentTimeMillis();
        renderCallbackStatus();
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (savedInstanceState != null) {
            callbackCount = savedInstanceState.getInt(COUNT_KEY);
            lastCallbackTime = savedInstanceState.getLong(TIME_KEY);
        }

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(247, 248, 250));
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        int padding = dp(24);
        content.setPadding(padding, padding, padding, padding);
        scroll.addView(content);
        // Android 15 draws target-35 apps under system bars. Keep the page clear of both bars.
        scroll.setOnApplyWindowInsetsListener((view, insets) -> {
            android.graphics.Insets bars = insets.getInsets(
                    WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });
        setContentView(scroll);

        addTitle(content, "SnapVeil", 30);
        addText(content, "截屏通知保护", 18);
        addText(content, "阻止 Android 14–16 标准截屏回调。需要 Root 模块与 LSPosed 配合。", 15);

        addTitle(content, "运行状态", 20);
        moduleStatus = addText(content, "", 15);
        Button refresh = new Button(this);
        refresh.setText("刷新状态");
        refresh.setOnClickListener(view -> refreshModuleStatus());
        content.addView(refresh);
        addText(content, "本应用已加载，只说明自身作用域已生效。"
                + "系统框架是否成功拦截，需要下方对照测试和 LSPosed 日志确认。", 14);

        addTitle(content, "启用方法", 20);
        addText(content, "1. 在 Root 管理器安装并开启 SnapVeil。\n"
                + "2. 安装脚本会同时安装 SnapVeil 应用。\n"
                + "3. 在 LSPosed 中启用 SnapVeil，勾选“系统框架”（android）及 SnapVeil。\n"
                + "4. 重启手机，再打开本页测试。", 15);

        addTitle(content, "标准截屏回调测试", 20);
        callbackStatus = addText(content, "", 16);
        Button reset = new Button(this);
        reset.setText("清零计数");
        reset.setOnClickListener(view -> {
            callbackCount = 0;
            lastCallbackTime = 0;
            renderCallbackStatus();
        });
        content.addView(reset);
        addText(content, "先在 Root 管理器停用 SnapVeil 并重启。停留在本页，"
                + "用电源键＋音量减键截屏，确认计数增加。\n\n"
                + "然后开启 SnapVeil 并重启。用相同方式截屏，确认计数保持 0。\n\n"
                + "0 次回调不能独立证明拦截成功。部分系统、截屏方式或应用状态"
                + "不会发出标准回调。测试时请保持本页在前台。", 15);

        addTitle(content, "适用范围", 20);
        addText(content, "系统截屏仍可能保存到公共相册。拥有照片或文件访问权的软件，"
                + "仍可能从新图片推断截屏。厂商私有检测方式也可能不受影响。\n\n"
                + "本模块不解除禁止截屏页面的限制，不改变录屏检测。"
                + "如需避免公共相册产生截屏记录，请使用模块提供的私有截屏命令。", 15);
        addText(content, "本页计数仅保留在应用进程和页面状态中，不写入文件，不上传。", 13);
        refreshModuleStatus();
        renderCallbackStatus();
    }

    @Override
    protected void onStart() {
        super.onStart();
        registrationFailure = null;
        try {
            registerScreenCaptureCallback(getMainExecutor(), screenshotCallback);
            callbackRegistered = true;
        } catch (SecurityException | IllegalStateException failure) {
            callbackRegistered = false;
            registrationFailure = failure.getClass().getSimpleName();
            Log.w(TAG, "Screen capture callback registration failed", failure);
        }
        refreshModuleStatus();
        renderCallbackStatus();
    }

    @Override
    protected void onStop() {
        if (callbackRegistered) {
            try {
                unregisterScreenCaptureCallback(screenshotCallback);
            } catch (SecurityException | IllegalStateException failure) {
                Log.w(TAG, "Screen capture callback unregistration failed", failure);
            }
            callbackRegistered = false;
        }
        super.onStop();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        outState.putInt(COUNT_KEY, callbackCount);
        outState.putLong(TIME_KEY, lastCallbackTime);
        super.onSaveInstanceState(outState);
    }

    private void refreshModuleStatus() {
        String ownScope = ModuleState.isOwnProcessHooked() ? "已加载" : "未检测到加载";
        String rootFlag;
        try {
            String value = new RuntimeFlag(getClassLoader()).read();
            rootFlag = "1".equals(value) ? "已开启" : "未读取到启用值";
        } catch (ReflectiveOperationException | SecurityException | LinkageError failure) {
            rootFlag = "无法读取（" + failure.getClass().getSimpleName() + "）";
            Log.w(TAG, "Cannot read runtime activation flag", failure);
        }
        moduleStatus.setText("本应用中的 LSPosed：" + ownScope
                + "\nRoot 模块本次开机开关：" + rootFlag
                + "\n系统框架拦截：需通过对照测试确认");
    }

    private void renderCallbackStatus() {
        String listener = callbackRegistered ? "已注册" : "未注册";
        if (registrationFailure != null) {
            listener = "注册失败（" + registrationFailure + "）";
        }
        String lastTime = lastCallbackTime == 0 ? "无"
                : DateFormat.getTimeInstance().format(new Date(lastCallbackTime));
        callbackStatus.setText("回调监听：" + listener
                + "\n已收到截屏通知：" + callbackCount + " 次"
                + "\n最近一次：" + lastTime);
    }

    private void addTitle(LinearLayout parent, String text, int size) {
        TextView title = addText(parent, text, size);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        title.setPadding(0, dp(18), 0, dp(8));
        title.setAccessibilityHeading(true);
    }

    private TextView addText(LinearLayout parent, String text, int size) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(size);
        view.setTextColor(Color.rgb(31, 35, 42));
        view.setLineSpacing(dp(3), 1f);
        view.setPadding(0, dp(5), 0, dp(9));
        view.setTextIsSelectable(true);
        parent.addView(view, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        return view;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
