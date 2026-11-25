# STL 截面与梯形四点预览

| 入口 | 内容 |
|---|---|
| [加工算法与流程图](MACHINING.md) | 配对输入、调参和成品另存 |
| [斜顶成品](examples/sloped-machined-default.stl) · [验收记录](ACCEPTANCE.md) | 固定配对输入的五组参数回读 |
| [头部成品 STL](head-demo/head-finished.stl) · [头部样件](head-demo/README.md) · [成品回读验收](head-demo/ACCEPTANCE.md) | 毛坯、IGES、成品预览与剖面 |
| [审计基线](DELIVERY-AUDIT.md) · [增量复验](DELIVERY-RECHECK.md) | 已验证范围和待客户确认口径 |

## Clean-room 安装

从复制或解压后的 `stl-assembly/` 独立目录根执行；不依赖工作区父级路径。Python 3.9+：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/stl-preview --stl examples/box-ascii.stl --datum-z 0 --offset 5 --upper-z 10 --angle 45
.venv/bin/stl-machine --stl examples/sloped-stock.stl --igs examples/wide-reference.igs --yellow-z 0 --offset 7.5 --angle 53 --y-start 4 --y-end 16 --out /tmp/sloped-machined.stl
.venv/bin/python -IB -m unittest discover -s . -p 'test_*.py' -q
.venv/bin/python -IB head-demo/verify_finished.py
```

该安装为本地原型包，不含客户加工规则的断言。输入 STL 和 IGES 须先处于同一右手毫米参考系；不指定 `--frame` 时认为已摆正。提供 `--frame frame-example.json` 格式的共享原点和局部轴，程序同时变换 STL/IGES，输出仍是该局部系，不自动还原世界系。可选 `--ab-y-range MIN MAX` 只限制候选 A/B 搜索的截面 Y 条带；条带仅为显式选取器，不代表已识别“脸部”。`--offset` 是黄基准至截面的距离；`--igs-vertical-gap` 是截面平面至水平 IGES 线的正 Z 距离，二者互斥，且输出记录端点垂向测量对。

输入 STL 时，先在 CAD 中把模型摆到所需的局部坐标系：`+X` 向右，`Y` 为深度轴，`+Z` 向上。导出数值须以毫米为单位。STL 格式没有单位信息，程序按原数值读取坐标，沿用导出时的姿态和原点。

从独立项目根目录运行：

```bash
python3 -B preview.py --stl examples/box-ascii.stl --datum-z 0 --offset 5 --upper-z 10 --angle 45
python3 -B preview.py --stl examples/box-binary.stl --datum-z 0 --offset 5 --upper-z 10 --angle 45
python3 -B preview.py
python3 -B -m unittest discover -s . -p 'test_preview.py' -v
python3 -B -m unittest discover -s . -p 'test_stl.py' -v
```

前两条命令使用同一个 `30 × 20 × 15 mm` 盒体的两种 STL 表示。`--datum-z` 是基准高度，`--offset` 是从基准往上的距离，两者相加得到截面高度。`--upper-z` 是上边的绝对局部高度，`--angle` 是梯形斜边与水平线的夹角，单位为度。省略 `--stl` 时使用原内置盒体。

上述样件在 `z=5 mm` 处取截面，沿 `X` 找左右极值，以 `(x, z)` 输出候选四点 `A=(-15, 5)`、`B=(15, 5)`、`C=(-10, 10)`、`D=(10, 10)`，上边宽 `20 mm`。JSON 同时给出三维截面线段和对应极值点，可用于检查实际截面位置。四点是正视投影的候选梯形。若截面与三角面或三角边重合，现有算法会报错，可调整截面高度再预览。ASCII 读取支持常规单 `solid` 的逐行 STL，二进制读取要求文件长度与三角形数量一致。
