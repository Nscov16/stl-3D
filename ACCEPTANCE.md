# 非盒体合成加工验收记录

## 口径与结论

**已确认**：以下结果只针对仓库合成样件，单位均为 mm / mm² / mm³。固定输入为 `examples/sloped-stock.stl` 与 `examples/wide-reference.igs`，局部坐标 +X 向右、Y 为深度、+Z 向上；黄基准 `yellow_z=0`，加工区间 `Y=[4,16]`，其余坐标与文件不变。每种成品均从 ASCII STL 回读后测量；下表的顶宽和角度从 Y=4/16 的上边交点反算，体积以三角网格带符号体积回读，解析值另按截面积分计算。数值容差：报告数值显示到 6 位小数；程序输入线端点检查为 0.000001 mm。

**已确认**：输出闭合且定向一致，回读带符号体积为正。原毛坯在加工区间外的斜顶截面保持不变；如 Y=2 与 Y=18，原截面高度分别为 20.4 和 23.6，完整截面积分别为 612 和 708 mm²。范围外总保留体积为 `8 × 30 × 22 = 5280 mm³`。

## 五组测量

原毛坯顶面为 `z=20+0.2y`，固定 IGES 参考线为 `(-15,10,14) → (15,10,14)`。对偏移 `o` 与角度 `a`：斜边内收 `s=(14-o)/tan(a)`，上边宽 `w=30-2s`；加工带截面保留面积 `A=30o + (30+w)(14-o)/2`，成品体积解析值 `V=5280+12A`。

| 配置 | 偏移/底边 Z | 角度实测 | 上边 X 实测 | 顶宽解析/回读 (mm) | 体积解析/回读 (mm³) |
|---|---:|---:|---|---:|---:|
| 默认 | 7.5 | 53.000000° | [-10.101899, 10.101899] | 20.203797 / 20.203797 | 9937.948097 / 9937.948097 |
| 仅改角度 | 7.5 | 55.000000° | [-10.448651, 10.448651] | 20.897302 / 20.897302 | 9964.994778 / 9964.994778 |
| 仅改偏移 | 5 | 53.000000° | [-8.218014, 8.218014] | 16.436027 / 16.436027 | 9587.545463 / 9587.545463 |
| 仅改角度 | 7.5 | 52.000000° | [-9.921643, 9.921643] | 19.843287 / 19.843287 | 9923.888187 / 9923.888187 |
| 仅改偏移 | 10 | 53.000000° | [-11.985784, 11.985784] | 23.971568 / 23.971568 | 10175.317622 / 10175.317622 |

**已确认**：每组回读顶边端点按解析内收量吻合，角度由 `(14-o)/(15-|x_top|)` 反算；解析与网格回读体积差小于 `0.000001 mm³`。默认成品示例保存在 [`examples/sloped-machined-default.stl`](examples/sloped-machined-default.stl)，ASCII STL，36 个三角面，回读体积 9937.948097 mm³。

## 复现

从独立项目根目录执行。依赖版本见 `requirements.txt`；输出目录需为新建目录或指定未存在文件。

```bash
python3 -m venv /tmp/stl-machining-venv
/tmp/stl-machining-venv/bin/python -m pip install -r requirements.txt
mesh_python=/tmp/stl-machining-venv/bin/python

run_sloped_demo() {
  result_name=$1
  shift
  "$mesh_python" -B machine.py \
    --stl examples/sloped-stock.stl \
    --igs examples/wide-reference.igs \
    --yellow-z 0 --y-start 4 --y-end 16 \
    --out "/tmp/$result_name.stl" "$@"
}
run_sloped_demo sloped-default --offset 7.5 --angle 53
run_sloped_demo sloped-angle-55 --offset 7.5 --angle 55
run_sloped_demo sloped-offset-5 --offset 5 --angle 53
run_sloped_demo sloped-angle-52 --offset 7.5 --angle 52
run_sloped_demo sloped-offset-10 --offset 10 --angle 53
```

## 真实件待提供

**未知**：以上合成件数据不能证明客户件规则或现场加工满足要求。开始实件验收至少需提供：

1. 配对 STL 与 IGES 原文件，确认两者同一坐标系、毫米单位、局部轴向及原点；
2. 黄基准的定义和数值、偏移、角度，以及允许的参数范围；
3. 加工 Y 起止位置、应保留/切除侧和 IGES 参考线所代表的实体边；
4. 预期截面、顶宽/关键尺寸或可信 CAD/测量基准，以及各项公差；
5. 对网格闭合、表面偏差、最小特征和允许加工结果的验收要求。

当前验证使用合成非盒体 STL 与单条 IGES 110 直线；不覆盖客户加工规则、现场刀路、真实公差、自交/多壳网格及曲面离散误差。
