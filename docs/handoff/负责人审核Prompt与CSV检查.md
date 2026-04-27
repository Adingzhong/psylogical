# 负责人审核 Prompt 与 CSV 检查清单

## 用法

这份文档用于把仓库交给原范式负责人后，快速启动审核。

每位负责人下面有两段：

1. **发给人的话**：直接发给负责人，说明他/她负责什么、要做什么判断。
2. **复制给 Codex 的 prompt**：负责人把这段复制给 Codex / ChatGPT，让机器去读 handoff、扫代码、整理证据和 CSV 输出结构。

负责人本人不需要先读完整机器交接文档。机器会按 prompt 去读。

## 通用审核目标

负责人最后只需要判断：

| 范式 | 当前实现是否符合原设计 | 主要差异 | 证据是否够 | CSV/JSON输出是否够分析 | 需要改什么 | 优先级 |
|---|---|---|---|---|---|---|

优先级建议：

- 高：影响任务效度、正式数据、主要指标或输出字段；
- 中：影响老人理解、练习通过率、材料难度或后续分析便利性；
- 低：文案、目录说明、非核心界面细节。

## 刘晓烨

### 发给人的话

```text
晓烨，这次想请你帮忙审核你原来负责的两个范式：空间导航、看眼读心/RMET。

我已经把当前 Web 代码、原始开发文档、旧版材料、修改依据、当前使用的图片和指导语都放到 GitHub 里了。你不需要自己从头翻全仓库，也不需要改代码。你可以把下面这段“复制给 Codex 的 prompt”直接交给 Codex，让它先帮你把当前实现、原始设计、修改证据和数据输出整理成表格。

你最后主要判断：这些修改从空间导航/RMET 的心理学范式逻辑看是否合理，哪些可以接受，哪些必须改，哪些需要补文献或材料来源说明。
```

### 复制给 Codex 的 prompt

```text
你现在协助刘晓烨审核“老年范式综合2 / psylogical”仓库中她负责的两个范式：空间导航、看眼读心/RMET。

工作边界：
- 不要改代码；
- 不要 git add / commit / push；
- 不要处理 zjuaipsy.cn；
- 不要读取或要求上传被试数据、日志、私钥、数据库；
- 你的任务是替负责人整理证据和问题，方便她做科研判断。

请先读取这些 handoff 文件，理解仓库结构和本轮审核目标：
- docs/handoff/认知测评平台_协作者审核说明.md
- docs/handoff/审核材料充分性检查.md
- docs/handoff/CSV输出结构审核索引.md
- docs/handoff/认知测评平台_修改记录与交接说明.md

然后只围绕以下路径做三路对照：

空间导航：
- 当前实现：web-battery/paradigms/visuospatial/；web-battery/audio/visuospatial/
- 当前指导语/图片：web-battery/paradigms/visuospatial/img/
- 原始文档：开发文档/视空间导航产品文档.md；开发文档/视空间导航产品文档-刘晓烨.pdf
- 旧版材料：空间导航/视空间范式/
- 修改依据：4月6日 反馈/09_空间导航.md；UX图片/脚本/脚本_空间导航.md

RMET：
- 当前实现：web-battery/paradigms/rmet/；web-battery/stimuli/rmet/；web-battery/audio/rmet/
- 当前指导语/图片：web-battery/paradigms/rmet/img/
- 原始材料：社会认知/RMET【以此为基准】/RMET.py；社会认知/RMET【以此为基准】/marterial/options_new.xlsx；社会认知/RMET【以此为基准】/marterial/image/
- 修改依据：docs/handoff/认知测评平台_修改记录与交接说明.md 中 RMET 相关内容

请重点整理：
1. 当前 Web 版到底怎么实现；
2. 和原始设计/旧版材料相比改了什么；
3. 证据或依据在哪个文件；
4. CSV/JSON 输出是否足够后续分析；
5. 哪些问题必须由刘晓烨确认；
6. 哪些点可能影响数据质量或实验效度。

输出要求：
- 用中文；
- 不要长篇解释；
- 每个范式一张表；
- 文件路径写到文件或目录即可，不需要精确到行号；
- 如果没有找到证据，直接写“未找到明确证据”；
- 最后给一个“需要刘晓烨确认的问题清单”，按高/中/低优先级排列。
```

## 许一桦

### 发给人的话

```text
一桦，这次想请你帮忙审核你原来负责的三个范式：Flanker、SART、VSTMB。

我已经把当前 Web 代码、原始开发文档、旧版程序、关键文献、当前使用的刺激材料和指导语都放到 GitHub 里了。你不需要自己从头翻全仓库，也不需要改代码。你可以把下面这段“复制给 Codex 的 prompt”直接交给 Codex，让它先把当前参数、原始设计、修改依据和 CSV/JSON 输出整理出来。

你最后主要判断：当前 timing、trial 数、练习/正式流程、反应窗口、Go/No-go 错误定义、VSTMB 条件和输出字段是否仍符合你原来的范式设计和文献逻辑。
```

### 复制给 Codex 的 prompt

