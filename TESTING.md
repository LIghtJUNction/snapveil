# v0.1.0 检查记录

日期：2026-10-19。

## 已执行

| 检查 | 实际结果 |
| --- | --- |
| `kam --version` | 真实 Kam 0.6.14，由固定源码提交构建 |
| `kam export prop src/snapveil/module.prop` | 通过；版本 `v0.1.0`、版本码 `1` |
| `kam validate` | 通过 |
| `kam check --fail-on-error --json` | 0 个错误，5 项启动阶段/属性写入提示，已人工核实 |
| ShellCheck 0.9.0 | 运行脚本、安装脚本、CLI 和构建 hooks 均通过 |
| Java 编译 | Java 17，`--release 8 -Xlint:all -Werror`，Android 35 SDK，通过 |
| `sh android/tests/run.sh` | 38 项 Java 行为检查通过 |
| `python3 -m unittest discover -s tests -v` | 23 个测试通过，其中 19 个脚本流程测试、4 个版本测试 |
| `kam build --release` | 通过，实际生成可刷入 ZIP |
| `tools/verify.py` | ZIP CRC、根目录元数据、脚本执行权限、APK 与校验值均通过 |
| Android `apksigner verify --verbose` | APK 的 v3 签名通过 |
| Android `zipalign -c 4` | 通过 |
| Android `aapt2 dump badging` | 包名 `best.lmm.snapveil`；版本 `v0.1.0`；版本码 `1`；最低 API 34；目标 API 35 |

Kam 的五项提示是服务、按钮、卸载的执行阶段，以及两处 `setprop` 使用。
属性写入只在普通命令中或等待 Android 启动完成之后执行。
卸载脚本的后台等待不会阻塞管理器在早期启动阶段的同步清理。
项目未关闭相应检查规则。

## 主机测试覆盖

- 精确启用值、实时开关变化、调用权限、异常后的恢复与失败时保留系统原行为。
- 安装失败、错误退出码、校验失败和缺失 APK 不会被报告成成功。
- 真正通过 `/bin/sh` 执行运行脚本，模拟 Android 的 `pm`、`getprop`、`setprop` 和 `screencap`。
- 暂停跨启动保存，升级保留私有图片和暂停标记。
- 私有图片的 600 权限、目录的 700 权限、原样导出。
- 错误、截断 PNG、路径越界、符号链接和错误参数的处理。
- 卸载立即返回给调用者，Android 操作延后执行。
- 版本正常递增、禁止降级、真实 Kam 元数据导出，以及导出失败时回滚两个文件。

这些测试验证脚本与 Java 决策代码。它们没有模拟完整的 Android 系统，也没有证明厂商 ROM 的运行效果。

## 源码核对

已检查 AOSP Android 14、15、16 的 `WindowManagerService.notifyScreenshotListeners(int)`、
`ActivityRecord.reportScreenCaptured()`、标准回调注册与 SystemUI 的图像保存路径。
`sys.` 属性的已有类型映射、系统框架读取权限，以及 Root 管理器的属性写入授权也已核对。
具体官方源码链接见 README 与 `android/README.md`。

## 尚未执行

- 手机上实际刷入、LSPosed 系统框架加载、截屏回调关闭/开启对照。
- 厂商 ROM 的三指截屏、侧边栏、长截图等专用入口。
- 普通应用、系统应用、多用户和工作资料中的真实兼容性。
- 真实相册监听和文件观察器的检测结果。
- GitHub Actions 的远程运行及模块仓库发布。

因此本版为首次测试交付，不标注“所有软件检测均已通过”。

## 构建结果

| 文件 | 大小 | SHA256 |
| --- | ---: | --- |
| `snapveil-v0.1.0.zip` | 21,671 字节 | `03bce9ad0e0b62e839ffddf6cfd9cda4dd6bb858b2ae647ba81121fee4577b9c` |
| `snapveil.apk` | 20,947 字节 | `8ad541b7a6da705d53ea047670f94cdb4ec98e3c8909484dca9ebd41ccad2ecf` |

APK 含项目开发签名。维护签名备份与公开源码分开保存；ZIP 的 SHA256 用于确认收到的文件内容。

## 2026-10-19 — GitHub Actions 发布流程补充检查

- 新增 `workflow_dispatch` 的 `bump=none/patch/minor/major`、`release`、`prerelease`。普通 push 和 PR 不会修改版本或发布。
- 使用临时裸 Git 仓库和模拟的 `gh` 命令，测试版本提交、tag、预发布、重复发布阻止、版本不符、校验值错误、非 `main` 分支等路径。
- 发布版本通过真实构建和校验后，才允许写入 `main` 并上传 Release。发布时必须使用仓库提供的持久 APK 签名文件，禁止使用随机开发签名。
- 以上测试不会访问真实 GitHub Release 写入接口。实际创建 Release 需要持有仓库权限并配置签名 Secrets 后通过手动工作流验证。
