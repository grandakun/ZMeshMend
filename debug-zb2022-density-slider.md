[OPEN] zb2022 density slider debug

- Session ID: `zb2022-density-slider`
- Symptom: 在 ZBrush 2022 中加载 `D:\Program Files\Pixologic\ZBrush 2022\ZStartup\ZPlugs64\ZMeshMend_ZScript.txt` 后，UI 有 `Fill Density` 滑杆，但无论怎么调，最终面数和顶点数都一样。
- Expected: 调整 `Fill Density` 后，补洞结果的面数/顶点数应随密度变化。

## Hypotheses

1. ZScript UI 已更新 `gFillDensity`，但保存到的配置文件不是核心 EXE 实际读取的那个文件。
2. ZScript 调起的 `zmeshmend_core.exe` 使用零参数模式，读取的是固定工作目录下的另一个配置文件，导致 UI 改动被忽略。
3. `Fill Density` 已写入配置，但当前操作路径没有走到 `triangulate_refine_and_fair_hole(... density_control_factor(...))` 这条分支。
4. ZBrush 2022 里的 `.zsc` 编译缓存或旧文件覆盖了新的 `.txt` 行为，导致面板显示和实际执行逻辑不一致。
5. 结果模型的“面数/顶点数显示”不是来自填充 patch，而是被后续导入/合并流程归一化，看起来像没变化。

## Evidence To Collect

- ZScript 写配置的目标路径
- ZScript 调 EXE 的工作目录和参数模式
- EXE 零参数模式读取的配置文件路径
- 安装目录里两个配置文件是否并存且内容不同
- 运行日志是否显示读取的是哪份配置

## Evidence Collected

- ZScript 在 `ResolvePaths` 中将 `configPath` 指向 `ZMeshMendData/zmeshmend_config.txt`，不是根目录的 `ZMeshMend_config.txt`。
- ZScript 在 `RunCGAL` 中先 `SaveConfig`，再用 `LaunchAppWithFile` 直接启动 `zmeshmend_core.exe`，没有传命令行参数。
- `zmeshmend_core.cpp` 零参数模式会先把工作目录切到 EXE 所在目录，然后固定读取 `zmeshmend_config.txt`。
- 安装目录中同时存在两份配置：
  - `ZPlugs64/ZMeshMend_config.txt`：普通文本，内容完整。
  - `ZPlugs64/ZMeshMendData/zmeshmend_config.txt`：长度固定 4096 字节，但从 `removeSmallF` 开始出现大量 `00` 空字节。
- 损坏文件意味着 `fillDensity=...` 这一行根本没有以有效文本形式落盘，核心 EXE 自然读不到。

## Current Conclusion

最可能的根因是：ZScript 的 `SaveConfig` 用单个字符串变量 `cfgBuf` 拼整份配置，再写入固定 4096 字节 memblock。该字符串在 ZScript 环境下被截断，导致 `zmeshmend_config.txt` 只写入前半段文本，后半段被 `NUL` 字节填充。由于 `fillDensity` 位于被截断区域之后，UI 滑杆虽然改变了 `gFillDensity`，但核心程序读取到的配置始终没有这项，因此补洞面数/顶点数不变。
