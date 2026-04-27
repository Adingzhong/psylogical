# CSV/JSON 输出结构审核索引

## 用途

这份文档只帮助负责人快速定位“当前版本会输出什么数据”。它不是数据字典的最终版，也不包含真实被试数据。

审核时请优先确认三件事：

1. 字段是否足够支持后续统计分析；
2. 练习、正式、block、trial、特殊事件是否能区分；
3. 超时、漏按、误按、跳过、撤回、清空、录音失败等异常是否有记录。

## 按范式查看

| 范式 | 输出结构位置 | 主要输出 | 重点字段或文件 | 需要确认 |
|---|---|---|---|---|
| 空间导航 | `web-battery/paradigms/visuospatial/visuospatial.js` | CSV | `phase`, `trialIndex`, `pathId`, `turnCount`, `movementDurationMs`, `clickRTms`, `distanceErrorPx`, `distanceErrorM`, `angleErrorDeg`, `tap_count`, `input_type` | guided / practice / formal 是否足够区分；guided 数据是否分析时排除 |
| RMET | `web-battery/paradigms/rmet/rmet.js` | trial CSV | `is_practice`, `phase_name`, `stimulation`, `option1-3`, `answer`, `response`, `accuracy`, `rt_ms` | 是否足够做题目难度、正确率和反应时分析 |
| Flanker | `web-battery/paradigms/flanker/flanker.js` | trial CSV；attention rating CSV | `trial_type`, `is_popout`, `popout_type`, `target_dir`, `flanker_dir`, `phase_name`, `accuracy`, `rt_ms`, `timeout`, `is_anticipatory`, `rt_over_2s`, `rt_over_3s`; 评分表含 `focus_rating` | 4000ms 窗口下是否用慢反应标记筛选；评分 CSV 是否进入正式分析 |
| SART | `web-battery/paradigms/sart/sart.js` | trial CSV；summary JSON | `digit`, `trial_type`, `response_made`, `rt_ms`, `accuracy`, `error_type`, `phase`, `tap_count`, `input_type`; summary 含 `commission_errors`, `omission_errors`, `go_rt_mean` | `commission` / `omission` 定义是否符合原设计；触控字段是否纳入质控 |
| VSTMB | `web-battery/paradigms/vstmb/vstmb.js` | trial CSV；summary JSON | `is_practice`, `condition`, `trial_type`, `response_key`, `reaction_time`, `accuracy`, `sdt_classification`, `timeout`, `study_*`, `probe_*`, `same_response_mapping` | 字段是否足够计算 SDT 指标；Binding 条件材料是否能还原 |
| 图片记忆 / N-back | `web-battery/paradigms/nback/nback.js`; `web-battery/paradigms/nback/lists/*.csv` | trial CSV；summary JSON；block 列表 CSV | `block`, `trial_index`, `phase`, `condition`, `image`, `correct_resp`, `response`, `rt_ms`, `accuracy`, `timeout`, `rt_over_2s`, `rt_over_3s`; 列表含 `stim_dur`, `resp_deadline`, `isi` | B3 cue/probe 信息是否足够；B4 门控状态是否需要额外记录 |
| TMT | `web-battery/paradigms/tmt/tmt.js`; `web-battery/paradigms/tmt/layouts/` | segments CSV；raw path CSV；summary CSV；event marker CSV | summary: `finished`, `completion_time_s`, `total_errors`, `nodes_completed`, `hard_limit_s`; segments: `from_k`, `to_k`, `duration_ms`, `path_length_px`, `is_error`, `error_type`; raw path: `ts_ms`, `x_px`, `y_px`, `is_pen_down` | 取消 40 秒硬上限后，完成时间和跳过/卡住事件是否够解释 |
| 画钟 | `web-battery/paradigms/clock/clock.js` | trajectory CSV；raw CSV；stroke summary CSV；undo events CSV；screenshot JSON；最终图 WebP | `stroke_count`, `undo_count`, `total_drawing_ms`, `trajectory`, `stroke_summary`, `undo_events`, `image_base64` | 截图和轨迹都属于被试数据，不能公开；撤回/清空是否满足评分需要 |
| 语音 | `web-battery/paradigms/speech/speech.js` | item CSV；每题音频文件 | `task_type`, `item_id`, `item_name`, `duration_ms`, `mic_available`, `recorded`, `audio_filename`, `timestamp_iso` | 当前是每题自动录音；是否要改为主持人手动开始/停止 |

## 服务端保存结构

服务端保存入口在 `web-battery/server/main.py`。协作版只上传服务端代码，不上传 `web-battery/server/data/`。真实 CSV、JSON、录音、轨迹、截图都可能包含被试数据，不应放到公开仓库。

## 审核建议

每位负责人审核自己范式时，请在结论里额外写一列：

| 范式 | 输出是否足够 | 缺什么字段 | 是否影响分析 | 建议 |
|---|---|---|---|---|

如果某个字段“代码里能算但 CSV 没有保存”，应标为高优先级，因为后续真实采集后再补字段会影响可比性。
