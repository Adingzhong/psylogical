# N-back Battery (B1–B4)

本项目为**视觉情景图片版 N-back 工作记忆测验电池**，面向老年人群（HC / SCD / MCI / 早期AD）。

- **B1：0-back（目标图比较）**：先学习 1 张“目标图”，随后在提示出现时判断“刚刚图片”与目标图的关系（相同 / 相似 / 不同）。
- **B2：1-back（和上一张比较）**：提示出现时判断“刚刚图片”与“上一张图片”的关系（相同 / 相似 / 不同）。
- **B3：1-back（图片作答版）**：提示出现后弹出问题窗口，屏幕显示 3 张图片，从中选出“上一张出现过的那张”（最符合上一张）。
- **B4：2-back（常规 2-back）**：图片连续出现；当“当前图片”与“前两张（倒数第二张）”完全相同，需按固定键或点击固定按钮；不相同则不操作。

> 说明：若文档与程序不一致，以程序为准。

---

## 1) 运行环境

- Python 3.x
- PsychoPy（建议使用 PsychoPy Standalone，或在 conda/venv 中安装 `psychopy`）
- 依赖：`numpy`（PsychoPy 通常会自动带上）

---

## 2) 目录结构（必须保持相对路径）

脚本内部通过 `Path(__file__).resolve().parents[1]` 自动定位项目根目录，因此请保持如下结构：

```
N-back/
├─ run/
│  ├─ run_all.py
│  ├─ run_B1_last.py
│  ├─ run_B2_last.py
│  ├─ run_B3_last.py
│  └─ run_B4_last.py
├─ lists/
│  ├─ B1_ListA.csv
│  ├─ B2_ListA.csv
│  ├─ B3_ListA.csv
│  └─ B4_ListA.csv
├─ stimuli/
│  ├─ B1/ListA/*.png
│  ├─ B2/ListA/*.png
│  ├─ B3/ListA/*.png
│  └─ B4/ListA/*.png
├─ assets/
│  └─ instruction/
│     ├─ 1.png      # 总指导语
│     ├─ 2.png      # 休息页
│     ├─ B1_1.png   # B1 指导语
│     ├─ B2_1.png   # B2 指导语
│     ├─ B3_1.png   # B3 指导语
│     └─ B4_1.png   # B4 指导语
└─ result/
   ├─ raw/
   └─ summary/
```

---

## 3) 快速运行

### 3.1 运行完整电池（推荐）

进入 `run/` 目录运行：

```bash
python run_all.py
```

运行后会依次执行 B1 → 休息 → B2 → 休息 → B3 → 休息 →（满足条件则进入）B4。

### 3.2 单独运行某个 block

```bash
python run_B1_last.py
python run_B2_last.py
python run_B3_last.py
python run_B4_last.py
```

每个脚本都支持**独立运行**（会自己创建窗口），也支持被 `run_all.py` 调用（复用同一个窗口，保证风格一致）。

---

## 4) 交互规则（对老年被试友好）

- 所有过场页（开始/休息/练习结束等）都支持：
  - **按空格继续**；或
  - **点击/触摸屏幕继续**。
- 为避免误触，过场页设置了**最短等待时间**（例如 0.8 s）后才允许继续。

---

## 5) List 文件说明

### B1 / B2（3 选项：相同 / 相似 / 不同）

CSV 列（示例）：

- `trial_index, phase, image, cond, correct, stim_dur, resp_deadline, isi, feedback`

含义：
- `phase`：`practice` / `main`
- `cond`：`same` / `similar` / `different`
- `correct`：正确答案（同上）
- `stim_dur`：图片呈现时长（秒）
- `resp_deadline`：最大反应时间窗口（秒）
- `isi`：试次间隔（秒）
- `feedback`：练习阶段是否给反馈（1=给）

### B3（1-back，图片作答）

CSV 列（示例）：

- `trial_index, phase, event, image, lag1_true, opt1, opt2, opt3, correct_opt, stim_dur, resp_deadline, isi, feedback`

含义：
- `event`：`stim`（只呈现图片）或 `probe`（出现提示并弹出 3 选项问题窗）
- `lag1_true`：上一张真实图片路径（记录用）
- `opt1~opt3`：问题窗 3 个候选图片路径
- `correct_opt`：正确选项（1/2/3）

### B4（2-back，按键/按钮）

CSV 列（示例）：

- `trial_index, phase, n, image, cond, correct, stim_dur, resp_deadline, isi, feedback`

含义：
- `n`：2
- `correct`：`press`（应按）/ `none`（不应按）/ `na`（warmup，不计分）

---

## 6) 数据输出

### 6.1 单个 block 输出

每个 block 会在项目根目录下输出：

- `result/raw/`：逐试次原始数据 CSV
- `result/summary/`：
  - B1/B2 会额外输出 block 级汇总 CSV（正确率、平均反应时等）
  - B3/B4 的汇总信息主要由 `run_all` 汇总（但会有各自 raw）

### 6.2 run_all 总汇总

`run_all.py` 会在：

- `data/summary/summary_<participant>_S<session>_<timestamp>.csv`

写入电池级汇总（包含每个 block 的 `acc / duration_s / status / out_raw` 等字段）。

---

## 7) B4 进入条件（run_all 控制）

`run_all.py` 支持按表现决定是否进入 B4（2-back）。典型逻辑：

- B3 完成时间 ≤ **270 秒（4分30秒）**
- 同时 B2、B3 的正确率 ≥ **0.80**

阈值可在 `run_all.py` 的 GUI 输入框中修改（若不需要门控，也可以选择“总是运行 B4”）。

---

## 8) 常见问题排查

- **提示找不到图片/列表**：检查目录结构是否与上面的树一致；尤其是 `lists/`、`stimuli/`、`assets/` 是否与项目根目录同级。
- **CSV 乱码**：建议使用 `UTF-8 with BOM (utf-8-sig)` 编码保存（当前脚本按 `utf-8-sig` 读取）。
- **图片加载卡顿**：确认 `PRELOAD_IMAGES=True`（脚本中已有预加载设置），并尽量把刺激图放在本地磁盘。

---

## 9) 联系与维护

如需扩展新的 list（例如 ListB/ListC），按相同命名规则新增：

- `lists/B1_ListB.csv`、`lists/B2_ListB.csv`、...
- 并把对应图片放入 `stimuli/<Block>/ListB/`。
