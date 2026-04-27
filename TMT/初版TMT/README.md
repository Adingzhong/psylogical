# 连线测试（DTMT）PsychoPy 程序

本项目是一套基于 **PsychoPy Standalone 2025** 的“连线/交替连线”认知范式电池子任务程序，包含 **A0、A1、B1、B2、B3、B4** 六个任务，并提供 `run_all_updated.py` 作为整套流程（含练习与休息页）的入口。

---

## 1. 项目入口与脚本说明

### 1.1 推荐入口：整套流程运行
- `run_all_updated.py`  
  按既定流程串联：
  - 欢迎页（`stimuli/zdy/all_1.png`）
  - 通用操作方法（`stimuli/zdy/1.png`）
  - 练习说明（`stimuli/zdy/all_2.png`）
  - 练习 1→2→3→4（程序内置）
  - 正式提示（`stimuli/zdy/2.png`；若缺失则回退 `all_3.png`）
  - 正式任务：A0 → B2 → B1 → A1 → (B3/B4 顺序由组别决定)
  - 任务间休息（优先 `stimuli/zdy/3.png`；若缺失回退 `stimuli/zdy/A0_2.png`）
  - 结束页（`stimuli/zdy/all_4.png`）

### 1.2 单任务脚本（可单独运行/调试）
- `run_A0_updated.py`：A0（数字顺序连线）
- `run_A1_updated.py`：A1（水果图标上的数字顺序连线；以数字规则为主）
- `run_B1_updated.py`：B1（阿拉伯数字 ↔ 汉字数字 交替连线）
- `run_B2_updated.py`：B2（方形 ↔ 圆形 交替连线，含诱饵/干扰节点）
- `run_B3_updated.py`：B3（水果 A/B 交替，双套同数字）
- `run_B4_updated.py`：B4（水果 A/B 交替，带顺序/类型规则）

> 说明：`run_all_updated.py` 会优先导入 `*_updated.py`，若缺失则回退到 `*_last.py`。

---

## 2. 环境与运行方式（PsychoPy Standalone 2025）

### 2.1 不使用 pip 的推荐方式
本项目面向 **PsychoPy Standalone 2025**，一般不需要手动 `pip install`。

**方式 A：PsychoPy Coder 中运行（推荐）**
1. 打开 PsychoPy
2. 打开 `Coder`
3. `File → Open...` 选择 `run_all_updated.py`
4. 点击运行（Run）

**方式 B：命令行运行（使用 Standalone 自带 Python）**
- 在项目根目录执行（示例）：
```bash
python run_all_updated.py
```
或使用 PsychoPy 自带的 python 可执行文件（路径以你本机安装为准）：
```bash
<psychopy_python> run_all_updated.py --subject S001 --session SES1 --group 1
```

### 2.2 平板/触屏实测建议
- 建议使用 **Windows 平板 + 触控笔/手指**（PsychoPy Standalone 原生支持桌面系统）。
- 尽量关闭系统级手势/弹窗干扰；正式测量建议全屏运行。
- 若全屏分辨率与设计分辨率不一致，程序会按实际屏幕尺寸运行（PsychoPy 可能提示显示器规格 warning 属正常现象）。

---

## 3. 参数与被试信息

### 3.1 `run_all_updated.py` 常用命令行参数
- `--subject`：被试编号（例如 `S001`）
- `--session`：会话编号（例如 `SES1`）
- `--age`：年龄（可留空）
- `--group`：组别（`1` 或 `2`；决定 B3/B4 的顺序）
- `--layout`：布局编号（`1/2/3`；`0` 表示自动分配）
- `--windowed`：窗口模式（调试用）
- `--screen`：屏幕索引（多屏时指定）
- `--hard_limit`：每个任务限时（秒）

> 若未提供 `--subject`，程序会弹出对话框让你填写 `subject_id / session_id / age / group`。

### 3.2 文件命名里的 “S001 / SES1 / layout2” 是什么？
以输出文件名为例：
`S001_SES1_B4_layout2_20251228_125720_summary.csv`

含义如下：
- **S001**：被试编号 `subject_id`
- **SES1**：会话编号 `session_id`
- **B4**：任务类型 `task_type`
- **layout2**：布局编号 `layout_id`（1~3）
- **20251228_125720**：本次运行的时间戳（年月日_时分秒）
- **summary / segments / raw_path / layout_nodes / event_marker**：输出文件类型（见下一节）

---

## 4. 目录结构要求（关键）

项目根目录建议如下（脚本会“向上查找” `stimuli/` 或 `layouts/` 来确定根目录）：

