# 认知测评平台 Codex 交接说明

## 给后续 Codex 的任务提示词

后续协作者可以把下面这段作为开场 prompt 使用：

```text
你现在协助我审核“老年范式综合2”仓库中的认知测评平台。

先阅读：
1. docs/handoff/认知测评平台_协作者审核说明.md
2. docs/handoff/认知测评平台_Codex交接说明.md
3. 如需深挖，再读 docs/handoff/认知测评平台_修改记录与交接说明.md

你的任务不是重写功能，也不是直接提交代码。请围绕我指定的范式，做三路对照：
- 原始开发文档/旧版程序；
- 当前 web-battery 代码和代码注释；
- 试测反馈、Markdown、文献证据、git commit 线索。

请用简洁中文输出：
1. 当前实现做了什么；
2. 相比原始设计改了什么；
3. 证据文件在哪里；
4. 哪些点需要原负责人确认；
5. 如果要改代码，应改哪些文件，但不要直接 commit/push。

不要处理 zjuaipsy.cn。不要删除文件。不要泄露或上传被试数据、私钥、日志和本地数据库。
```

## 这份机器文档怎么用

这份文档给 Codex / ChatGPT / 其他代码助手使用。它比人读版更偏操作：

- 帮机器快速定位目录；
- 告诉机器每个范式该看哪些文件；
- 给出可复用的搜索关键词和对照方式；
- 约束机器不要把交接任务误做成重构、提交或推送。

人读版用于负责人判断“改动是否合理”。机器读版用于辅助找文件、归纳证据和形成审核清单。

## 工作原则

- 每次只聚焦一个范式或一个负责人，不要一次性展开全仓库。
- 优先读当前代码，其次读原始文档和证据，commit 只作辅助线索。
- 输出给人的内容要短，重点是“改了什么、证据在哪、要确认什么”。
- 如果要修改代码，必须先得到用户明确要求；本交接阶段默认只读、只整理。
- 不要把 `CLAUDE.md` 当作最终事实，它只能作为可能过期的参考。

## 仓库架构速览

| 路径 | 说明 |
|---|---|
| `web-battery/` | 当前 Web 认知测评平台 |
| `web-battery/index.html` | 当前平台主控台/入口 |
| `web-battery/paradigms/` | 当前范式实现，每个子目录通常有 `.html` 和 `.js` |
| `web-battery/stimuli/` | 当前 Web 平台用到的刺激图片、材料 |
| `web-battery/audio/` | 当前 Web 平台用到的指导语音频 |
| `web-battery/lib/` | 公共 JS 能力，如触屏、保存、摄像、语音指导、结束页 |
| `web-battery/server/` | FastAPI 保存和下载服务 |
| `开发文档/` | 原始开发文档、参数说明、部分文献依据 |
| `4月6日 反馈/` | 试测反馈和改动原因 |
| `4月18日 修改/` | RT/呈现时间/文献原文核实材料 |
| `UX图片/` | 指导语、语音脚本、界面图片、适老化 UX 方案 |
| `按钮修正/` | 触控按钮、适老化交互相关依据 |
| 旧版范式目录 | `Flanker/`、`SART/`、`N-back/`、`TMT/`、`VSTMB/`、`空间导航/`、`社会认知/`、`画钟范式/`、`语音/` |

## 常用命令

只读扫描时优先使用：

```bash
rg -n "关键词" web-battery/paradigms 开发文档 "4月6日 反馈" "4月18日 修改" UX图片 按钮修正
rg --files | rg "flanker|sart|nback|vstmb|tmt|clock|speech|rmet|visuospatial|空间|画钟|语音"
git log --oneline --decorate --all -- web-battery/paradigms/flanker
git show --stat <commit>
```

不要在交接审核阶段运行：

```bash
git add
git commit
git push
git reset --hard
git checkout --
```

## 范式对照索引

