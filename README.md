# SnapVeil

**拦截 Android 的标准截屏通知，并提供不写入公共相册的私有截屏命令。**

当前版本以 [`kam.toml`](kam.toml) 的 `[prop]` 为准；使用 [Kam](https://github.com/MemDeco-WG/Kam) 构建。
源码仓库：[LIghtJUNction/snapveil](https://github.com/LIghtJUNction/snapveil)。

这是已完成主机测试的首版，尚未做 Android 真机验证。不能保证所有软件、所有截屏检测方式都失效。

## 能做什么

| 路径 | 本版行为 |
| --- | --- |
| Android 14 起的标准截屏回调 | 在系统分发通知前拦截。作用于经过这一入口的应用，无需逐个勾选第三方应用。 |
| 新安装的应用 | 使用标准回调的应用走同一个系统入口，不需要包列表轮询。 |
| 系统显示“某应用检测到截屏” | 同时返回空的已通知应用名单，避免这一标准路径继续生成检测提示。 |
| 普通系统按键截屏 | 图像生成和保存仍由系统处理；保存进相册后，软件仍可能通过图片记录推断截屏。 |
| 本模块的私有截屏命令 | 用系统 `screencap` 保存到模块私有目录，不向 MediaStore 插入图片记录。 |
| 厂商私有接口、相册监听、文件观察、拥有 Root 的软件 | 不保证拦截。私有截屏也不承诺对其他 Root 软件不可见。 |

本版没有修改相册权限、图片查询或文件通知。普通照片和图片选择器不需要为了这个模块停用。
`FLAG_SECURE` 页面限制和录屏检测属于另外的功能，本版未改动。

## 需要的环境

- Android 14 或更高版本，最低 API 34。挂点已逐文件核对 AOSP 14、15、16；厂商系统需要实测。
- KernelSU、APatch 或 Magisk。使用管理器的模块安装功能。
- 能在你的 Android 版本上正常运行的 LSPosed 或兼容框架。
- 管理器按钮入口要求 Magisk 27008+、KernelSU 1.0.2+ 或 APatch 11039+。也可以直接打开 SnapVeil 应用。

安装包包含 Root 模块脚本和 `best.lmm.snapveil` 配套 APK。设备端不依赖 Python、Java 编译器、网络或常驻轮询程序。

## 安装

1. 用 Root 管理器安装 `snapveil-v0.1.0.zip`。请在 Android 系统运行时安装。
2. 安装脚本会安装 SnapVeil 配套应用。若 APK 安装失败，脚本会报错并中止。
3. 打开 LSPosed，启用 SnapVeil。勾选 **系统框架（android）** 和 **SnapVeil**。
4. 重启手机。
5. 打开 SnapVeil，按测试页说明做一次关闭/开启对照测试。

“系统框架”是实际保护入口；SnapVeil 自身作用域用于显示本应用是否被 LSPosed 加载。
只看到 APK 已安装或开关为 1，不能证明系统拦截已生效。
不需要给所有第三方应用增加 LSPosed 作用域。

如果配套 APK 后来被手动卸载，可以修复安装：

```sh
su -c '/data/adb/modules/snapveil/cli install-app'
```

然后重新确认 LSPosed 作用域并重启。

## 真机测试

1. 在 Root 管理器中停用 SnapVeil，重启。打开 SnapVeil 测试页并保持前台。
2. 用电源键和音量减键截屏。确认“已收到截屏通知”增加。这是未拦截时的对照。
3. 开启 Root 模块，确认 LSPosed 的系统框架作用域已启用，再重启。
4. 清零测试计数，用同样方式截屏。期望图片正常生成，通知计数保持 0。
5. 在你实际使用的软件中测试，并单独记录相册检测或厂商提示是否仍出现。

若第 2 步本来就没有回调，不能用后续的 0 次回调判断成功。该截屏方式、系统实现或页面状态可能没有发送标准通知。

问题记录请包含 Android 版本、系统名称、Root 管理器、LSPosed 版本、两次对照结果，以及 LSPosed 中以 `SnapVeil:` 开头的日志。

## 私有截屏

在有 Root 权限的终端运行：

```sh
su -c '/data/adb/modules/snapveil/cli capture 5'
```

命令等待 5 秒，便于切换到需要截取的页面，然后返回图片路径。延迟范围为 0–30 秒。
这是一种单独的截屏方式，不会改变你平时的系统快捷键。

图片保存在 `/data/adb/modules/snapveil/captures/`，目录权限为 `700`，图片为 `600`。
模块检查 PNG 的头部和结束标记，失败或中断时清理本次临时文件。
捕获前检查 100 张图片和 256 MiB 的保存额度，写入后再次检查总大小。超限时拒绝新图片，不自动删除旧图片。
这些是单次操作的空间检查；不要同时启动多个捕获命令。

列出图片：

```sh
su -c '/data/adb/modules/snapveil/cli list'
```

可从已授权的电脑导出到本地。把 `NAME.png` 替换成上一步列出的真实文件名：

```sh
adb exec-out su -c '/data/adb/modules/snapveil/cli export NAME.png' > shot.png
```

导出命令只输出原始图片字节。不会自动放入手机相册。
若你主动把图片放入共享存储，其他软件可能再次访问或识别它。

## 开关、卸载和升级

```sh
su -c '/data/adb/modules/snapveil/cli status'
su -c '/data/adb/modules/snapveil/cli disable'
su -c '/data/adb/modules/snapveil/cli enable'
```

`cli disable` 立即清除运行开关，并保存暂停标记。`cli enable` 解除暂停；系统框架 hook 必须已经加载。
Root 管理器里的停用、移除操作按管理器的一般流程在重启后生效。

运行开关是非持久属性 `sys.snapveil.active`。已停用的模块在新一次开机不会设置它，APK 即使仍在，也不会因此继续拦截。
启动脚本等待 Android 启动完成，设置一次开关后退出。
没有 `post-fs-data` 阶段的属性写入，也没有后台按应用轮询。

升级保留本模块的 `captures/` 与 `state/`，不创建其他散落在 `/data/adb` 下的组件或历史版本目录。
每次开机只保留一份服务日志：`state/service.log`。

**卸载前先导出需要的私有图片。** 管理器会删除整个模块目录。卸载脚本会在 Android 启动完成后清理配套 APK，等待最多 240 秒，不阻塞开机。
如果系统始终未启动完成，或 PackageInstaller 拒绝操作，配套 APK 可能需要手动卸载；此时模块不会设置启用属性。

## 实现依据

系统 hook 位于 `WindowManagerService.notifyScreenshotListeners(int)`。
启用时先保留系统原有的调用权限检查，再返回空列表。
这阻止标准回调分发，也令系统得到空的已通知应用名单。
找不到预期方法、无法读取开关或无法检查调用权限时，模块保留系统原来的方法行为并记录错误。

`DETECT_SCREEN_CAPTURE` 是普通安装权限，不是 AOSP 14–16 中可配置的 AppOp。项目没有使用无效的 `appops set ... DETECT_SCREEN_CAPTURE` 或 `pm revoke` 命令。

可核验来源：

- [Android 官方截屏检测说明](https://developer.android.com/about/versions/14/features/screenshot-detection)
- [Android 14 WMS 源码](https://android.googlesource.com/platform/frameworks/base/+/android-14.0.0_r1/services/core/java/com/android/server/wm/WindowManagerService.java)
- [Android 15 WMS 源码](https://android.googlesource.com/platform/frameworks/base/+/android-15.0.0_r1/services/core/java/com/android/server/wm/WindowManagerService.java)
- [Android 16 WMS 源码](https://android.googlesource.com/platform/frameworks/base/+/android-16.0.0_r2/services/core/java/com/android/server/wm/WindowManagerService.java)
- [SystemUI 的截图保存实现](https://android.googlesource.com/platform/frameworks/base/+/android-14.0.0_r1/packages/SystemUI/src/com/android/systemui/screenshot/ImageExporter.java)
- [系统属性 `sys.` 的已有类型映射](https://android.googlesource.com/platform/system/sepolicy/+/android-16.0.0_r1/private/property_contexts)
- [LSPosed 作用域说明](https://github.com/LSPosed/LSPosed/wiki/Module-Scope)

## 从源码构建

需要 Python 3.11+、Java 17、Android SDK 平台 35、Build Tools 35.0.0，以及 Kam。
本次使用的 Kam 源码提交是 `3835842ca90cefc621383e72e01078481122aa30`，版本为 `0.6.14`。

```sh
cargo install --git https://github.com/MemDeco-WG/Kam --rev 3835842ca90cefc621383e72e01078481122aa30 --locked kam
sdkmanager 'platforms;android-35' 'build-tools;35.0.0'
export ANDROID_HOME=/path/to/android-sdk
kam export prop src/snapveil/module.prop
kam validate
kam check --fail-on-error
sh android/tests/run.sh
python3 -m unittest discover -s tests -v
kam build --release
python3 tools/verify.py
```

构建脚本从官方地址取得编译用 Xposed API 82，并校验固定 SHA256；它不会把 Xposed 实现打进 APK。
也可用 `XPOSED_API_JAR` 指向已经下载的同一文件。

`kam.toml` 是版本的唯一来源，APK 的版本与 ZIP 内 `module.prop` 同步。

```sh
python3 tools/bump.py patch
# 也可用 minor、major 或明确版本，例如 0.2.0。
```

bump 会让 `versionCode` 加 1，并限制在 APK 可用范围内；普通构建不会自动涨版本。
当前 Kam 0.6.14 的 `kam version` 会生成 13 位毫秒时间值，本项目使用自己的小脚本避免 APK 版本码溢出。

### 签名和工作流

默认在 `.local/signing/snapveil.p12` 生成项目专属开发签名，密码为 `android`，别名为 `snapveil`。
私钥不进入 Git 或可刷入 ZIP。**保留这个文件，后续 APK 更新需要同一签名。**
交付的维护包含单独的私钥备份；公开源码时不要公开维护包中的 `private/` 目录。

正式构建可指定自己的签名文件：

```sh
export SNAPVEIL_KEYSTORE=/private/path/snapveil.p12
export SNAPVEIL_KEYSTORE_PASSWORD='your-password'
export SNAPVEIL_KEY_ALIAS=snapveil
kam build --release
```

`init.yml` 与 `exec.yml` 使用 Kam 检查和构建，普通 push / PR 只进行测试，不自动更改版本或创建发布。

### GitHub Actions 手动版本与发布

从 **Actions → Build SnapVeil → Run workflow** 选择 `main`，然后设置：

| 参数 | 选项 | 效果 |
| --- | --- | --- |
| `bump` | `none`（默认）、`patch`、`minor`、`major` | 仅在不是 `none` 时调用 `tools/bump.py`，同步修改 `kam.toml` 与 `module.prop`；构建成功后提交到 `main` |
| `release` | `false`（默认）或 `true` | `true` 时发布当前或新版本的 GitHub Release，上传 ZIP、APK 与 SHA256SUMS |
| `prerelease` | `false`（默认）或 `true` | 只在 `release=true` 时可设为 `true`，用于测试版 |

常见操作：`patch + release=true` 发布修订版；`none + release=true` 发布已定版本；`minor + release=false` 只提交版本变更。`none + false` 只构建，适合检查。
手动更改版本或发布必须使用 `main`，PR 和常规 push 不会发布。构建、单元测试与包校验通过之后才提交 bump 并发布；已存在的 Release 不会被覆盖；已有标签指向其他提交时会中止。

**发布前必须配置两个仓库 Actions Secrets**：

- `SNAPVEIL_KEYSTORE_BASE64`：保留的 `snapveil.p12`（与之前 APK 相同签名），对文件执行 `base64 -w0 snapveil.p12` 所得的单行内容。macOS 可用 `base64 < snapveil.p12 | tr -d '\n'`。
- `SNAPVEIL_KEYSTORE_PASSWORD`：该 PKCS#12 签名文件的密码。签名别名固定为 `snapveil`。

在仓库 **Settings → Secrets and variables → Actions** 添加这两个 Secret。工作流会用 `keytool` 检查提供的签名文件；任何 Secret 缺失会阻止发布，不会意外拿随机生成的开发签名发布。
**不要将私钥或 Base64 私钥文本提交到 Git、Issue、Actions 日志或公开 Release。**
发布 ZIP 内的 APK 与单独提供的 APK 使用同一签名。若签名与旧版不同，Android 无法直接覆盖更新原有配套应用。只有构建成功并持有仓库写入权限时，工作流才可以创建 tag 和 Release。

正式发布使用不可覆盖版本：`vX.Y.Z` 标签、同名 ZIP 和 Release，之后应通过新版本修复问题，不能重用旧版本号。

如要收录到 KernelSU 模块仓库，应使用 `snapveil` 作为仓库名，保持版本码递增，并按[模块仓库示例](https://modules.kernelsu.org/en/modules/example_module_demo/)启用不可变发布。
当前没有设置尚不存在的下载地址或自动更新地址，也未声明已完成仓库上架。

## 检查记录

见 `TESTING.md`。所有主机检查与真实手机验证分开记录。

许可：MIT。
