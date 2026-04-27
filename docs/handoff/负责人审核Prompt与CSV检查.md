# 负责人审核 Prompt 与 CSV 检查清单

## 用法

这份文档用于把 GitHub 仓库交给原范式负责人后，让他们直接用 Codex / ChatGPT 辅助审核。

建议每位同学只复制自己那一段 prompt。不要一次性让模型重扫全仓库。

共同入口文件：

- `README.md`
- `docs/handoff/README.md`
- `docs/handoff/认知测评平台_协作者审核说明.md`
- `docs/handoff/认知测评平台_Codex交接说明.md`
- `docs/handoff/认知测评平台_修改记录与交接说明.md`
- `docs/handoff/CSV输出结构审核索引.md`

本次审核重点不是重新开发，而是做科研验证：

1. 当前 Web 实现是否仍符合原始范式逻辑；
2. 参数、材料、流程、难度是否有文献或试测依据；
3. 老年人/MCI 风险人群适配是否合理；
4. CSV/JSON 输出是否足够支持后续分析；
5. 哪些问题必须由原负责人确认。

## 通用输出模板

每位负责人最终建议按这个表交付：

| 范式 | 当前设置 | 与原设计差异 | 是否合理 | 证据位置 | CSV/数据输出检查 | 修改建议 | 优先级 |
|---|---|---|---|---|---|---|---|
| 例 | 当前网页怎么做 | 和原文档差在哪里 | 合理/需修改/不确定 | 文件路径 | 字段是否够、命名是否清楚、能否分析 | 简短建议 | 高/中/低 |

CSV/数据输出检查至少回答：

- 是否能区分练习、正式、引导、休息或不同 block；
- 是否记录 trial 编号、条件、材料编号、正确答案、被试反应、正确率、反应时；
- 是否能识别 timeout、漏按、误按、跳过、撤回、清空等特殊事件；
- 是否有足够字段用于排除无效 trial；
- 字段命名是否容易被后续统计脚本理解。

## 发给刘晓烨

```text
晓烨，你现在协助审核“老年范式综合2”GitHub 仓库中你负责的两个范式：空间导航、看眼读心/RMET。

请先阅读：
1. docs/handoff/README.md
2. docs/handoff/认知测评平台_协作者审核说明.md
3. docs/handoff/负责人审核Prompt与CSV检查.md
4. 如需细节，再看 docs/handoff/认知测评平台_修改记录与交接说明.md

你的任务不是写新功能，也不是直接改代码，而是做科研验证和交接审核：

一、空间导航
请重点看：
- 原始文档：开发文档/视空间导航产品文档.md；空间导航/视空间范式/
- 当前实现：web-battery/paradigms/visuospatial/；web-battery/audio/visuospatial/
- 证据：4月6日 反馈/09_空间导航.md；UX图片/脚本/脚本_空间导航.md

请判断：
- 任务流程、地图/路线呈现、guided 引导练习是否合理；
- 练习题数、练习轮数、反馈方式、正式阶段蓝色点击点是否会影响策略；
- 网格、路线、指导语、难度是否适合老年人/MCI 风险人群；
- 当前实现和原设计不一致的地方是否可以接受。

CSV/数据输出也要检查：
- 是否能区分 demo / guided / practice / formal；
- 是否记录路线、目标位置、点击位置、误差、反应时间、是否通过练习；
- guided 阶段数据是否需要在分析时排除或单独标记。

二、看眼读心/RMET
请重点看：
- 原始材料：社会认知/RMET【以此为基准】/RMET.py；社会认知/RMET【以此为基准】/marterial/options_new.xlsx
- 当前实现：web-battery/paradigms/rmet/；web-battery/stimuli/rmet/；web-battery/audio/rmet/

请判断：
- 当前 1 个练习题 + 10 个正式题是否足够；
- 图片材料、选项设置、题目难度是否符合 RMET/社会认知测量目标；
- 3 选项中文版是否需要补文献或材料来源说明；
- 呈现方式是否适合老年人。

CSV/数据输出也要检查：
- 是否记录图片编号、选项、正确答案、被试选择、正确率、反应时；
- 是否能区分练习和正式；
- 是否足够支持后续 RMET 得分和题目难度分析。

输出请用表格，重点写：
当前设置、与原设计差异、是否合理、证据位置、CSV 输出是否足够、需要修改或确认的问题。
```

## 发给许一桦

