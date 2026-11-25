# 独立复验记录

## 口径与状态

范围为当前 `stl-assembly/` 本地源码及内含合成件；毫米坐标。此复验不是客户件验收、生产签收或远端克隆/发布证明。

- **已确认**：项目根用 `python -m pip install .` 安装；包含预览/加工入口、样件、参数说明和完整测试。
- **已确认**：同一原点与右手正交轴对 STL 与 IGES 应用同一投影后，旋转平移回归在 23 项测试通过。输出坐标为 `local_mm`，不自动还原世界系。
- **已确认**：可用 `--ab-y-range MIN MAX` 限制截面 A/B 候选点 Y 范围。凸出部被限制条带排除时，全截面与所选条带计算的 B 不同。此参数不是自动分割脸部；同一范围内多个轮廓仍按 X 极值选择。
- **已确认**：`--offset` 与 `--igs-vertical-gap` 互斥。报告分别记黄基准到 A/B 平面的高度、A/B 平面到水平 IGES 线的高度，并给出线段两端垂向测量端点。该项仅是局部 +Z 距离，不是通用三维最短距。
- **已确认**：头部样件与独立成品验收脚本均保留；样件在临时目录运行成品回读验收通过。

## 干净目录复现

从归档中只解出 `stl-assembly/` 后进入其根目录运行，不依赖工作区父目录。成功的 clean-room 运行记录：macOS arm64、Python 3.9，在系统临时目录中解包；普通 `pip install .` 成功，预览和加工入口均运行，23 项测试全通过，头部 STL 回读验收通过。这里保存为已完成运行记录，不是本轮最终文件状态下的重新运行；其他平台和离线安装未验证。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/stl-preview --stl examples/box-ascii.stl --datum-z 0 --offset 5 --upper-z 10 --angle 45
.venv/bin/stl-machine --stl examples/sloped-stock.stl --igs examples/wide-reference.igs --yellow-z 0 --offset 7.5 --angle 53 --y-start 4 --y-end 16 --out /tmp/sloped-machined.stl
.venv/bin/python -IB -m unittest discover -s . -p 'test_*.py' -q
.venv/bin/python -IB head-demo/verify_finished.py
```

独立安装与本地样件脚本验证结果需由接收端再运行；本地验证记录和客户验收仍需区分。未配置或访问远端，也未发布。

## 待确认

需客户明确实际摆正基准与输出坐标、脸部 A/B 选取对象、测距端点/方向/投影定义、加工深度与保留侧、对照截面和制造/几何公差。支持的 IGES 实体子集和封闭单壳 STL 输入约束未扩大为通用 CAD 导入能力。