```text
你现在协助许一桦审核“老年范式综合2 / psylogical”仓库中她负责的三个范式：Flanker、SART、VSTMB。

工作边界：
- 不要改代码；
- 不要 git add / commit / push；
- 不要处理 zjuaipsy.cn；
- 不要读取或要求上传被试数据、日志、私钥、数据库；
- 你的任务是替负责人整理证据和问题，方便她做科研判断。

请先读取这些 handoff 文件，理解仓库结构和本轮审核目标：
- docs/handoff/认知测评平台_协作者审核说明.md
- docs/handoff/审核材料充分性检查.md
- docs/handoff/CSV输出结构审核索引.md
- docs/handoff/认知测评平台_修改记录与交接说明.md

然后只围绕以下路径做三路对照：

Flanker：
- 当前实现：web-battery/paradigms/flanker/
- 当前刺激/指导语：web-battery/stimuli/flanker/；web-battery/paradigms/flanker/img/；web-battery/audio/flanker/
- 原始文档：开发文档/Flanker开发文档.md；开发文档/Flanker开发文档-许一桦(2).pdf
- 旧版程序：Flanker/
- 修改依据：4月6日 反馈/01_Flanker.md；4月18日 修改/时间对比与原文核实.md；4月18日 修改/文献原文/Krueger_2009_Neurology_Flanker_FTD.pdf

SART：
- 当前实现：web-battery/paradigms/sart/
- 当前指导语：web-battery/paradigms/sart/img/；web-battery/audio/sart/
- 原始文档：开发文档/SART产品文档.md；开发文档/SART产品文档-许一桦(1).pdf
- 旧版程序：SART/
- 修改依据：4月6日 反馈/02_SART.md；4月18日 修改/文献原文/Robertson_1997_Neuropsychologia_SART.pdf

VSTMB：
- 当前实现：web-battery/paradigms/vstmb/
- 当前刺激/指导语：web-battery/stimuli/vstmb/；web-battery/paradigms/vstmb/img/；web-battery/audio/vstmb/
- 原始文档：开发文档/VSTMB范式编写手册.pdf
- 旧版程序/配置：VSTMB/VSTMB/README.md；VSTMB/VSTMB/config.json；VSTMB/VSTMB/*.py
- 修改依据：4月6日 反馈/05_VSTMB.md；4月18日 修改/时间对比与原文核实.md；4月18日 修改/文献原文/Parra_2020_Frontiers_Neurology_VSTMB_clinical_review.pdf；4月18日 修改/文献原文/Parra_2025_Aging_Neuropsychol_VSTMB_oculomotor.pdf

请重点整理：
1. 当前 Web 版的呈现时间、ITI/ISI、trial 数、练习 trial、正式 trial、反应窗口；
2. Flanker 的正确率、反应时、timeout、慢反应标记；
3. SART 的数字呈现时间、Go/No-go 比例、漏按、误按、error_type；
4. VSTMB 的 Object / Color / Binding 条件、刺激数量、保持间隔、探测方式、SDT 相关输出；
5. 和原始设计相比的差异；
6. 每个差异对应的证据文件；
7. CSV/JSON 输出是否足够后续分析；
8. 哪些点必须由许一桦确认。

输出要求：
- 用中文；
- 不要长篇解释；
- 每个范式一张表；
- 文件路径写到文件或目录即可，不需要精确到行号；
- 如果没有找到证据，直接写“未找到明确证据”；
- 最后给一个“需要许一桦确认的问题清单”，按高/中/低优先级排列。
```

## 黄朝琮

### 发给人的话

```text
朝琮，这次想请你帮忙审核你原来负责的两个范式：图片记忆/N-back、连线测试/TMT。

我已经把当前 Web 代码、原始开发文档、旧版程序、关键文献、当前使用的图片材料、layout 和指导语都放到 GitHub 里了。你不需要自己从头翻全仓库，也不需要改代码。你可以把下面这段“复制给 Codex 的 prompt”直接交给 Codex，让它先把当前实现、原始设计、修改依据和 CSV/轨迹输出整理出来。

你最后主要判断：N-back 的 B1/B2/B3/B4 流程和图片难度是否合理，TMT 的触屏流程、layout、错误处理、完成时间和轨迹记录是否仍符合原始设计与研究目标。
```

### 复制给 Codex 的 prompt