```text
一桦，你现在协助审核“老年范式综合2”GitHub 仓库中你负责的三个范式：Flanker、SART、VSTMB。

请先阅读：
1. docs/handoff/README.md
2. docs/handoff/认知测评平台_协作者审核说明.md
3. docs/handoff/负责人审核Prompt与CSV检查.md
4. 如需细节，再看 docs/handoff/认知测评平台_修改记录与交接说明.md

你的任务不是写新功能，也不是直接改代码，而是确认当前 Web 实现是否仍符合你原来设计的范式逻辑。

一、Flanker / 箭头判断
请重点看：
- 原始文档：开发文档/Flanker开发文档.md
- 当前实现：web-battery/paradigms/flanker/；web-battery/stimuli/flanker/
- 证据：4月6日 反馈/01_Flanker.md；4月18日 修改/时间对比与原文核实.md；Krueger 2009 PDF

请判断：
- 4000ms 反应窗口是否可以接受；
- 48 个正式 trial 是否保持；
- 刺激大小放大是否合理；
- ITI/ISI、练习 trial、正式 trial、正确率和反应时指标是否符合研究目的。

CSV/数据输出也要检查：
- 是否记录 trial、block、条件、刺激类型、正确答案、被试反应、accuracy、RT；
- 是否记录 timeout、anticipatory、rt_over_2s、rt_over_3s；
- 这些字段是否足够后续按 2000ms/3000ms/4000ms 做不同筛选。

二、SART / 数字注意
请重点看：
- 原始文档：开发文档/SART产品文档.md
- 当前实现：web-battery/paradigms/sart/
- 证据：4月6日 反馈/02_SART.md；Robertson 1997 PDF

请判断：
- 1250ms 数字 + 1250ms 空屏周期是否保持；
- Go/No-go 比例、练习 trial、正式 trial、反应窗口是否合理；
- 按钮常驻和触控反馈是否会改变任务性质；
- 漏按、误按、正确率、反应时指标是否定义清楚。

CSV/数据输出也要检查：
- 是否记录 digit、Go/No-go、response_made、accuracy、error_type、RT；
- 是否能区分 omission 和 commission；
- 是否记录练习/正式、trial 编号和注意探针等信息。

三、VSTMB / 视觉短时记忆
请重点看：
- 原始文档：开发文档/VSTMB范式编写手册.pdf；VSTMB/VSTMB/README.md；VSTMB/VSTMB/config.json
- 当前实现：web-battery/paradigms/vstmb/；web-battery/stimuli/vstmb/
- 证据：4月6日 反馈/05_VSTMB.md；4月18日 修改/时间对比与原文核实.md；Parra 相关 PDF

请判断：
- Object / Color / Binding 三条件是否保留原逻辑；
- 刺激数量、呈现时间、保持间隔、探测方式是否合理；
- 练习通过率 70%、最多 2 次是否合理；
- 2-item Binding 是否存在“只记一个物体也能做”的策略问题。

CSV/数据输出也要检查：
- 是否记录 condition、study/probe 材料、位置、颜色、形状；
- 是否记录 same/different、response、accuracy、RT；
- 是否有足够字段计算 d-prime、A'、beta 或其他 SDT 指标；
- 是否能区分练习和正式。

输出请用表格，重点写：
当前设置、与原设计差异、是否合理、证据位置、CSV 输出是否足够、需要修改或确认的问题。
```

## 发给黄朝琮

```text
朝琮，你现在协助审核“老年范式综合2”GitHub 仓库中你负责的两个范式：图片记忆/N-back、连线测试/TMT。

请先阅读：
1. docs/handoff/README.md
2. docs/handoff/认知测评平台_协作者审核说明.md
3. docs/handoff/负责人审核Prompt与CSV检查.md
4. 如需细节，再看 docs/handoff/认知测评平台_修改记录与交接说明.md

你的任务不是重做范式，也不是直接改代码，而是确认当前 Web 版本是否仍符合你原来的范式逻辑和研究目标。

一、图片记忆 / N-back
请重点看：
- 原始文档：开发文档/N-back范式开发文档.md；开发文档/N-back视老化改造_文献依据.md；N-back/N-back/
- 当前实现：web-battery/paradigms/nback/；web-battery/paradigms/nback/lists/；web-battery/stimuli/nback/
- 证据：4月6日 反馈/04_Nback.md；4月18日 修改/时间对比与原文核实.md；Suzuki 2018 PDF；UX图片/标准_Nback设计决策.md

请判断：
- B1/B2/B3 当前流程是否符合图片记忆任务目标；
- B4 现在是门控保留还是应该彻底移除；
- 4000ms 反应窗口是否合理；
- B3 cue 当前时长和文献依据文档不一致，应以哪个为准；
- 图片数量、图片相似度、任务难度是否需要重新审核。

CSV/数据输出也要检查：
- 是否记录 block、phase、trial、图片编号、目标/非目标或相同/不同条件；
- 是否记录 response、accuracy、RT、deadline、rt_over_2s、rt_over_3s；
- B3 是否能记录 cue/probe 相关信息；
- B4 如果被跳过，是否有明确记录；
- 是否足够支持按 block 分析正确率、反应时和错误类型。

二、连线测试 / TMT
请重点看：
- 原始文档：开发文档/TMT范式开发文档.md；TMT/初版TMT/
- 当前实现：web-battery/paradigms/tmt/；web-battery/paradigms/tmt/layouts/；web-battery/stimuli/tmt-fruits/
- 证据：4月6日 反馈/03_TMT.md；UX图片/脚本/脚本_TMT.md；按钮修正/适老化触控交互文献调研.md

请判断：
- 当前顺序 A0、B2、B1、A1、B3、B4 是否合理；
- 正式任务取消 40 秒硬上限是否可以接受；
- 触屏操作、错误处理、松手继续、卡住提示、跳过按钮是否影响完成时间指标；
- A/B 版本流程和 B4 固定 layout 是否会影响平衡。

CSV/数据输出也要检查：
- 是否记录 block、layout、节点顺序、开始/结束时间、完成时间；
- 是否记录错误次数、错误类型、stall、skip、加载失败等特殊事件；
- 是否保存轨迹或 segment 信息，足够回放被试操作过程；
- 是否能区分正常完成、跳过、超时或异常终止。

输出请用表格，重点写：
当前设置、与原设计差异、是否合理、证据位置、CSV 输出是否足够、需要修改或确认的问题。
```

## 总控汇总提示

戴敬力汇总三位同学结果时，建议统一看这几类结论：

| 类别 | 判断 |
|---|---|
| 可接受 | 有原始设计、文献或试测反馈支撑，不影响主要指标 |
| 需要补证据 | 改动可能合理，但缺少明确文献或材料来源 |
| 需要改代码 | 当前实现和范式逻辑冲突，或 CSV 输出不足以分析 |
| 需要人工决定 | 文献没有唯一答案，需要负责人按研究目标取舍 |

优先级建议：

- 高：影响任务效度、正式数据、主要指标或 CSV 输出；
- 中：影响老人理解、练习通过率、材料难度或后续分析便利性；
- 低：文案、目录说明、非核心界面细节。