| 范式 | 负责人 | 当前代码 | 原始/旧版资料 | 证据资料 | 搜索关键词 |
|---|---|---|---|---|---|
| 空间导航 | 刘晓烨 | `web-battery/paradigms/visuospatial/`; `web-battery/audio/visuospatial/` | `开发文档/视空间导航产品文档.md`; `空间导航/视空间范式/` | `4月6日 反馈/09_空间导航.md`; `UX图片/脚本/脚本_空间导航.md` | `空间导航`, `visuospatial`, `guided`, `GRID`, `practice` |
| RMET | 刘晓烨 | `web-battery/paradigms/rmet/`; `web-battery/stimuli/rmet/`; `web-battery/audio/rmet/` | `社会认知/RMET【以此为基准】/` | 旧版 RMET 目录；当前代码注释 | `RMET`, `rmet`, `eye`, `Baron-Cohen`, `options` |
| Flanker | 许一桦 | `web-battery/paradigms/flanker/`; `web-battery/stimuli/flanker/` | `开发文档/Flanker开发文档.md`; `Flanker/` | `4月6日 反馈/01_Flanker.md`; `4月18日 修改/时间对比与原文核实.md`; Krueger PDF | `Flanker`, `maxResponse`, `4000`, `rt_over`, `209px` |
| SART | 许一桦 | `web-battery/paradigms/sart/` | `开发文档/SART产品文档.md`; `SART/` | `4月6日 反馈/02_SART.md`; Robertson PDF | `SART`, `1250`, `No-Go`, `commission`, `omission` |
| VSTMB | 许一桦 | `web-battery/paradigms/vstmb/`; `web-battery/stimuli/vstmb/` | `开发文档/VSTMB范式编写手册.pdf`; `VSTMB/VSTMB/` | `4月6日 反馈/05_VSTMB.md`; Parra PDFs | `VSTMB`, `Binding`, `Object`, `Color`, `retention`, `5000` |
| 图片记忆 / N-back | 黄朝琮 | `web-battery/paradigms/nback/`; `web-battery/paradigms/nback/lists/`; `web-battery/stimuli/nback/` | `开发文档/N-back范式开发文档.md`; `开发文档/N-back视老化改造_文献依据.md`; `N-back/N-back/` | `4月6日 反馈/04_Nback.md`; Suzuki PDF; `UX图片/标准_Nback设计决策.md` | `N-back`, `B4`, `B3`, `cue`, `resp_deadline`, `4000` |
| TMT | 黄朝琮 | `web-battery/paradigms/tmt/`; `web-battery/paradigms/tmt/layouts/`; `web-battery/stimuli/tmt-fruits/` | `开发文档/TMT范式开发文档.md`; `TMT/初版TMT/` | `4月6日 反馈/03_TMT.md`; `UX图片/脚本/脚本_TMT.md`; `按钮修正/适老化触控交互文献调研.md` | `TMT`, `HARD_LIMIT`, `Infinity`, `stall`, `skip`, `layout` |
| 画钟 | 戴敬力 | `web-battery/paradigms/clock/` | `画钟范式/CDT_PsychoPy_概述.docx`; `画钟范式/clock.py` | `4月6日 反馈/10_画钟测验.md`; `UX图片/脚本/脚本_画钟.md` | `clock`, `drawing`, `undo`, `clear`, `trajectory`, `screenshot` |
| 语音 | 戴敬力 | `web-battery/paradigms/speech/`; `web-battery/stimuli/speech/`; `web-battery/audio/speech/` | `语音/260316语音(2).pptx` | `4月6日 反馈/11_语音.md`; `UX图片/标准_语音脚本规范.md`; `UX图片/脚本/脚本_语音范式.md` | `speech`, `recording`, `MediaRecorder`, `audio`, `60s`, `manual` |

## 已知关键差异

| 范式 | 当前最需要确认的差异 |
|---|---|
| 空间导航 | guided 阶段新增；练习轮数说法不一致；网格和点击反馈做了适老化 |
| RMET | 当前是 10 题短版，不是完整 36 题 RMET |
| Flanker | 反应窗口改到 4000ms；刺激大小放大；文件头有 2000ms 旧注释 |
| SART | 核心 timing 基本保留；按钮常驻和触控反馈做了适老化 |
| VSTMB | 练习通过率和次数调整；Binding 条件可能存在策略局限 |
| N-back | B4 代码仍保留门控；B3 cue 时长与文献依据文档不一致；响应窗改为 4000ms |
| TMT | 正式 40 秒硬上限取消；有 stall/skip 机制；B4 固定 layout 1 |
| 画钟 | Web 版含临摹条件；保存轨迹、撤销、截图等过程数据 |
| 语音 | 当前每题自动录音；没有主持人手动开始/停止；主持人声音可能混入 |

## 给 Codex 的简洁 TODO

当用户指定一个范式后，按下面顺序做：

1. 读人读版里该范式对应行。
2. 打开当前代码目录，确认当前实现。
3. 打开原始开发文档或旧版程序，确认原设计。
4. 打开反馈和证据文件，确认修改原因。
5. 必要时用 `git log --oneline -- <路径>` 找相关 commit。
6. 输出不超过 8 条要点：
   - 当前实现；
   - 与原设计差异；
   - 证据位置；
   - 需要负责人确认；
   - 数据质量风险。
7. 如果用户要求改代码，先列将要改的文件，再动手；不要自动 commit/push。

## 输出模板

```markdown
## 范式：<名称>

当前实现：
- ...

主要改动：
- ...

证据位置：
- ...

需要负责人确认：
- ...

风险：
- ...
```

## 需要谨慎处理的文件

不要公开或需要人工确认后再上传：

- `web-battery/server/data/`
- `web-battery/server/logs/`
- `web-battery-https-certs/lan.key`
- `4月19日 修改/hospital_query/data/queue.db`
- `伦理审查/`
- `社会认知/RMET【以此为基准】/result/*.csv`
- `.DS_Store`
- `__pycache__/`
- `web-battery/node_modules/`
- `web-battery/.pw-browsers/`
- `web-battery/test-results/`

## 详细底稿

如果一个范式需要继续深挖，读取：

`docs/handoff/认知测评平台_修改记录与交接说明.md`

这份底稿包含更多 commit、代码注释、参数和文献证据。它偏详细，不适合直接发给负责人作为第一阅读材料。