```text
你现在协助黄朝琮审核“老年范式综合2 / psylogical”仓库中他负责的两个范式：图片记忆/N-back、连线测试/TMT。

工作边界：
- 不要改代码；
- 不要 git add / commit / push；
- 不要处理 zjuaipsy.cn；
- 不要读取或要求上传被试数据、日志、私钥、数据库；
- 你的任务是替负责人整理证据和问题，方便他做科研判断。

请先读取这些 handoff 文件，理解仓库结构和本轮审核目标：
- docs/handoff/认知测评平台_协作者审核说明.md
- docs/handoff/审核材料充分性检查.md
- docs/handoff/CSV输出结构审核索引.md
- docs/handoff/认知测评平台_修改记录与交接说明.md

然后只围绕以下路径做三路对照：

图片记忆 / N-back：
- 当前实现：web-battery/paradigms/nback/
- 当前 block 列表：web-battery/paradigms/nback/lists/
- 当前刺激/指导语：web-battery/stimuli/nback/；web-battery/stimuli/nback-instructions/；web-battery/paradigms/nback/img/；web-battery/audio/nback/
- 原始文档：开发文档/N-back范式开发文档.md；开发文档/N-back范式开发文档.pdf；开发文档/N-back视老化改造_文献依据.md
- 旧版程序/列表：N-back/N-back/
- 修改依据：4月6日 反馈/04_Nback.md；4月18日 修改/时间对比与原文核实.md；4月18日 修改/文献原文/Suzuki_2018_Frontiers_Aging_Neurosci_N-back.pdf；UX图片/标准_Nback设计决策.md
- 材料预览：docs/handoff/material_previews/nback.jpg；docs/handoff/material_previews/material_preview_manifest.csv

连线测试 / TMT：
- 当前实现：web-battery/paradigms/tmt/
- 当前 layout：web-battery/paradigms/tmt/layouts/
- 当前刺激/指导语：web-battery/stimuli/tmt-fruits/；web-battery/paradigms/tmt/img/；web-battery/audio/tmt/
- 原始文档：开发文档/TMT范式开发文档.md；开发文档/TMT范式开发文档(1).pdf
- 旧版程序/生成脚本：TMT/初版TMT/
- 修改依据：4月6日 反馈/03_TMT.md；UX图片/脚本/脚本_TMT.md；按钮修正/适老化触控交互文献调研.md

请重点整理：
1. N-back 的 B1/B2/B3/B4 当前流程、trial 数、反应窗口、cue/probe、图片材料和 block 列表；
2. N-back 当前 B4 是门控保留还是正式启用；
3. TMT 当前 A0/B2/B1/A1/B3/B4 顺序、layout、触屏操作、错误处理、skip/stall、是否取消 40 秒硬上限；
4. 和原始设计相比的差异；
5. 每个差异对应的证据文件；
6. CSV/JSON/轨迹输出是否足够后续分析；
7. 哪些点必须由黄朝琮确认。

输出要求：
- 用中文；
- 不要长篇解释；
- 每个范式一张表；
- 文件路径写到文件或目录即可，不需要精确到行号；
- 如果没有找到证据，直接写“未找到明确证据”；
- 最后给一个“需要黄朝琮确认的问题清单”，按高/中/低优先级排列。
```

## 戴敬力自查

### 发给人的话

```text
敬力，这部分主要是你自己后续确认：画钟测试和语音测评。

仓库里已经放了当前 Web 代码、旧版画钟程序、语音原始 PPT、当前使用的语音图片和指导语。你可以把下面这段 prompt 给 Codex，让它先整理当前实现、输出文件和风险点。你最后主要判断：画钟轨迹/截图是否够评分，语音是否必须改成主持人手动开始/停止录音。
```

### 复制给 Codex 的 prompt

```text
你现在协助戴敬力审核“老年范式综合2 / psylogical”仓库中的画钟测试和语音测评。

工作边界：
- 不要改代码；
- 不要 git add / commit / push；
- 不要处理 zjuaipsy.cn；
- 不要读取或要求上传被试数据、日志、私钥、数据库；
- 你的任务是整理当前实现、输出文件和风险点。

请先读取：
- docs/handoff/认知测评平台_协作者审核说明.md
- docs/handoff/审核材料充分性检查.md
- docs/handoff/CSV输出结构审核索引.md
- docs/handoff/认知测评平台_修改记录与交接说明.md

然后只围绕以下路径做对照：

画钟：
- 当前实现：web-battery/paradigms/clock/
- 当前指导语/临摹图：web-battery/paradigms/clock/img/；web-battery/paradigms/clock/*.webp；web-battery/audio/clock/
- 旧版材料：画钟范式/CDT_PsychoPy_概述.docx；画钟范式/clock.py
- 修改依据：4月6日 反馈/10_画钟测验.md；UX图片/脚本/脚本_画钟.md

语音：
- 当前实现：web-battery/paradigms/speech/
- 当前材料/指导语：web-battery/stimuli/speech/；web-battery/audio/speech/
- 原始材料：语音/260316语音(2).pptx
- 修改依据：4月6日 反馈/11_语音.md；UX图片/标准_语音脚本规范.md；UX图片/脚本/脚本_语音范式.md

请重点整理：
1. 画钟当前是否记录撤回、清空、轨迹、原始轨迹、最终图、时间戳；
2. 画钟输出文件是否足够后续评分；
3. 语音当前是否每题单独录音；
4. 语音是否存在主持人声音混入风险；
5. 后续如果改为主持人手动开始/停止录音，需要改哪些文件；
6. 哪些输出属于被试数据，不能上传公开仓库。

输出要求：
- 用中文；
- 每个范式一张表；
- 文件路径写到文件或目录即可，不需要精确到行号；
- 最后给一个高/中/低优先级问题清单。
```
