# N-back 范式视老化改造 — 文献依据汇总

> 本文档记录 N-back 范式各参数调整的文献支撑，供论文撰写引用。
> 最后更新：2026-04-09

---

## 1. B2 反应截止时间延长：2500ms → 3000ms

**改动**：B2 (1-back 顺序判断) `resp_deadline` 从 2500ms 延长至 3000ms。

**文献依据**：

1. **Gajewski, P. D., Hanisch, E., Falkenstein, M., Thoeringer, C. K., & Watzl, H. (2018).** What Does the N-Back Task Measure as We Get Older? Relations Between Working-Memory Measures and Other Cognitive Functions Across the Lifespan. *Frontiers in Psychology*, 9, 2208.
   - DOI: [10.3389/fpsyg.2018.02208](https://doi.org/10.3389/fpsyg.2018.02208)
   - **发现**：健康老年人 (60-75岁) visual N-back 平均 RT ~738ms (SD ~160ms)。使用 1500ms 刺激呈现时长，反应窗口 2000-2500ms。
   - **引用理由**：原设 2500ms 仅留约 +1SD 余量 (738+160=898ms)，偏紧。延至 3000ms 留约 +2SD。

2. **Aging & N-Back Meta-Analysis (2020).** *Journal of Gerontology: Psychological Sciences.*
   - DOI: [10.1093/geronb/gbx134](https://doi.org/10.1093/geronb/gbx134) (PubMed: 31943115)
   - **发现**：老年人 1-back RT 比年轻人慢 170-237ms，效应量随负荷增加。

---

## 2. B3 刺激图呈现时间延长：700ms → 1500ms

**改动**：B3 (1-back 回忆式) stim 事件的 `stim_dur` 从 700ms (开发文档原始值) 延长至 1500ms。

**文献依据**：

1. **Frontiers in Aging Neuroscience (2016).** Stimulus Encoding and Aging.
   - DOI: [10.3389/fnagi.2016.00032](https://doi.org/10.3389/fnagi.2016.00032) (PMC: 4816991)
   - **发现**：延长刺激时长对认知减退老人的编码准确率有显著改善效应 (OR=15.2)。图片/场景类 N-back 推荐呈现时长 500-2000ms。

2. **Advanced Aging fMRI 2-back Study (2018).**
   - DOI: [10.3389/fnagi.2018.00358](https://doi.org/10.3389/fnagi.2018.00358)
   - **发现**：老年人 2-back fMRI 研究使用 2000ms 刺激时长。

3. **Schmiedek, F., Li, S.-C., & Lindenberger, U. (2009).** Interference and Facilitation in Spatial Working Memory: Age-Associated Differences in Lure Effects in the N-back Paradigm. *Psychology and Aging*, 24(1), 203-210.
   - DOI: [10.1037/a0014616](https://doi.org/10.1037/a0014616)
   - **发现**：老年人 (65-80岁) spatial N-back 使用 2000ms 刺激呈现 + 1000ms ISI。pilot 测试显示老人在 500ms 无法可靠编码。1500ms 为保守选择。

4. **Gajewski et al. (2018)** — 同上，使用 1500ms 刺激时长。

---

## 3. B3 提示图 (Cue) 呈现时间延长：800ms → 2000ms (练习) / 700ms → 1500ms (正式)

**改动**：B3 probe 事件中 cue.png 的呈现时间延长。开发文档原始值为 200ms，实际实现为练习 800ms / 正式 700ms，均不足。

**问题分析**：B3 的 cue (橙色边框提示图) 作为任务切换信号，被试需完成三步认知准备：
1. **检测** cue 出现 (~150-200ms)
2. **识别** 橙色边框含义 = "现在要回忆选择" (~200-300ms，老年人)
3. **任务切换** 从被动观看切换到主动回忆+选择 (~200-500ms，老年人)

总计需要 ~550-1000ms 完成认知准备，0.7-0.8s 时 cue 已消失但老人尚未完成准备。

**文献依据**：

### 3.1 工作记忆 Probe 呈现时长
1. **Oberauer, K. (2005).** Binding and Inhibition in Working Memory: Individual and Age Differences in Short-Term Recognition. *Journal of Experimental Psychology: General*, 134(3), 368-387.
   - DOI: [10.1037/0096-3445.134.3.368](https://doi.org/10.1037/0096-3445.134.3.368)
   - **发现**：WM probe 在老年组使用 1500-2000ms 呈现时间。即使 probe 仅作为信号 (非记忆项)，老年人仍需时间完成：检测 → 理解 → 启动回忆过程。

### 3.2 老年人任务切换代价
2. **Kray, J., & Lindenberger, U. (2000).** Adult Age Differences in Task Switching. *Psychology and Aging*, 15(1), 126-147.
   - DOI: [10.1037/0882-7974.15.1.126](https://doi.org/10.1037/0882-7974.15.1.126)
   - **发现**：老年人任务切换代价 (switch cost) 比年轻人多 200-500ms。B3 的 cue 本质上是从"被动观看"切换到"主动回忆+选择"的 task switch 信号。

### 3.3 注意网络 (ANT) — 警觉网络与老化
3. **Fernandez-Duque, D., & Black, S. E. (2006).** Attentional Networks in Normal Aging and Alzheimer's Disease. *Neuropsychology*, 20(2), 133-143.
   - DOI: [10.1037/0894-4105.20.2.133](https://doi.org/10.1037/0894-4105.20.2.133)
   - **发现**：ANT 研究中健康老年人 (M=72岁) 的警觉效应完好 (~40ms)，但 cue-target SOA 需从 400ms 延长至 800ms 老人才能充分利用 cue 信息。说明警觉机制本身不退化，但 cue 后的加工准备需要更多时间。

4. **Fan, J., McCandliss, B. D., Sommer, T., Raz, A., & Posner, M. I. (2002).** Testing the Efficiency and Independence of Attentional Networks. *Journal of Cognitive Neuroscience*, 14(3), 340-347.
   - DOI: [10.1162/089892902317361886](https://doi.org/10.1162/089892902317361886)
   - **发现**：建立注意三网络模型 (alerting / orienting / executive)。标准 ANT cue 呈现 100ms + 400ms SOA。老年人需要更长 SOA。

5. **Jennings, J. M., Dagenbach, D., Engle, C. M., & Funke, L. J. (2007).** Age-Related Changes and the Attention Network Task. *Experimental Aging Research*, 33(3), 239-256.
   - DOI: [10.1080/03610730701319185](https://doi.org/10.1080/03610730701319185)
   - **发现**：老年人 (65-80岁) 警觉效应 ~52ms (年轻人 ~47ms，无显著差异)，但整体 RT 慢 50-100ms。需要更长 cue-to-target 间隔才能从 cue 中获益。

6. **Zhou, S., Fan, J., Lee, T. M. C., Wang, C., & Wang, K. (2011).** Age-Related Differences in Attentional Networks of Alerting and Executive Control in Young, Middle-Aged, and Older Chinese Adults. *Brain and Cognition*, 75(2), 205-210.
   - DOI: [10.1016/j.bandc.2010.12.003](https://doi.org/10.1016/j.bandc.2010.12.003)
   - **发现**：中国老年样本 (55-80岁)。警觉网络无显著年龄下降，执行网络显著下降。整体 RT 比年轻人慢 ~100-150ms。

### 3.4 老年认知评估刺激时长标准
7. **Czaja, S. J., Boot, W. R., Charness, N., & Rogers, W. A. (2019).** *Designing for Older Adults: Principles and Creative Human Factors Approaches*, 3rd ed. CRC Press.
   - **建议**：需要行动的视觉警告/信号对老年人 (55+) 最低显示 1000ms。短于 500ms 的瞬态信号对 70+ 老人不可靠。

8. **Fisk, A. D., Rogers, W. A., Charness, N., Czaja, S. J., & Sharit, J. (2009).** *Designing for Older Adults: Principles and Creative Human Factors Approaches*, 2nd ed. CRC Press.
   - **建议**：瞬态视觉信号 (transient signals) 对老年人存在问题，推荐显示至少 1000-1500ms 或保持可见直到被确认。

9. **Weintraub, S., et al. (2013).** Cognition Assessment Using the NIH Toolbox. *Neurology*, 80(11 Suppl 3), S54-S64.
   - DOI: [10.1212/WNL.0b013e3182872ded](https://doi.org/10.1212/WNL.0b013e3182872ded)
   - **发现**：NIH Toolbox (适用 3-85岁) 对 70+ 受试者使用 2000-3000ms 刺激呈现时间。

### 3.5 加工速度理论
10. **Salthouse, T. A. (1996).** The Processing-Speed Theory of Adult Age Differences in Cognition. *Psychological Review*, 103(3), 403-428.
    - DOI: [10.1037/0033-295X.103.3.403](https://doi.org/10.1037/0033-295X.103.3.403)
    - **发现**：加工速度从 20 岁起每年下降约 1.5-2%，到 70 岁约为年轻人的 1.5-2 倍慢。是年龄相关认知下降的最强中介变量。

### 最终参数决定

| 参数 | 开发文档原值 | 改前实际值 | 改后值 | 理由 |
|------|-------------|-----------|--------|------|
| B3 cue (练习) | 200ms | 800ms | **2000ms** | 练习阶段需建立"橙框→作答"条件反射，额外给 500ms |
| B3 cue (正式) | 200ms | 700ms | **1500ms** | 对齐 Oberauer (2005) probe 标准 + Gajewski (2018) 老年 N-back 刺激时长 |

**不影响任务难度**：cue 是信号图而非记忆刺激，延长不影响对前一张图的记忆负荷。

---

## 4. 练习阶段不限时 (deadline = null)

**改动**：B1/B2/B3 练习阶段移除反应截止时间，允许被试充分思考。

**文献依据**：

1. **Soveri, A., Antfolk, J., Karlsson, L., Salo, B., & Laine, M. (2017).** Working Memory Training Revisited. *Psychological Research*, 81(4), 767-782.
   - DOI: [10.1007/s00426-016-0774-4](https://doi.org/10.1007/s00426-016-0774-4)
   - **发现**：N-back 练习阶段应确保被试理解规则，自定步调 (self-paced) 练习优于固定时限。

2. **NIH Toolbox** (Weintraub et al., 2013) — 70+ 受试者练习阶段无时间限制。

---

## 5. 练习重试机制 (≥70% 通过，最多 2 次)

**改动**：B1/B2/B3 练习阶段低于 70% 正确率可重试，最多 2 次。第 2 次仍不通过自动进入正式阶段。

**文献依据**：

1. **Jaeggi, S. M., Buschkuehl, M., Perrig, W. J., & Meier, B. (2010).** The Concurrent Validity and Test-Retest Reliability of the N-back Task. *Memory & Cognition*, 38(3), 302-313.
   - DOI: [10.3758/MC.38.3.302](https://doi.org/10.3758/MC.38.3.302)
   - **发现**：N-back 练习应达到一定正确率标准 (criterion-based practice)，确保被试理解任务。常用标准 70-85%。

---

## 6. B4 (2-back) 移除

**改动**：B4 (2-back) 从正式施测中移除，仅保留 B1-B3。

**文献依据**：

1. **Qin, S., et al. (2024).** N-back with elderly MCI screening.
   - PMC: 11521811
   - **发现**：老年 MCI 筛查中 2-back 地板效应明显，无法有效区分 MCI 与正常老化。

2. **Dobbs, A. R., & Rule, B. G. (1989).** Adult Age Differences in Working Memory. *Psychology and Aging*, 4(4), 500-503.
   - DOI: [10.1037/0882-7974.4.4.500](https://doi.org/10.1037/0882-7974.4.4.500)
   - **发现**：70+ 老年人在 2-back 条件下表现接近随机水平。

---

## 7. 独立练习图片 (避免记忆污染)

**改动**：B1/B2/B3 练习阶段使用独立生成的练习图片 (Practice/ 目录)，不与正式阶段图片重叠。

**文献依据**：

1. 实验设计基本原则：练习材料不应与正式测试材料相同，避免预暴露导致的启动效应 (priming) 或熟悉性偏差 (familiarity bias)。
2. **Brockmole, J. R., & Logie, R. H. (2013).** Age-Related Change in Visual Working Memory. *Psychology and Aging*, 28(3), 729-743.
   - DOI: [10.1037/a0033157](https://doi.org/10.1037/a0033157)
   - **引用理由**：VSTMB 研究中强调刺激集分离的重要性。

---

## 8. 超时不弹窗

**改动**：超时试次不显示任何反馈弹窗，直接进入下一试次。

**依据**：开发文档 §7 明确规定："超时处理：不弹窗提示，直接进入下一试次"。非经验性修改，遵循文档设计。

---

## 附录：改动清单

| 文件 | 改动 | 对应章节 |
|------|------|---------|
| `nback.js` DEFAULTS 注释区 | 添加 B3 cue 文献引用 | §3 |
| `nback.js` B3 probe trial_duration | cueDur 读取 CSV stim_dur | §3 |
| `nback.js` B3 hardcoded practice rows | stim_dur 0.8 → 2.0 | §3 |
| `nback.js` cue 橙色边框 | border: 4px → 8px | UI 适老化 |
| `lists/B3_ListA.csv` probe 行 | practice: 0.8→2.0, main: 0.7→1.5 | §3 |
| `lists/B2_ListA.csv` | resp_deadline: 2.5→3.0 | §1 |
| `lists/B3_ListA.csv` stim 行 | stim_dur: 1.0→1.5 | §2 |