```text
project_root/
  run_all_updated.py
  run_A0_updated.py
  run_A1_updated.py
  run_B1_updated.py
  run_B2_updated.py
  run_B3_updated.py
  run_B4_updated.py

  layouts/
    A0/ ...
    A1/ ...
    B1/ ...
    B2/ ...
    B3/ ...
    B4/ ...

  stimuli/
    zdy/
      all_1.png
      1.png
      all_2.png
      2.png
      3.png            (休息页，推荐)
      all_4.png
      A0_1.png A0_2.png
      A1_1.png
      B1_1.png
      B2_1.png
      B3_1.png
      B4_1.png         (若与 B3_1 相同也可复用图，但文件名需存在)
    ...（水果/图形等节点刺激图片，供 layouts JSON 引用）

  results/
    ...（程序自动生成）
```

---

## 5. 输出数据说明（results）

每次运行每个任务，都会在 `results/<TASK_TYPE>/` 下生成一组 CSV 文件（UTF-8 with BOM，Excel 可直接打开）：

### 5.1 输出文件一览
- `*_summary.csv`：**本次任务的总体指标**（完成与否、完成时长、错误数等）
- `*_segments.csv`：**逐段/逐事件日志**（每一段从哪个节点到哪个节点、耗时、距离、是否错误、错误类型）
- `*_raw_path.csv`：**高频轨迹采样**（时间戳、坐标、是否按下/触摸）
- `*_layout_nodes.csv`：**布局节点表**（用于复现实验：每个节点的类型/数值/坐标/刺激文件、布局文件 hash）
- `*_event_marker.csv`：**关键事件标记**（任务开始/结束/提示/退出等）

此外，整套流程 `run_all_updated.py` 还会生成：
- `results/PRACTICE/<subject>_<session>_practice.csv`：练习 1→2→3→4 的轨迹采样
- `results/<subject>_<session>_runall_log.txt`：run_all 流程日志（按任务顺序记录）

### 5.2 核心字段如何理解（以 B4 为例）
- `summary.csv` 常见字段：
  - `finished`：是否完成（1=完成，0=未完成/中止/超时）
  - `completion_time_s`：完成用时（秒）
  - `total_errors / order_errors / type_errors`：错误总数及分类型
  - `hard_limit_s`：限时（秒）
  - `layout_file / layout_sha1`：使用的布局文件路径与内容校验（便于版本追踪）
- `segments.csv` 常见字段：
  - `kind`：`SEGMENT`（正确段）/ `ERROR`（错误事件）/ `MARKER`（标记）
  - `from_* / to_*`：段起点与终点信息（标签、类型、数值）
  - `duration_ms`：该段耗时（毫秒）
  - `path_length_px`：轨迹长度（像素）
  - `error_type`：错误类型（例如 `order` / `type` / `invalid_start` 等）
- `raw_path.csv` 常见字段：
  - `ts_ms`：相对任务开始的时间戳（毫秒）
  - `x_px / y_px`：屏幕像素坐标
  - `is_pen_down`：是否按下/触摸（1=按下，0=抬起）

---

## 6. 开发/改动提醒（常用）

### 6.1 更换指导语呈现（图片）
- 所有“说明/指导语/休息页”都以 `stimuli/zdy/*.png` 的形式加载。
- **尽量只改图片内容，不改文件名**：脚本里是按固定文件名查找的（如 `B2_1.png`、`3.png`）。
- 若缺失某张图片：部分页面会回退到备用图；再缺失则显示 “Image missing ...” 的文本提示。

### 6.2 更换布局（JSON）
- 布局文件位于 `layouts/<TASK_TYPE>/...json`
- 输出里会记录 `layout_file` 与 `layout_sha1`，方便你做版本控制与复现。

---

## 7. 常见问题（FAQ）

### Q1：全屏运行提示 “Monitor specification not found”？
PsychoPy 常见提示，不一定影响实验。正式环境可在 PsychoPy 的 Monitor Center 里配置显示器参数，或继续忽略。

### Q2：全屏请求分辨率与实际屏幕不一致？
PsychoPy 会按实际屏幕尺寸运行，并提示一次 warning。  
若要调试布局/手感，建议先加 `--windowed` 观察。

### Q3：如何中途退出？
一般可按 `ESC` 退出（不同脚本对 ESC 的处理略有差异）。退出前已写入的数据会保留，便于排查。

---

## 8. 版本信息
- 运行平台：PsychoPy Standalone 2025
- 当前整套流程入口：`run_all_updated.py`
