# 玩偶头部后脑加工样例

[成品 STL](head-finished.stl) 可在支持 STL 的 CAD 或切片软件中打开。另附 [毛坯](head-stock.stl)、[IGES 参考线](head-reference.igs)、[预览与侧剖](head-preview.png) 和 [加工参数输出](head-geometry.json)。

## 样例约定

- 两份输入使用同一局部毫米坐标系。`+X` 向右，`−Y` 朝脸，`+Y` 朝后脑，`+Z` 向上。头部外包络为 `68 × 56 × 59 mm`。毛坯由头、双耳、鼻口以及眼窝等几何组成。
- 黄基准为 `Z=20 mm` 的平面。从黄基准抬高 `7.5 mm` 在 `Z=27.5 mm` 取底边，斜边与水平夹角为 `53°`。上边由 `(-31,12,43)` 至 `(31,12,43)` 的有限 IGES 线段约束。
- 后脑加工段从 `Y=7 mm` 到 `Y=21 mm`。段内保留梯形及其下方的实际毛坯。预览蓝色标出部分加工面，侧剖取 `X=0.3 mm`。
- 数字几何验收使用 `0.0001 mm` 的槽位检查容差和 `0.01 mm³` 的体积记录精度。IGES 端点检查沿用程序的 `0.000001 mm` 容差。以上为本样例自选条件，物理加工公差尚未验证。

## 复现

在独立项目根目录运行，输出放入新目录。

```sh
head_output=$(mktemp -d)
python3 -m venv "$head_output/venv"
head_python="$head_output/venv/bin/python"
"$head_python" -m pip install -r requirements.txt 'Pillow>=10.1'
"$head_python" -B head-demo/build_stock.py "$head_output"
"$head_python" -B machine.py \
  --stl "$head_output/head-stock.stl" --igs "$head_output/head-reference.igs" \
  --yellow-z 20 --offset 7.5 --angle 53 --y-start 7 --y-end 21 \
  --out "$head_output/head-finished.stl" > "$head_output/head-geometry.json"
"$head_python" -B head-demo/render_preview.py "$head_output"
printf '%s\n' "$head_output"
```

## 数字网格实测

成品回读为单一闭合且定向一致的外壳。毛坯有 7,618 个三角面，成品有 7,678 个三角面。毛坯中完全位于 `Y<0` 的 6,024 个三角面在成品中逐面一致。毛坯体积为 `89,517.18 mm³`，成品为 `84,580.54 mm³`，切除 `4,936.64 mm³`。
