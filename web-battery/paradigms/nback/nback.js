/**
 * N-back Working Memory Battery — jsPsych 8 Web Implementation
 *
 * 4 blocks:
 *   B1: 0-back (compare to target image) — 3 buttons: same/similar/different
 *   B2: 1-back (compare to previous image) — 3 buttons: same/similar/different
 *   B3: 1-back probe recall (select previous from 3 options)
 *   B4: 2-back (press if same as 2 items ago) — single GO button
 *
 * Adaptive gating: B4 runs only if B3 time <= 270s AND B2+B3 accuracy >= 80%
 * Trial lists are CSV-driven from lists/ directory.
 */

(function () {
  'use strict';

  // ==================== Config ====================
  const STIMULI_BASE = '../../stimuli/nback';
  const INSTR_BASE   = '../../stimuli/nback-instructions';
  const LISTS_BASE   = 'lists';

  const urlParams = new URLSearchParams(window.location.search);
  const SUBJECT_ID = urlParams.get('sid') || 'TEST';
  const LIST_NAME  = urlParams.get('list') || 'ListA';

  // F4 (2026-04-19): Block-level resume 参数
  let START_BLOCK = 0;
  let SKIP_INSTRUCTIONS = false;
  if (window.ProgressAPI && window.ProgressAPI.getResumeParams) {
    const _rp = window.ProgressAPI.getResumeParams();
    START_BLOCK = _rp.startBlock;
    SKIP_INSTRUCTIONS = _rp.skipInstructions;
  }
  const NBACK_TOTAL_BLOCKS = 3;  // B1/B2/B3 (B4 由 gate 控制,不计入 resume)
  if (START_BLOCK >= NBACK_TOTAL_BLOCKS) {
    console.warn('[nback] startBlock', START_BLOCK, '>= totalBlocks, falling back to 0');
    START_BLOCK = 0;
    SKIP_INSTRUCTIONS = false;
    if (window.ProgressAPI) window.ProgressAPI.clear('nback', SUBJECT_ID);
  }

  // 全局状态 (三指退出读)
  window.__paradigmName = 'nback';
  window.__subjectId = SUBJECT_ID;
  window.__totalBlocks = NBACK_TOTAL_BLOCKS;
  window.__currentBlockIdx = START_BLOCK;
  window.__blockOrder = ['B1','B2','B3'];
  window.__balance = null;

  // Gating thresholds
  const GATE_TIME_S = 270;   // B3 max duration in seconds
  const GATE_ACC    = 0.80;  // B2 and B3 minimum accuracy

  // Timing defaults (ms) — CSV values override
  //
  // B1 / B2 / B3 / B4 resp_deadline 统一为 4000ms(2026-04-18 更新, CSV 已同步):
  //   文献依据: Suzuki M et al. (2018). Neural Correlates of Working Memory
  //     Maintenance in Advanced Aging: Evidence From fMRI.
  //     Frontiers in Aging Neuroscience 10:358.
  //     (中科院医学大类 2 区, IF 4.1, Q2)
  //   原文 verbatim (Methods): "Each item (the face or the dot) appeared for
  //     2000 ms, with a stimulus onset asynchrony (SOA) of 4000 ms."
  //   高龄老年组(77-82 岁)SOA=4000ms 即每试次响应窗 = 4000ms。
  //
  //   注:原注释引用 Gajewski et al. (2018) Frontiers in Psychology 支持 3000ms,
  //   但该论文实际使用 Max RT=1200ms 的字母 N-back, 不适用本项目的图片/场景 N-back,
  //   故已删除该引用。Bopp & Verhaeghen (2020) J Gerontol B meta-analysis 不给出
  //   具体 ms 推荐,只作为趋势旁证。
  //
  // B3 stim_dur 保持 1500ms(CSV 已含):
  //   文献依据: 图片/场景类 N-back 老年人推荐呈现时长 500-2000ms;
  //   复杂室内场景图 1500ms 为保守适老化选择。
  //   Citation: Frontiers in Aging Neuroscience (2016) DOI:10.3389/fnagi.2016.00032
  //
  // CSV 输出新增 rt_over_2s / rt_over_3s 标志列(2026-04-18):
  //   采集全量 RT + 标志列,供后处理按任意阈值筛选,不在采集时截断数据。
  const DEFAULTS = {
    stimDur: 1000,
    respDeadline: 4000,
    isi: 450,
    feedbackDur: 1500,
    confirmDur: 200,
  };

  // ==================== Checkpoint (inline — no ES module import) ====================
  function createCheckpoint(paradigm, subjectId, getDataFn) {
    let saving = false;
    let lastSaveTime = 0;
    let pendingSave = false;
    const MIN_INTERVAL_MS = 5000;
    const filename = `${paradigm}_${subjectId}_checkpoint.csv`;
    const lsKey = `checkpoint_${paradigm}_${subjectId}`;
    const API_BASE = window.location.origin;

    async function doSave() {
      if (saving) { pendingSave = true; return; }
      const csv = getDataFn();
      if (!csv) return;
      saving = true;
      lastSaveTime = Date.now();
      try { localStorage.setItem(lsKey, csv); } catch (e) { /* ignore */ }
      try {
        await fetch(`${API_BASE}/api/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ paradigm, subject_id: subjectId, filename, content: csv }),
        });
      } catch (e) {
        console.debug(`[Checkpoint] ${paradigm} server save failed, localStorage backup exists`);
      }
      saving = false;
      if (pendingSave) { pendingSave = false; doSave(); }
    }

    return {
      save() {
        const elapsed = Date.now() - lastSaveTime;
        if (elapsed < MIN_INTERVAL_MS) {
          if (!pendingSave) {
            pendingSave = true;
            setTimeout(() => { if (pendingSave) { pendingSave = false; doSave(); } }, MIN_INTERVAL_MS - elapsed);
          }
          return;
        }
        doSave();
      },
      forceSave() { doSave(); },
      clear() { try { localStorage.removeItem(lsKey); } catch (e) { /* ignore */ } },
    };
  }

  // ==================== Practice Retry Config ====================
  // 练习阶段通过门槛与最大重试次数
  //   文献依据：70-85% 为老年认知训练常用通过标准
  //   Citation: Antonenko et al. (2018). PMC6554703 — 85% advance / 65% decrease
  //   Citation: Frontiers fnhum.2025.1721330 — "up to three practice blocks until performance stabilizes"
  //   当前取 70% 为适老化下限，最多 2 次练习（第 2 次不过自动放行，避免挫败感）
  const PRACTICE_PASS_THRESHOLD = 0.70;
  const PRACTICE_MAX_ATTEMPTS = 2;
  const practiceAttempt = { B1: 0, B2: 0, B3: 0, B4: 0 };

  // ==================== State ====================
  const allTrialData = [];
  const blockSummaries = {};
  let b3StartTime = 0;
  let b3Duration  = 0;
  const checkpoint = createCheckpoint('nback', SUBJECT_ID, generateCSV);

  // ==================== CSV Loader ====================
  async function loadCSV(filename) {
    const resp = await fetch(`${LISTS_BASE}/${filename}`);
    if (!resp.ok) throw new Error(`Failed to load ${filename}: ${resp.status}`);
    const text = await resp.text();
    return parseCSV(text);
  }

  function parseCSV(text) {
    // Handle BOM
    const clean = text.replace(/^\uFEFF/, '');
    const lines = clean.split(/\r?\n/).filter(l => l.trim());
    if (lines.length < 2) return [];
    const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const vals = lines[i].split(',');
      if (vals.every(v => !v.trim() || v.trim().toLowerCase() === 'nan')) continue;
      const row = {};
      headers.forEach((h, idx) => { row[h] = (vals[idx] || '').trim(); });
      rows.push(row);
    }
    return rows;
  }

  // ==================== Path Resolver ====================
  function resolveImagePath(rawPath) {
    // CSV paths are like "stimuli/B1/ListA/xxx.webp" — relative to N-back project root
    // Web paths need to point to stimuli/nback/B1/ListA/xxx.webp
    if (!rawPath || rawPath.toLowerCase() === 'nan') return '';
    // Strip leading "stimuli/" if present, then prepend our base
    let p = rawPath.replace(/^stimuli\//, '');
    return `${STIMULI_BASE}/${p}`;
  }

  // ==================== Collect all images for preload ====================
  function collectAllImages(b1Rows, b2Rows, b3Rows, b4Rows) {
    const imgs = new Set();
    // Instruction images
    ['1.webp', '2.webp', 'B1_1.webp', 'B2_1.webp', 'B3_1.webp', 'B4_1.webp'].forEach(f => {
      imgs.add(`${INSTR_BASE}/${f}`);
    });
    // B1 — target + stim
    b1Rows.forEach(r => {
      if (r.image) imgs.add(resolveImagePath(r.image));
      // B1 target file: first row image is target
    });
    // B2
    b2Rows.forEach(r => { if (r.image) imgs.add(resolveImagePath(r.image)); });
    // B3
    b3Rows.forEach(r => {
      ['image', 'opt1', 'opt2', 'opt3', 'lag1_true'].forEach(k => {
        if (r[k]) imgs.add(resolveImagePath(r[k]));
      });
    });
    // B4
    b4Rows.forEach(r => { if (r.image) imgs.add(resolveImagePath(r.image)); });
    // Practice-only images (not in CSV, hardcoded in JS)
    ['B1/Practice/B1_Prac_S1_BlueCushions.webp',
    ].forEach(p => imgs.add(`${STIMULI_BASE}/${p}`));
    ['B2/Practice/B2_Prac_F1_LivingRoom_A.webp',
     'B2/Practice/B2_Prac_F1_LivingRoom_B.webp',
    ].forEach(p => imgs.add(`${STIMULI_BASE}/${p}`));
    ['B3/Practice/B3_Prac_P1_Bathroom.webp',
     'B3/Practice/B3_Prac_P2_DiningRoom.webp',
     'B3/Practice/B3_Prac_P3_LivingRoom.webp',
     'B3/Practice/B3_Prac_P4_Study.webp',
     'B3/Practice/B3_Prac_P5_Kitchen.webp',
    ].forEach(p => imgs.add(`${STIMULI_BASE}/${p}`));
    imgs.delete('');
    return [...imgs];
  }

  // ==================== Normalize helpers ====================
  function normResp(s) {
    if (!s) return '';
    const lower = s.trim().toLowerCase();
    const map = { '一样': 'same', '很像': 'similar', '不一样': 'different' };
    return map[lower] || lower;
  }

  function normPhase(s) {
    if (!s) return 'main';
    const lower = s.trim().toLowerCase();
    if (lower === 'practice' || lower === '练习') return 'practice';
    return 'main';
  }

  function toFloat(s, def) {
    const v = parseFloat(s);
    return isNaN(v) ? def : v;
  }

  function respLabel(resp) {
    return { same: '一样', similar: '很像', different: '不一样' }[resp] || resp;
  }

  // ==================== Data Recording ====================
  let _nbBlockCount = 0;
  let _nbBlockTotal = 0;

  /** 重置 block 内计数器 */
  function _resetBlockProgress(total, label) {
    _nbBlockCount = 0;
    _nbBlockTotal = total;
    _nbBlockLabel = label || '';
    var el = document.getElementById('_nback_progress');
    if (el) el.remove();
  }
  let _nbBlockLabel = '';

  /** 更新右上角进度 DOM */
  function _updateProgress(phase) {
    if (phase === 'hide') {
      var el = document.getElementById('_nback_progress');
      if (el) el.remove();
      return;
    }
    _nbBlockCount++;
    var el = document.getElementById('_nback_progress');
    if (!el) {
      el = document.createElement('div');
      el.id = '_nback_progress';
      el.style.cssText = 'position:fixed;top:12px;right:24px;color:rgba(0,0,0,0.3);font-size:36px;font-family:"PingFang SC","Microsoft YaHei",sans-serif;pointer-events:none;z-index:9999;';
      document.body.appendChild(el);
    }
    // 根据 phase 决定标签：练习阶段显示"练习"，正式阶段不显示
    var label = (phase === 'practice') ? '练习' : '';
    el.textContent = (label ? label + ' ' : '') + _nbBlockCount + ' / ' + _nbBlockTotal;
  }

  function recordTrial(block, data) {
    const attempt = data.phase === 'practice' ? practiceAttempt[block] : 0;
    allTrialData.push({ subject_id: SUBJECT_ID, block, practice_attempt: attempt, ...data });
    checkpoint.save(); // throttled — at most once per 5s
  }

  // ==================== CSV Export ====================
  function formatTimestamp() {
    const d = new Date();
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
  }

  function generateCSV() {
    const BOM = '\uFEFF';
    const fields = [
      'subject_id','block','trial_index','phase','practice_attempt','condition','image',
      'correct_resp','response','rt_ms','rt_hold','drift_max','drift_path','drift_end','tap_count','input_type','accuracy','timeout',
      'rt_over_2s','rt_over_3s',
    ];
    let csv = BOM + fields.join(',') + '\n';
    allTrialData.forEach(d => {
      csv += fields.map(f => {
        const v = d[f];
        return v === undefined || v === null ? '' : String(v).includes(',') ? `"${v}"` : v;
      }).join(',') + '\n';
    });
    return csv;
  }

  function generateSummaryJSON() {
    return JSON.stringify({
      subject_id: SUBJECT_ID,
      list_name: LIST_NAME,
      timestamp: new Date().toISOString(),
      blocks: blockSummaries,
      practice_attempts: { ...practiceAttempt },
      total_trials: allTrialData.length,
      b4_gate: {
        b3_duration_s: Math.round(b3Duration),
        b2_acc: blockSummaries.B2 ? blockSummaries.B2.accuracy : null,
        b3_acc: blockSummaries.B3 ? blockSummaries.B3.accuracy : null,
      },
    }, null, 2);
  }

  function downloadFile(content, filename, mime) {
    const blob = new Blob([content], { type: mime || 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function trySaveData(csvFn, csvContent, jsonFn, jsonContent) {
    try {
      const base = window.location.origin;
      const r1 = await safeFetch(`${base}/api/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paradigm: 'nback', subject_id: SUBJECT_ID, filename: csvFn, content: csvContent }),
      });
      if (r1.ok) {
        const r2 = await safeFetch(`${base}/api/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ paradigm: 'nback', subject_id: SUBJECT_ID, filename: jsonFn, content: jsonContent }),
        });
        if (r2.ok) return;
      }
    } catch(e) {
      console.warn('[N-back] server save failed, LocalPack has backup:', e);
    }
  }

  // ==================== Block Accuracy Calculator ====================
  function calcBlockAccuracy(block) {
    // Only count trials with a meaningful correct_resp (exclude warmup 'na' and empty)
    const mainTrials = allTrialData.filter(d =>
      d.block === block && d.phase === 'main' &&
      d.correct_resp && d.correct_resp !== 'na' && d.accuracy !== -1
    );
    if (mainTrials.length === 0) return 0;
    return mainTrials.filter(d => d.accuracy === 1).length / mainTrials.length;
  }

  // ==================== Practice Accuracy (per-block, per-attempt) ====================
  function calcPracticeAccuracy(block) {
    const attempt = practiceAttempt[block];
    const trials = allTrialData.filter(d =>
      d.block === block && d.phase === 'practice' &&
      d.practice_attempt === attempt && d.accuracy !== -1
    );
    if (trials.length === 0) return 0;
    return trials.filter(d => d.accuracy === 1).length / trials.length;
  }

  // ==================== Transition text pages (matching original PsychoPy) ====================
  function textPage(text, btnLabel) {
    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: `<div class="instruction-page" style="min-height:70vh;">
        <div class="instruction-body" style="font-size:44px;line-height:2;white-space:pre-line;">${text}</div>
      </div>`,
      choices: [btnLabel || '继续'],
      button_html: (c) => `<button class="jspsych-btn" style="margin-top:24px;">${c}</button>`,
    };
  }

  /** Basic practice-result page for legacy callers (currently B4 only) */
  function practiceResultPage(block) {
    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: function() {
        const accPct = Math.round(calcPracticeAccuracy(block) * 100);
        const msg = `练习结束\n\n正确率：${accPct}%\n\n按屏幕进入正式任务`;
        return `<div class="instruction-page" style="min-height:70vh;">
          <div class="instruction-body" style="font-size:44px;line-height:2;white-space:pre-line;">${msg}</div>
        </div>`;
      },
      choices: ['开始正式任务'],
      button_html: (c) => `<button class="jspsych-btn" style="margin-top:24px;font-size:32px;">${c}</button>`,
    };
  }

  /** Practice-result page with retry messaging */
  function practiceResultPageWithRetry(block) {
    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: function() {
        const acc = calcPracticeAccuracy(block);
        const accPct = Math.round(acc * 100);
        const attempt = practiceAttempt[block];
        let msg, btnText;
        if (acc >= PRACTICE_PASS_THRESHOLD) {
          msg = `练习完成！\n\n做得很好！\n按屏幕进入正式任务`;
          btnText = '开始正式任务';
        } else if (attempt < PRACTICE_MAX_ATTEMPTS) {
          msg = `我们再练一遍\n\n没关系，慢慢来`;
          btnText = '再练一次';
        } else {
          msg = `准备好了就继续\n\n按屏幕进入正式任务`;
          btnText = '开始正式任务';
        }
        return `<div class="instruction-page" style="min-height:70vh;">
          <div class="instruction-body" style="font-size:44px;line-height:2;white-space:pre-line;">${msg}</div>
        </div>`;
      },
      choices: function() {
        const acc = calcPracticeAccuracy(block);
        const attempt = practiceAttempt[block];
        if (acc >= PRACTICE_PASS_THRESHOLD || attempt >= PRACTICE_MAX_ATTEMPTS) return ['开始正式任务'];
        return ['再练一次'];
      },
      button_html: (c) => `<button class="jspsych-btn" style="margin-top:24px;font-size:32px;">${c}</button>`,
    };
  }

  // ==================== Trial builder for 3-button blocks (B1/B2) ====================
  function buildTrialNodes3btn(block, rows, targetImg) {
    const nodes = [];
    rows.forEach((row, idx) => {
      const phase = normPhase(row.phase);
      const correctResp = normResp(row.correct);
      const imgPath = resolveImagePath(row.image);
      // 练习阶段不限时（让老年人充分理解规则），正式阶段保留 deadline
      const rawDeadline = toFloat(row.resp_deadline, DEFAULTS.respDeadline / 1000) * 1000;
      const deadline = phase === 'practice' ? null : rawDeadline;
      const isi = toFloat(row.isi, DEFAULTS.isi / 1000) * 1000;
      const hasFeedback = row.feedback === '1' && phase === 'practice';
      const isWarmup = !correctResp || row.cond === 'warmup';

      // ISI fixation + 进度更新
      nodes.push((function(_ph, _wu) { return {
        type: jsPsychHtmlButtonResponse,
        stimulus: '<div class="fixation">+</div>',
        choices: [], trial_duration: isi, response_ends_trial: false,
        on_load: function() { if (!_wu) _updateProgress(_ph); },
      }; })(phase, isWarmup));

      if (isWarmup && block === 'B2') {
        // Warmup: just show image, no response
        nodes.push({
          type: jsPsychHtmlButtonResponse,
          stimulus: `<div class="nback-stim-container">
            <img src="${imgPath}" class="nback-stim-img">
            <p style="font-size:28px;color:var(--text-secondary);margin-top:16px;">请注意这张图片</p>
          </div>`,
          choices: [],
          trial_duration: toFloat(row.stim_dur, 1.0) * 1000,
          response_ends_trial: false,
          on_finish: function() {
            recordTrial(block, {
              trial_index: idx + 1, phase, condition: row.cond || 'warmup',
              image: row.image || '', correct_resp: '', response: '',
              rt_ms: -1, rt_hold: '', drift_max: '', drift_path: '', drift_end: '', tap_count: 0, input_type: '',
              accuracy: -1, timeout: 0,
              rt_over_2s: 0, rt_over_3s: 0,  // 纯展示不响应,填 0 保持列格式一致
            });
          },
        });
      } else {
        // Target panel only for B1
        const targetHtml = (block === 'B1' && targetImg)
          ? `<div class="nback-target-panel"><div class="nback-target-label">目标图</div><img src="${targetImg}"></div>`
          : '';

        // Stimulus + 3 buttons (B1: target+test stacked top-down, no centering gap)
        const b1Style = (block === 'B1' && targetImg) ? 'justify-content:flex-start;padding-top:2px;gap:2px;' : '';
        nodes.push({
          type: jsPsychHtmlButtonResponse,
          stimulus: `<div class="nback-stim-container" style="${b1Style}">
            ${targetHtml}
            <img src="${imgPath}" class="nback-stim-img">
          </div>
          <div class="nback-btn-row">
            <button class="nback-btn-3" id="nb-btn-same" data-choice="0">一样</button>
            <button class="nback-btn-3" id="nb-btn-similar" data-choice="1">很像</button>
            <button class="nback-btn-3" id="nb-btn-diff" data-choice="2">不一样</button>
          </div>`,
          choices: ['一样', '很像', '不一样'],
          button_html: (c) => `<button class="jspsych-btn" style="display:none !important;">${c}</button>`,
          trial_duration: deadline > 0 ? deadline : null,
          response_ends_trial: true,
          on_start: function() {
            if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
              ParadigmCamera.addEvent('stimulus_onset', { trial_index: idx + 1, block: block, image: row.image || '', is_target: correctResp === 'same' });
            }
          },
          on_load: function() {
            const jsBtns = document.querySelectorAll('#jspsych-html-button-response-btngroup button');
            ['nb-btn-same','nb-btn-similar','nb-btn-diff'].forEach((id, i) => {
              const btn = document.getElementById(id);
              if (btn && jsBtns[i]) {
                // 原生 click 兜底鼠标操作（TouchHardening 仅处理 touch/pen，忽略 mouse）
                btn.addEventListener('click', () => jsBtns[i].click());
                if (typeof TouchHardening !== 'undefined') {
                  TouchHardening.setupButton(btn, () => jsBtns[i].click());
                }
              }
            });
          },
          on_finish: function(data) {
            if (typeof TouchHardening !== 'undefined') TouchHardening.correctRT(data);
            const respMap = {0:'same', 1:'similar', 2:'different'};
            const resp = data.response !== null ? respMap[data.response] : '';
            const timeout = data.response === null;
            const acc = correctResp && resp === correctResp ? 1 : 0;

            recordTrial(block, {
              trial_index: idx + 1,
              phase, condition: row.cond || '',
              image: row.image || '',
              correct_resp: correctResp,
              response: resp,
              rt_ms: data.rt !== null ? data.rt : -1,
              rt_hold: data.rt !== null ? (data.rt_hold || '') : '',
              drift_max: data.rt !== null ? (data.drift_max || '') : '',
              drift_path: data.rt !== null ? (data.drift_path || '') : '',
              drift_end: data.rt !== null ? (data.drift_end || '') : '',
              tap_count: data.rt !== null ? (data.tap_count || 1) : 0,
              input_type: data.rt !== null ? (data.input_type || '') : '',
              accuracy: acc,
              timeout: timeout ? 1 : 0,
              rt_over_2s: timeout || data.rt > 2000 ? 1 : 0,
              rt_over_3s: timeout || data.rt > 3000 ? 1 : 0,
            });

            if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
              ParadigmCamera.addEvent('response', { trial_index: idx + 1, block: block, response: resp, rt: data.rt, correct: acc });
            }

            data._nb_correct = acc;
            data._nb_correctResp = correctResp;
            data._nb_resp = resp;
          },
        });

        // Feedback for practice
        if (hasFeedback) {
          nodes.push({
            type: jsPsychHtmlButtonResponse,
            stimulus: function() {
              const last = jsPsych.data.get().last(1).values()[0];
              if (last.response === null) return '<div></div>'; // 超时不弹提示（开发文档§7：超时直接进入下一试次）
              const fbClass = last._nb_correct ? 'correct' : 'incorrect';
              const fbText = last._nb_correct ? '✓ 对了' : '没关系，再看仔细';
              return `<div class="practice-feedback ${fbClass}">${fbText}</div>`;
            },
            trial_duration: function() {
              const last = jsPsych.data.get().last(1).values()[0];
              return last.response === null ? 1 : DEFAULTS.feedbackDur;
            },
            choices: [],
            response_ends_trial: false,
          });
        }
      }
    });
    return nodes;
  }

  // ==================== B1 Practice Rows (独立练习图片，不污染正式阶段) ====================
  // 目标图与正式阶段相同（0-back 整个 block 比对同一目标，不能换），
  // similar 和 different 用独立练习图片，正式阶段不出现。
  const B1_PRACTICE_ROWS = [
    { phase: 'practice', image: 'stimuli/B1/ListA/B1_T_LivingRoom_Base.webp',
      cond: 'same', correct: 'same', stim_dur: '1.0', resp_deadline: '3.0', isi: '0.45', feedback: '1' },
    { phase: 'practice', image: 'stimuli/B1/Practice/B1_Prac_S1_BlueCushions.webp',
      cond: 'similar', correct: 'similar', stim_dur: '1.0', resp_deadline: '3.0', isi: '0.45', feedback: '1' },
    { phase: 'practice', image: 'stimuli/B3/Practice/B3_Prac_P5_Kitchen.webp',
      cond: 'different', correct: 'different', stim_dur: '1.0', resp_deadline: '3.0', isi: '0.45', feedback: '1' },
    { phase: 'practice', image: 'stimuli/B3/Practice/B3_Prac_P4_Study.webp',
      cond: 'different', correct: 'different', stim_dur: '1.0', resp_deadline: '3.0', isi: '0.45', feedback: '1' },
  ];

  // ==================== B1: 0-back ====================
  function buildB1(rows) {
    const nodes = [];

    nodes.push({
      type: jsPsychCallFunction,
      func: () => {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('block_start', { block: 'B1' });
        }
      },
    });

    // Determine target image
    const targetRow = rows.find(r => normResp(r.correct) === 'same');
    const targetImg = targetRow ? resolveImagePath(targetRow.image) : '';

    // Study target page — large centered image (matching original show_study_target)
    nodes.push({
      type: jsPsychHtmlButtonResponse,
      stimulus: `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:60vh;">
        <p style="font-size:40px;font-weight:bold;margin-bottom:16px;">学习目标图</p>
        <img src="${targetImg}" style="max-height:48vh;max-width:82vw;object-fit:contain;border:4px solid #FFA500;border-radius:12px;">
        <p style="font-size:32px;color:var(--text-secondary);margin-top:16px;">记住这张目标图<br>准备好后按屏幕继续</p>
      </div>`,
      choices: ['记住了，继续'],
      button_html: (c) => `<button class="jspsych-btn" style="margin-top:16px;">${c}</button>`,
    });

    // === Practice loop (独立图片，max 2 attempts, pass ≥70%) ===
    const b1PracticeCount = B1_PRACTICE_ROWS.length;
    nodes.push({
      timeline: [
        { type: jsPsychCallFunction, func: () => { practiceAttempt.B1++; _resetBlockProgress(b1PracticeCount, '练习'); } },
        textPage('练习开始', '继续'),
        ...buildTrialNodes3btn('B1', B1_PRACTICE_ROWS, targetImg),
        practiceResultPageWithRetry('B1'),
      ],
      loop_function: () => {
        return calcPracticeAccuracy('B1') < PRACTICE_PASS_THRESHOLD
          && practiceAttempt.B1 < PRACTICE_MAX_ATTEMPTS;
      },
    });

    // Formal start text page
    nodes.push(textPage('正式任务开始\n\n请尽量又快又准', '继续'));

    // 3-2-1 倒计时 (白底深色大字,避免"点继续立刻进第一题"的猝不及防)
    // N-back 只加载 html-button-response,用空 choices + trial_duration 自动跳转
    for (let _c = 3; _c >= 1; _c--) {
      nodes.push({
        type: jsPsychHtmlButtonResponse,
        stimulus: `<div style="font-size:14vh;color:#1A1A2E;font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">${_c}</div>`,
        choices: [],
        trial_duration: 1000,
        response_ends_trial: false,
      });
    }

    // Formal trials — reset progress to actual main count
    const mainRows = rows.filter(r => normPhase(r.phase) === 'main');
    const mainTrialCount = mainRows.filter(r => r.cond !== 'warmup').length;
    nodes.push({ type: jsPsychCallFunction, func: function() { _resetBlockProgress(mainTrialCount, ''); } });
    nodes.push(...buildTrialNodes3btn('B1', mainRows, targetImg));

    // Block end
    nodes.push(textPage('本部分结束', '继续'));

    // Compute summary at end
    nodes.push({
      type: jsPsychCallFunction,
      func: () => {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('block_end', { block: 'B1' });
        }
        blockSummaries.B1 = { accuracy: calcBlockAccuracy('B1'), status: 'done' };
        checkpoint.forceSave();
      },
    });

    return nodes;
  }

  // ==================== B2 Practice Rows (独立练习图片，不污染正式阶段) ====================
  const B2_PRACTICE_ROWS = [
    { phase: 'practice', image: 'stimuli/B2/Practice/B2_Prac_F1_LivingRoom_A.webp',
      cond: 'warmup', correct: '', stim_dur: '1.0', resp_deadline: '0.0', isi: '0.45', feedback: '0' },
    { phase: 'practice', image: 'stimuli/B2/Practice/B2_Prac_F1_LivingRoom_A.webp',
      cond: 'same', correct: 'same', stim_dur: '1.0', resp_deadline: '3.0', isi: '0.45', feedback: '1' },
    { phase: 'practice', image: 'stimuli/B2/Practice/B2_Prac_F1_LivingRoom_B.webp',
      cond: 'similar', correct: 'similar', stim_dur: '1.0', resp_deadline: '3.0', isi: '0.45', feedback: '1' },
    { phase: 'practice', image: 'stimuli/B3/Practice/B3_Prac_P1_Bathroom.webp',
      cond: 'different', correct: 'different', stim_dur: '1.0', resp_deadline: '3.0', isi: '0.45', feedback: '1' },
    { phase: 'practice', image: 'stimuli/B3/Practice/B3_Prac_P2_DiningRoom.webp',
      cond: 'different', correct: 'different', stim_dur: '1.0', resp_deadline: '3.0', isi: '0.45', feedback: '1' },
  ];

  // ==================== B2: 1-back ====================
  function buildB2(rows) {
    const nodes = [];

    nodes.push({
      type: jsPsychCallFunction,
      func: () => {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('block_start', { block: 'B2' });
        }
      },
    });

    // === Practice loop (独立图片，不污染正式阶段) ===
    const b2PracticeCount = B2_PRACTICE_ROWS.filter(r => r.cond !== 'warmup').length;
    nodes.push({
      timeline: [
        { type: jsPsychCallFunction, func: () => { practiceAttempt.B2++; _resetBlockProgress(b2PracticeCount, '练习'); } },
        textPage('练习开始', '继续'),
        ...buildTrialNodes3btn('B2', B2_PRACTICE_ROWS, ''),
        practiceResultPageWithRetry('B2'),
      ],
      loop_function: () => {
        return calcPracticeAccuracy('B2') < PRACTICE_PASS_THRESHOLD
          && practiceAttempt.B2 < PRACTICE_MAX_ATTEMPTS;
      },
    });

    // Formal start
    nodes.push(textPage('正式任务开始\n\n请尽量又快又准', '继续'));

    // 3-2-1 倒计时 (同 B1)
    for (let _c = 3; _c >= 1; _c--) {
      nodes.push({
        type: jsPsychHtmlButtonResponse,
        stimulus: `<div style="font-size:14vh;color:#1A1A2E;font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">${_c}</div>`,
        choices: [],
        trial_duration: 1000,
        response_ends_trial: false,
      });
    }

    // Formal trials — reset progress to actual main count
    const mainRows = rows.filter(r => normPhase(r.phase) === 'main');
    const mainTrialCount = mainRows.filter(r => r.cond !== 'warmup').length;
    nodes.push({ type: jsPsychCallFunction, func: function() { _resetBlockProgress(mainTrialCount, ''); } });
    nodes.push(...buildTrialNodes3btn('B2', mainRows, ''));

    // Block end
    nodes.push(textPage('本部分结束', '继续'));

    nodes.push({
      type: jsPsychCallFunction,
      func: () => {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('block_end', { block: 'B2' });
        }
        blockSummaries.B2 = { accuracy: calcBlockAccuracy('B2'), status: 'done' };
        checkpoint.forceSave();
      },
    });

    return nodes;
  }

  // ==================== B3 trial node builder ====================
  function buildB3TrialNodes(rows) {
    const nodes = [];
    rows.forEach((row, idx) => {
      const phase = normPhase(row.phase);
      const eventType = (row.event || '').trim().toLowerCase();
      const imgPath = resolveImagePath(row.image);
      const isi = toFloat(row.isi, DEFAULTS.isi / 1000) * 1000;
      const hasFeedback = row.feedback === '1' && phase === 'practice';
      const isWarmup = eventType === 'stim' || eventType === 's'; // stimulus-only events are not response trials

      // ISI fixation + 进度更新
      nodes.push((function(_ph, _wu) { return {
        type: jsPsychHtmlButtonResponse,
        stimulus: '<div class="fixation">+</div>',
        choices: [], trial_duration: isi, response_ends_trial: false,
        on_load: function() { if (!_wu) _updateProgress(_ph); },
      }; })(phase, isWarmup));

      if (eventType === 'stim' || eventType === 's') {
        const stimDur = toFloat(row.stim_dur, 1.0) * 1000;
        nodes.push({
          type: jsPsychHtmlButtonResponse,
          stimulus: `<div class="nback-stim-container">
            <img src="${imgPath}" class="nback-stim-img">
          </div>`,
          choices: [],
          trial_duration: stimDur,
          response_ends_trial: false,
          on_start: function() {
            if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
              ParadigmCamera.addEvent('stimulus_onset', { trial_index: idx + 1, block: 'B3', image: row.image || '', is_target: false });
            }
          },
          on_finish: function() {
            recordTrial('B3', {
              trial_index: idx + 1, phase, condition: 'stim',
              image: row.image || '', correct_resp: '', response: '',
              rt_ms: -1, rt_hold: '', drift_max: '', drift_path: '', drift_end: '', tap_count: 0, input_type: '',
              accuracy: -1, timeout: 0,
              rt_over_2s: 0, rt_over_3s: 0,  // B3 stim 阶段只展示图片不响应
            });
          },
        });
      } else if (eventType === 'probe' || eventType === 'p') {
        const cueDur = toFloat(row.stim_dur, 0.8) * 1000;
        // fallback 跟随 DEFAULTS.respDeadline (2026-04-18 统一为 4000ms)
        const rawDeadline = toFloat(row.resp_deadline, DEFAULTS.respDeadline / 1000) * 1000;
        const deadline = phase === 'practice' ? null : rawDeadline;
        const correctOpt = parseInt(row.correct_opt) || 1;

        const opt1 = resolveImagePath(row.opt1);
        const opt2 = resolveImagePath(row.opt2);
        const opt3 = resolveImagePath(row.opt3);

        // Show cue briefly
        nodes.push({
          type: jsPsychHtmlButtonResponse,
          stimulus: `<div class="nback-stim-container">
            <p style="font-size:36px;color:#FFA500;margin-bottom:12px;">提示</p>
            <img src="${imgPath}" class="nback-stim-img" style="border:4px solid #FFA500;">
          </div>`,
          choices: [],
          trial_duration: cueDur,
          response_ends_trial: false,
        });

        // Show 3 options
        nodes.push({
          type: jsPsychHtmlButtonResponse,
          stimulus: `<div class="nback-stim-container" style="min-height:55vh;">
            <p style="font-size:32px;margin-bottom:12px;">上一张图片是哪个？</p>
            <div class="nback-probe-options">
              <div class="nback-probe-opt" id="nb-opt-1"><img src="${opt1}"></div>
              <div class="nback-probe-opt" id="nb-opt-2"><img src="${opt2}"></div>
              <div class="nback-probe-opt" id="nb-opt-3"><img src="${opt3}"></div>
            </div>
          </div>`,
          choices: ['1', '2', '3'],
          button_html: (c) => `<button class="jspsych-btn" style="display:none !important;">${c}</button>`,
          trial_duration: deadline,
          response_ends_trial: true,
          on_start: function() {
            if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
              ParadigmCamera.addEvent('stimulus_onset', { trial_index: idx + 1, block: 'B3', image: row.image || '', is_target: true });
            }
          },
          on_load: function() {
            const jsBtns = document.querySelectorAll('#jspsych-html-button-response-btngroup button');
            [1, 2, 3].forEach(i => {
              const el = document.getElementById(`nb-opt-${i}`);
              if (el && jsBtns[i-1]) {
                // 原生 click 兜底鼠标操作
                el.addEventListener('click', () => {
                  el.classList.add('selected');
                  jsBtns[i-1].click();
                });
                if (typeof TouchHardening !== 'undefined') {
                  TouchHardening.setupButton(el, () => {
                    el.classList.add('selected');
                    jsBtns[i-1].click();
                  });
                }
              }
            });
          },
          on_finish: function(data) {
            if (typeof TouchHardening !== 'undefined') TouchHardening.correctRT(data);
            const resp = data.response !== null ? data.response + 1 : 0;
            const timeout = data.response === null;
            const acc = resp === correctOpt ? 1 : 0;

            recordTrial('B3', {
              trial_index: idx + 1, phase, condition: 'probe',
              image: row.image || '', correct_resp: correctOpt,
              response: resp, rt_ms: data.rt !== null ? data.rt : -1,
              rt_hold: data.rt !== null ? (data.rt_hold || '') : '',
              drift_max: data.rt !== null ? (data.drift_max || '') : '',
              drift_path: data.rt !== null ? (data.drift_path || '') : '',
              drift_end: data.rt !== null ? (data.drift_end || '') : '',
              tap_count: data.rt !== null ? (data.tap_count || 1) : 0,
              input_type: data.rt !== null ? (data.input_type || '') : '',
              accuracy: acc, timeout: timeout ? 1 : 0,
              rt_over_2s: timeout || data.rt > 2000 ? 1 : 0,
              rt_over_3s: timeout || data.rt > 3000 ? 1 : 0,
            });

            if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
              ParadigmCamera.addEvent('response', { trial_index: idx + 1, block: 'B3', response: resp, rt: data.rt, correct: acc });
            }

            data._nb_correct = acc;
            data._nb_correctOpt = correctOpt;
          },
        });

        if (hasFeedback) {
          nodes.push({
            type: jsPsychHtmlButtonResponse,
            stimulus: function() {
              const last = jsPsych.data.get().last(1).values()[0];
              if (last.response === null) return '<div></div>'; // 超时不弹提示（开发文档§7：超时直接进入下一试次）
              const fbClass = last._nb_correct ? 'correct' : 'incorrect';
              const fbText = last._nb_correct ? '✓ 对了' : '没关系，再看仔细';
              return `<div class="practice-feedback ${fbClass}">${fbText}</div>`;
            },
            trial_duration: function() {
              const last = jsPsych.data.get().last(1).values()[0];
              return last.response === null ? 1 : DEFAULTS.feedbackDur;
            },
            choices: [],
            response_ends_trial: false,
          });
        }
      }
    });
    return nodes;
  }

  // ==================== B3 Practice Rows (独立练习图片，不污染正式阶段) ====================
  // 序列设计：4 stim → probe1 → 3 stim → probe2（共 9 事件，2 个计分 probe）
  // 选项规则遵循开发文档 §4: lag-1 正确，诱饵从刺激池随机取
  const B3_PRACTICE_ROWS = [
    { phase: 'practice', event: 'stim', image: 'stimuli/B3/Practice/B3_Prac_P1_Bathroom.webp',
      stim_dur: '1.5', resp_deadline: '0.0', isi: '0.45', feedback: '0' },
    { phase: 'practice', event: 'stim', image: 'stimuli/B3/Practice/B3_Prac_P2_DiningRoom.webp',
      stim_dur: '1.5', resp_deadline: '0.0', isi: '0.45', feedback: '0' },
    { phase: 'practice', event: 'stim', image: 'stimuli/B3/Practice/B3_Prac_P3_LivingRoom.webp',
      stim_dur: '1.5', resp_deadline: '0.0', isi: '0.45', feedback: '0' },
    { phase: 'practice', event: 'stim', image: 'stimuli/B3/Practice/B3_Prac_P4_Study.webp',
      stim_dur: '1.5', resp_deadline: '0.0', isi: '0.45', feedback: '0' },
    // Probe 1: 上一张 = Study → correct_opt=1
    { phase: 'practice', event: 'probe', image: 'stimuli/B3/ListA/cue.webp',
      lag1_true: 'stimuli/B3/Practice/B3_Prac_P4_Study.webp',
      opt1: 'stimuli/B3/Practice/B3_Prac_P4_Study.webp',
      opt2: 'stimuli/B3/Practice/B3_Prac_P1_Bathroom.webp',
      opt3: 'stimuli/B3/Practice/B3_Prac_P5_Kitchen.webp',
      correct_opt: '1', stim_dur: '0.8', resp_deadline: '3.0', isi: '0.45', feedback: '1' },
    { phase: 'practice', event: 'stim', image: 'stimuli/B3/Practice/B3_Prac_P5_Kitchen.webp',
      stim_dur: '1.5', resp_deadline: '0.0', isi: '0.45', feedback: '0' },
    { phase: 'practice', event: 'stim', image: 'stimuli/B3/Practice/B3_Prac_P2_DiningRoom.webp',
      stim_dur: '1.5', resp_deadline: '0.0', isi: '0.45', feedback: '0' },
    { phase: 'practice', event: 'stim', image: 'stimuli/B3/Practice/B3_Prac_P1_Bathroom.webp',
      stim_dur: '1.5', resp_deadline: '0.0', isi: '0.45', feedback: '0' },
    // Probe 2: 上一张 = Bathroom → correct_opt=2
    { phase: 'practice', event: 'probe', image: 'stimuli/B3/ListA/cue.webp',
      lag1_true: 'stimuli/B3/Practice/B3_Prac_P1_Bathroom.webp',
      opt1: 'stimuli/B3/Practice/B3_Prac_P5_Kitchen.webp',
      opt2: 'stimuli/B3/Practice/B3_Prac_P1_Bathroom.webp',
      opt3: 'stimuli/B3/Practice/B3_Prac_P3_LivingRoom.webp',
      correct_opt: '2', stim_dur: '0.8', resp_deadline: '3.0', isi: '0.45', feedback: '1' },
  ];

  // ==================== B3: 1-back Probe Recall ====================
  function buildB3(rows) {
    const nodes = [];

    nodes.push({
      type: jsPsychCallFunction,
      func: () => {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('block_start', { block: 'B3' });
        }
      },
    });

    // === Practice loop (独立图片，不污染正式阶段) ===
    const b3PracticeProbeCount = B3_PRACTICE_ROWS.filter(r => {
      const ev = (r.event || '').trim().toLowerCase();
      return ev === 'probe' || ev === 'p';
    }).length;
    nodes.push({
      timeline: [
        { type: jsPsychCallFunction, func: () => { practiceAttempt.B3++; _resetBlockProgress(b3PracticeProbeCount, '练习'); } },
        textPage('练习开始', '继续'),
        ...buildB3TrialNodes(B3_PRACTICE_ROWS),
        practiceResultPageWithRetry('B3'),
      ],
      loop_function: () => {
        return calcPracticeAccuracy('B3') < PRACTICE_PASS_THRESHOLD
          && practiceAttempt.B3 < PRACTICE_MAX_ATTEMPTS;
      },
    });

    // Formal start — also record B3 timing from here
    nodes.push(textPage('正式任务开始\n\n请尽量又快又准', '继续'));

    // 3-2-1 倒计时 (同 B1/B2)
    for (let _c = 3; _c >= 1; _c--) {
      nodes.push({
        type: jsPsychHtmlButtonResponse,
        stimulus: `<div style="font-size:14vh;color:#1A1A2E;font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">${_c}</div>`,
        choices: [],
        trial_duration: 1000,
        response_ends_trial: false,
      });
    }

    // Record B3 start time (only for main phase, as per original gating logic)
    nodes.push({
      type: jsPsychCallFunction,
      func: () => { b3StartTime = performance.now(); },
    });

    // Main trials — reset progress to actual main probe count
    const mainRows = rows.filter(r => normPhase(r.phase) === 'main');
    const mainProbeCount = mainRows.filter(r => { const ev = (r.event||'').trim().toLowerCase(); return ev === 'probe' || ev === 'p'; }).length;
    nodes.push({ type: jsPsychCallFunction, func: function() { _resetBlockProgress(mainProbeCount, ''); } });
    nodes.push(...buildB3TrialNodes(mainRows));

    // Block end
    nodes.push(textPage('本部分结束', '继续'));

    // Record B3 end time + summary
    nodes.push({
      type: jsPsychCallFunction,
      func: () => {
        b3Duration = (performance.now() - b3StartTime) / 1000;
        const probeTrials = allTrialData.filter(d => d.block === 'B3' && d.phase === 'main' && d.condition === 'probe');
        const acc = probeTrials.length > 0
          ? probeTrials.filter(d => d.accuracy === 1).length / probeTrials.length : 0;
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('block_end', { block: 'B3' });
        }
        blockSummaries.B3 = { accuracy: acc, duration_s: Math.round(b3Duration), status: 'done' };
        checkpoint.forceSave();
      },
    });

    return nodes;
  }

  // ==================== B4 trial node builder ====================
  function buildB4TrialNodes(rows) {
    const nodes = [];

    rows.forEach((row, idx) => {
      const phase = normPhase(row.phase);
      const imgPath = resolveImagePath(row.image);
      const correct = (row.correct || '').trim().toLowerCase();
      const isWarmup = correct === 'na' || correct === 'warmup' || correct === '';
      const isTarget = correct === 'press' || correct === 'hit' || correct === 'go' || correct === '1';
      const stimDur = toFloat(row.stim_dur, 1.0) * 1000;
      // fallback 跟随 DEFAULTS.respDeadline (2026-04-18 统一为 4000ms,原 B4 fallback 2.5 已过时)
      const rawDeadline = toFloat(row.resp_deadline, DEFAULTS.respDeadline / 1000) * 1000;
      const deadline = phase === 'practice' ? null : rawDeadline;
      const isi = toFloat(row.isi, DEFAULTS.isi / 1000) * 1000;
      const hasFeedback = row.feedback === '1' && phase === 'practice';

      // ISI fixation + 进度更新
      nodes.push((function(_ph, _wu) { return {
        type: jsPsychHtmlButtonResponse,
        stimulus: '<div class="fixation">+</div>',
        choices: [], trial_duration: isi, response_ends_trial: false,
        on_load: function() { if (!_wu) _updateProgress(_ph); },
      }; })(phase, isWarmup));

      if (isWarmup) {
        nodes.push({
          type: jsPsychHtmlButtonResponse,
          stimulus: `<div class="nback-stim-container b4-mode">
            <img src="${imgPath}" class="nback-stim-img">
          </div>`,
          choices: [],
          trial_duration: stimDur,
          response_ends_trial: false,
          on_finish: function() {
            recordTrial('B4', {
              trial_index: idx + 1, phase, condition: 'warmup',
              image: row.image || '', correct_resp: 'na', response: '',
              rt_ms: -1, rt_hold: '', drift_max: '', drift_path: '', drift_end: '', tap_count: 0, input_type: '',
              accuracy: -1, timeout: 0,
              rt_over_2s: 0, rt_over_3s: 0,  // B4 warmup 只展示不响应
            });
          },
        });
      } else {
        nodes.push({
          type: jsPsychHtmlButtonResponse,
          stimulus: `<div class="nback-stim-container b4-mode">
            <img src="${imgPath}" class="nback-stim-img">
          </div>
          <button class="nback-go-btn" id="nb-go-btn">按这里</button>`,
          choices: ['按这里'],
          button_html: (c) => `<button class="jspsych-btn" style="display:none !important;">${c}</button>`,
          trial_duration: deadline > 0 ? deadline : null,
          response_ends_trial: true,
          on_start: function() {
            if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
              ParadigmCamera.addEvent('stimulus_onset', { trial_index: idx + 1, block: 'B4', image: row.image || '', is_target: isTarget });
            }
          },
          on_load: function() {
            const jsBtns = document.querySelectorAll('#jspsych-html-button-response-btngroup button');
            const goBtn = document.getElementById('nb-go-btn');
            if (goBtn && jsBtns[0]) {
              // 原生 click 兜底鼠标操作
              goBtn.addEventListener('click', () => jsBtns[0].click());
              if (typeof TouchHardening !== 'undefined') {
                TouchHardening.setupButton(goBtn, () => jsBtns[0].click());
              }
            }
          },
          on_finish: function(data) {
            if (typeof TouchHardening !== 'undefined') TouchHardening.correctRT(data);
            const pressed = data.response !== null;
            const timeout = !pressed;
            let acc;
            if (isTarget) {
              acc = pressed ? 1 : 0;
            } else {
              acc = pressed ? 0 : 1;
            }

            // B4 (2-back): 只有 Go trial(target)才有 rt;No-Go 正确时 rt=-1 属于正常(不视为 timeout)
            // rt_over_X 仅在有 rt 时比较;无 rt 的情况(No-Go 正确 or Go 未响应)按 timeout 判断
            recordTrial('B4', {
              trial_index: idx + 1, phase, condition: row.cond || (isTarget ? 'target' : 'foil'),
              image: row.image || '',
              correct_resp: isTarget ? 'press' : 'none',
              response: pressed ? 'press' : 'none',
              rt_ms: data.rt !== null ? data.rt : -1,
              rt_hold: data.rt !== null ? (data.rt_hold || '') : '',
              drift_max: data.rt !== null ? (data.drift_max || '') : '',
              drift_path: data.rt !== null ? (data.drift_path || '') : '',
              drift_end: data.rt !== null ? (data.drift_end || '') : '',
              tap_count: data.rt !== null ? (data.tap_count || 1) : 0,
              input_type: data.rt !== null ? (data.input_type || '') : '',
              accuracy: acc, timeout: timeout && isTarget ? 1 : 0,
              rt_over_2s: (data.rt !== null && data.rt > 2000) || (timeout && isTarget) ? 1 : 0,
              rt_over_3s: (data.rt !== null && data.rt > 3000) || (timeout && isTarget) ? 1 : 0,
            });

            if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
              ParadigmCamera.addEvent('response', { trial_index: idx + 1, block: 'B4', response: pressed ? 'press' : 'none', rt: data.rt, correct: acc });
            }

            data._nb_correct = acc;
            data._nb_isTarget = isTarget;
          },
        });

        if (hasFeedback) {
          nodes.push({
            type: jsPsychHtmlButtonResponse,
            stimulus: function() {
              const last = jsPsych.data.get().last(1).values()[0];
              if (last.response === null) return '<div></div>'; // 超时不弹提示（开发文档§7：超时直接进入下一试次）
              const fbClass = last._nb_correct ? 'correct' : 'incorrect';
              const fbText = last._nb_correct ? '✓ 对了' : '没关系，再看仔细';
              return `<div class="practice-feedback ${fbClass}">${fbText}</div>`;
            },
            trial_duration: function() {
              const last = jsPsych.data.get().last(1).values()[0];
              return last.response === null ? 1 : DEFAULTS.feedbackDur;
            },
            choices: [],
            response_ends_trial: false,
          });
        }
      }
    });
    return nodes;
  }

  // ==================== B4: 2-back ====================
  function buildB4(rows) {
    const nodes = [];

    nodes.push({
      type: jsPsychCallFunction,
      func: () => {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('block_start', { block: 'B4' });
        }
      },
    });

    // Practice start
    nodes.push(textPage('练习开始', '继续'));

    // Practice trials
    const pracRows = rows.filter(r => normPhase(r.phase) === 'practice');
    nodes.push(...buildB4TrialNodes(pracRows));

    // Practice result + transition
    nodes.push(practiceResultPage('B4'));

    // Formal start
    nodes.push(textPage('正式任务开始\n\n请尽量又快又准', '继续'));

    // 3-2-1 倒计时 (B4 罕见触发,但一致性起见也加)
    for (let _c = 3; _c >= 1; _c--) {
      nodes.push({
        type: jsPsychHtmlButtonResponse,
        stimulus: `<div style="font-size:14vh;color:#1A1A2E;font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">${_c}</div>`,
        choices: [],
        trial_duration: 1000,
        response_ends_trial: false,
      });
    }

    // Main trials
    const mainRows = rows.filter(r => normPhase(r.phase) === 'main');
    nodes.push(...buildB4TrialNodes(mainRows));

    // Block end
    nodes.push(textPage('本部分结束', '继续'));

    nodes.push({
      type: jsPsychCallFunction,
      func: () => {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('block_end', { block: 'B4' });
        }
        blockSummaries.B4 = { accuracy: calcBlockAccuracy('B4'), status: 'done' };
        checkpoint.forceSave();
      },
    });

    return nodes;
  }

  // ==================== Instruction Pages ====================

  /** Generic instruction page (welcome, rest, etc.) */
  function instrPage(imgFile, btnText) {
    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: `<div style="text-align:center;">
        <img src="${INSTR_BASE}/${imgFile}" class="nback-instr-img">
      </div>`,
      choices: [btnText || '继续'],
      button_html: (c) => `<button class="jspsych-btn" style="margin-top:16px;">${c}</button>`,
    };
  }

  function restPage() {
    return instrPage('2.webp', '继续');
  }

  /**
   * Rich instruction page for each block.
   * Embeds the original hand-drawn illustration image + structured HTML text.
   */
  function blockInstrPage(block) {
    const imgFile = `${block}_1.webp`;
    const content = {
      B1: {
        badge: '第 1/4 部分',
        title: '记住目标图，逐张比较',
        steps: [
          { icon: '1', text: '<b>记住目标图</b>：先看一张目标图，记住它的样子' },
          { icon: '2', text: '<b>逐张比较</b>：之后每出现一张图，和目标图比较' },
        ],
        buttons: [
          { label: '一样', color: '#4CAF50', desc: '和目标图一模一样' },
          { label: '很像', color: '#FFA726', desc: '大体一样，只有一点变化' },
          { label: '不一样', color: '#EF5350', desc: '已经不是同一张图' },
        ],
        tip: '不确定也要选一个',
      },
      B2: {
        badge: '第 2/4 部分',
        title: '和上一张比较',
        steps: [
          { icon: '1', text: '图片一张一张出现' },
          { icon: '2', text: '每张图和<b>上一张</b>比较，判断关系' },
        ],
        buttons: [
          { label: '一样', color: '#4CAF50', desc: '和上一张一模一样' },
          { label: '很像', color: '#FFA726', desc: '大体一样，只有一点变化' },
          { label: '不一样', color: '#EF5350', desc: '已经不是同一张图' },
        ],
        note: '第1张只看不答，从第2张开始比较',
        tip: '不确定也要选一个',
      },
      B3: {
        badge: '第 3/4 部分',
        title: '看到提示图，回忆上一张',
        steps: [
          { icon: '1', text: '图片一张张出现，<b>只看</b>，记住顺序' },
          { icon: '2', text: '看到<span style="color:#FFA500;font-weight:bold;">提示图</span>时，需要作答' },
          { icon: '3', text: '从3张图中选出：<b>上一张是哪张？</b>' },
        ],
        buttons: [],
        tip: '不确定也要选一个',
        // 占位文字，后续统一修改指导语时替换
        highlight: '① 图片依次出现，只需观看　② 出现橙色提示图时 → 从下方3张中选"上一张是哪张"　③ 不确定也要选一个',
      },
      B4: {
        badge: '第 4/4 部分',
        title: '跳过一张，和前两张比较',
        steps: [
          { icon: '1', text: '图片快速连续出现' },
          { icon: '2', text: '每张图和<b>前两张</b>（跳过一张）比较' },
        ],
        buttons: [],
        actions: [
          { text: '一样', icon: '', result: '点<span style="color:white;background:#4CAF50;padding:2px 16px;border-radius:8px;font-weight:bold;">匹配</span>按钮' },
          { text: '不一样', icon: '', result: '不操作，等下一张' },
        ],
        highlight: '记住：跳一张比！不是和上一张比！',
        tip: '不确定也要按一下',
      },
    };
    const c = content[block];
    if (!c) return instrPage(imgFile, '开始');

    // Build HTML — 图片即指导语，不重复文字
    let html = `<div class="nback-instr-rich">`;
    // Badge
    html += `<div class="nback-instr-badge">${c.badge}</div>`;
    // Title
    html += `<div class="nback-instr-title">${c.title}</div>`;
    // Illustration image — 占满可用空间，是主要信息载体
    html += `<div class="nback-instr-img-wrap">
      <img src="${INSTR_BASE}/${imgFile}" class="nback-instr-illust">
    </div>`;
    // Note (B2 warmup — 图片里没这个信息，需要保留)
    if (c.note) {
      html += `<div class="nback-instr-note">${c.note}</div>`;
    }
    // Highlight (B4 — 关键区分信息，需要保留)
    if (c.highlight) {
      html += `<div class="nback-instr-highlight">${c.highlight}</div>`;
    }
    html += `</div>`;

    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: html,
      choices: ['我明白了，开始'],
      button_html: (c) => `<button class="jspsych-btn nback-instr-start-btn">${c}</button>`,
    };
  }

  // ==================== Main ====================
  async function main() {
    // Load all CSV lists
    let b1Rows, b2Rows, b3Rows, b4Rows;
    try {
      [b1Rows, b2Rows, b3Rows, b4Rows] = await Promise.all([
        loadCSV(`B1_${LIST_NAME}.csv`),
        loadCSV(`B2_${LIST_NAME}.csv`),
        loadCSV(`B3_${LIST_NAME}.csv`),
        loadCSV(`B4_${LIST_NAME}.csv`),
      ]);
    } catch (e) {
      document.getElementById('jspsych-target').innerHTML =
        `<div class="instruction-page"><div class="instruction-title" style="color:var(--error);">加载失败</div>
         <div class="instruction-body">${e.message}<br>请检查 lists/ 目录下的 CSV 文件</div></div>`;
      return;
    }

    const allImages = collectAllImages(b1Rows, b2Rows, b3Rows, b4Rows);

    const timeline = [];

    // Preload images + audio + instruction images
    // 实际磁盘上的音频数量:b1=8, b2=12, b3=8(对齐当前 VoiceGuide 脚本)
    // 原先写死 15 会 404 17 个,触发 jsPsych preload 的 statusText 崩溃导致 stuck
    var _nbackAudioFiles = [];
    var _nbackAudioBase = '../../audio/nback/';
    var _nbackCounts = { b1: 8, b2: 12, b3: 8 };
    Object.keys(_nbackCounts).forEach(function(b) {
      var n = _nbackCounts[b];
      for (var i = 1; i <= n; i++) _nbackAudioFiles.push(_nbackAudioBase + b + '_s' + String(i).padStart(2,'0') + '.mp3');
      _nbackAudioFiles.push(_nbackAudioBase + b + '_retry.mp3');
    });
    var _instrImgs = ['img/block1.webp','img/block2.webp','img/block3.webp'];

    timeline.push({
      type: jsPsychPreload,
      images: allImages.concat(_instrImgs),
      audio: _nbackAudioFiles,
      show_progress_bar: true,
      message: '<p style="font-size:32px;">正在加载，请稍候...</p>',
      continue_after_error: true,
    });
    // 2026-04-19: 预加载后检查失败资源
    timeline.push({
      type: jsPsychCallFunction, async: true,
      func: function(done) {
        if (typeof TouchHardening !== 'undefined' && TouchHardening.checkLoadFailures) {
          TouchHardening.checkLoadFailures({ paradigmName: 'N-back 图片记忆' }).then(function() { done(); });
        } else { done(); }
      },
    });

    // F4 (2026-04-19): resume 场景 — 从 progress.paradigmState 恢复 blockSummaries + b3Duration
    // 这样 B4 gate 检查能读到正确的 b2/b3 成绩
    if (START_BLOCK > 0 && window.ProgressAPI) {
      const prog = window.ProgressAPI.read('nback', SUBJECT_ID);
      if (prog && prog.paradigmState) {
        const ps = prog.paradigmState;
        if (ps.blockSummaries) {
          Object.keys(ps.blockSummaries).forEach(k => { blockSummaries[k] = ps.blockSummaries[k]; });
        }
        if (typeof ps.b3Duration === 'number') b3Duration = ps.b3Duration;
        console.log('[nback] restored paradigmState from progress:', ps);
      }
    }

    // F4 helper: 短提醒页(resume 时替换完整 VoiceGuide)
    function buildShortReminder(blockName, focusText) {
      return {
        type: jsPsychHtmlButtonResponse,
        stimulus: `
          <div class="instruction-page">
            <div class="instruction-title">接着测试 - ${blockName}</div>
            <div class="instruction-body">
              ${focusText}<br><br>
              <span style="font-size:22px;color:#666;">准备好后点击继续</span>
            </div>
          </div>`,
        choices: ['继续'],
        button_html: (c) => `<button class="jspsych-btn" style="margin-top:24px;">${c}</button>`,
      };
    }
    // F4: 写 progress 的 trial(复用 ProgressAPI)
    function writeNbackProgressTrial(blockIdx) {
      if (!window.ProgressAPI || !window.ProgressAPI.writeTrial) return null;
      return window.ProgressAPI.writeTrial('nback', SUBJECT_ID, blockIdx, NBACK_TOTAL_BLOCKS, {
        paradigmState: {
          blockSummaries: JSON.parse(JSON.stringify(blockSummaries)),  // snapshot
          b3Duration: b3Duration,
        },
      });
    }
    // 因为 progress 在 trial 运行时动态读 blockSummaries/b3Duration,需要延迟计算
    function makeWriteProgressTrial(blockIdx) {
      return {
        type: jsPsychCallFunction,
        func: function() {
          if (window.ProgressAPI && window.ProgressAPI.write) {
            window.ProgressAPI.write('nback', SUBJECT_ID, {
              lastCompletedBlockIdx: blockIdx,
              totalBlocks: NBACK_TOTAL_BLOCKS,
              blockOrder: ['B1','B2','B3'],
              paradigmState: {
                blockSummaries: JSON.parse(JSON.stringify(blockSummaries)),
                b3Duration: b3Duration,
              },
            });
            window.__currentBlockIdx = blockIdx + 1;
          }
        },
      };
    }

    // 每个block的正式试次数（用于 block 内进度显示）
    const b1MainCount = b1Rows.filter(r => (r.phase || '').trim().toLowerCase() === 'main' && r.cond !== 'warmup').length;
    const b2MainCount = b2Rows.filter(r => (r.phase || '').trim().toLowerCase() === 'main' && r.cond !== 'warmup').length;
    const b3MainCount = b3Rows.filter(r => (r.phase || '').trim().toLowerCase() === 'main' && r.cond !== 'warmup').length;

    // ===== B1 — Voice-guided instruction (逐句播放) =====
    const AUDIO_BASE = '../../audio/nback';
    // F4: B1 仅在 START_BLOCK<=0 时推入 timeline
    const b1VoiceTrial = {
      type: jsPsychCallFunction,
      async: true,
      func: async function(done) {
        await VoiceGuide.show({
          // 2026-04-13 戴敬力最终版 (基于朝琮 7 句 + 加结尾 s08, 去掉例子避免老人钻细节)
          image: 'img/block1.webp',
          btnRegion: { x: '80.1%', y: '4.9%', w: '15%', h: '8.2%' },
          buttonText: '开始练习',
          pauseBetween: 500,
          steps: [
            { region: { x: '5.2%', y: '38.4%', w: '19.8%', h: '36.5%' }, lines: [
              { audio: `${AUDIO_BASE}/b1_s01.mp3`, subtitle: '先看这张目标图，记住它的样子' },
            ] },
            { region: { x: '27.7%', y: '14.3%', w: '66.1%', h: '31.1%' }, lines: [
              { audio: `${AUDIO_BASE}/b1_s02.mp3`, subtitle: '后面会一张一张出现新的图片' },
            ] },
            { region: { x: '51.7%', y: '21.3%', w: '19%', h: '23.7%' }, lines: [
              { audio: `${AUDIO_BASE}/b1_s03.mp3`, subtitle: '每出现一张，都请和刚才的目标图比一比' },
            ] },
            { region: { x: '29.8%', y: '52.9%', w: '19.2%', h: '37.2%' }, lines: [
              { audio: `${AUDIO_BASE}/b1_s04.mp3`, subtitle: '如果和目标图一模一样，就点"一样"' },
            ] },
            { region: { x: '52.8%', y: '52.5%', w: '18.3%', h: '37.2%' }, lines: [
              { audio: `${AUDIO_BASE}/b1_s05.mp3`, subtitle: '如果还是同一张图，只是有一点小变化，就点"很像"' },
            ] },
            { region: { x: '73.2%', y: '52.1%', w: '18.9%', h: '37.4%' }, lines: [
              { audio: `${AUDIO_BASE}/b1_s06.mp3`, subtitle: '如果已经不一样了，就点"不一样"' },
            ] },
            { region: { x: '27.4%', y: '48.2%', w: '67.9%', h: '43.4%' }, lines: [
              { audio: `${AUDIO_BASE}/b1_s07.mp3`, subtitle: '按你的第一感觉来选，不用着急' },
            ] },
            { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
              { audio: `${AUDIO_BASE}/b1_s08.mp3`, subtitle: '明白了就点击开始练习' },
            ] },
          ],
        });
        done();
      },
    };
    // F4: 根据 START_BLOCK 决定 B1 是否推入
    if (START_BLOCK <= 0) {
      if (SKIP_INSTRUCTIONS && START_BLOCK === 0 /* 不应发生,防御 */) {
        timeline.push(buildShortReminder('第 1 部分', '继续留意<b>目标图</b>'));
      } else {
        timeline.push(b1VoiceTrial);
      }
      timeline.push(...buildB1(b1Rows));
      timeline.push(buildAttentionProbe(jsPsych, 'nback', 'after_B1'));
      timeline.push(makeWriteProgressTrial(0));
    }

    // ===== B2 — Voice-guided instruction =====
    const b2VoiceTrial = {
      type: jsPsychCallFunction,
      async: true,
      func: async function(done) {
        await VoiceGuide.show({
          // 2026-04-13 方案 A: 朝琮 10 句 + 戴敬力加回 2 个滑动窗口示例 (s04/s05 各一个红框,坐标用戴敬力精调版)
          image: 'img/block2.webp',
          btnRegion: { x: '80.1%', y: '4.9%', w: '15%', h: '8.2%' },
          buttonText: '开始练习',
          pauseBetween: 500,
          steps: [
            { region: { x: '5.1%', y: '14.3%', w: '22.8%', h: '80.1%' }, lines: [
              { audio: `${AUDIO_BASE}/b2_s01.mp3`, subtitle: '这次没有固定的目标图，图片会一张一张出现' },
            ] },
            { region: { x: '7.8%', y: '27.8%', w: '17%', h: '32%' }, lines: [
              { audio: `${AUDIO_BASE}/b2_s02.mp3`, subtitle: '第一张图出来的时候，先记住它' },
            ] },
            { region: { x: '30.3%', y: '16%', w: '61.2%', h: '40.5%' }, lines: [
              { audio: `${AUDIO_BASE}/b2_s03.mp3`, subtitle: '从第二张开始，每出来一张，都和前面那一张比一比' },
            ] },
            { region: { x: '33.2%', y: '29.1%', w: '36.7%', h: '26.6%' }, lines: [
              { audio: `${AUDIO_BASE}/b2_s04.mp3`, subtitle: '比如第二张和第一张比' },
            ] },
            { region: { x: '53.1%', y: '29%', w: '37%', h: '26.7%' }, lines: [
              { audio: `${AUDIO_BASE}/b2_s05.mp3`, subtitle: '第三张和第二张比' },
            ] },
            { region: { x: '36.5%', y: '66.9%', w: '51.1%', h: '6%' }, lines: [
              { audio: `${AUDIO_BASE}/b2_s06.mp3`, subtitle: '如果和前一张一模一样，就点"一样"' },
            ] },
            { region: { x: '36.7%', y: '73.8%', w: '50.8%', h: '6.3%' }, lines: [
              { audio: `${AUDIO_BASE}/b2_s07.mp3`, subtitle: '如果还是很像，只是有一点变化，就点"很像"' },
            ] },
            { region: { x: '36.8%', y: '80.6%', w: '51%', h: '6.4%' }, lines: [
              { audio: `${AUDIO_BASE}/b2_s08.mp3`, subtitle: '如果已经不一样了，就点"不一样"' },
            ] },
            { region: { x: '32%', y: '27.6%', w: '58.8%', h: '34.1%' }, lines: [
              { audio: `${AUDIO_BASE}/b2_s09.mp3`, subtitle: '每次只和紧挨着前面的那一张比，不用去想更早的图片' },
            ] },
            { region: { x: '34.5%', y: '59.2%', w: '56.5%', h: '31.9%' }, lines: [
              { audio: `${AUDIO_BASE}/b2_s10.mp3`, subtitle: '按你的第一感觉来选，不用着急' },
            ] },
            { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
              { audio: `${AUDIO_BASE}/b2_s11.mp3`, subtitle: '明白了就点击开始练习' },
            ] },
          ],
        });
        done();
      },
    };
    // F4: B2 根据 START_BLOCK 推入
    if (START_BLOCK <= 1) {
      if (SKIP_INSTRUCTIONS && START_BLOCK === 1) {
        timeline.push(buildShortReminder('第 2 部分', '继续留意<b>每张图</b>和<b>前一张</b>是否相同'));
      } else {
        timeline.push(b2VoiceTrial);
      }
      timeline.push(...buildB2(b2Rows));
      timeline.push(buildAttentionProbe(jsPsych, 'nback', 'after_B2'));
      timeline.push(restPage());
      timeline.push(makeWriteProgressTrial(1));
    }

    // ===== B3 — Voice-guided instruction =====
    const b3VoiceTrial = {
      type: jsPsychCallFunction,
      async: true,
      func: async function(done) {
        await VoiceGuide.show({
          // 2026-04-13 朝琮 + 戴敬力精调版 (用 chaocong 标注站拖过的坐标)
          image: 'img/block3.webp',
          btnRegion: { x: '80.1%', y: '4.9%', w: '15%', h: '8.2%' },
          buttonText: '开始练习',
          pauseBetween: 500,
          steps: [
            { region: { x: '5.2%', y: '14.5%', w: '15.9%', h: '52.5%' }, lines: [
              { audio: `${AUDIO_BASE}/b3_s01.mp3`, subtitle: '先看这张带橙色边框、写着"提示"的图，这就是提示图' },
            ] },
            { region: { x: '25.8%', y: '30.3%', w: '39.4%', h: '23.6%' }, lines: [
              { audio: `${AUDIO_BASE}/b3_s02.mp3`, subtitle: '后面图片会一张一张出现，前面先只看，不用按按钮' },
            ] },
            { region: { x: '65.3%', y: '29.7%', w: '16.2%', h: '24.4%' }, lines: [
              { audio: `${AUDIO_BASE}/b3_s03.mp3`, subtitle: '当提示图一出现，请马上想一想，它前面那一张是什么' },
            ] },
            { region: { x: '46.8%', y: '55.9%', w: '49.1%', h: '27.8%' }, lines: [
              { audio: `${AUDIO_BASE}/b3_s04.mp3?v=20260423`, subtitle: '这时屏幕会出现三张小图，请从里面选出提示图的前一张，也就是倒数第二张' },
            ] },
            { region: { x: '51.7%', y: '33.8%', w: '13.8%', h: '18.3%' }, lines: [
              { audio: `${AUDIO_BASE}/b3_s05.mp3?v=20260423`, subtitle: '注意，不是选提示图本身，也不是选更早的图，只选倒数第二张' },
            ] },
            { region: { x: '50.2%', y: '64.5%', w: '42.2%', h: '24.7%' }, lines: [
              { audio: `${AUDIO_BASE}/b3_s06.mp3`, subtitle: '想一想再选，选你觉得最像的那一张' },
            ] },
            { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
              { audio: `${AUDIO_BASE}/b3_s07.mp3`, subtitle: '明白了就点击开始练习' },
            ] },
          ],
        });
        done();
      },
    };
    // F4: B3 根据 START_BLOCK 推入
    if (START_BLOCK <= 2) {
      if (SKIP_INSTRUCTIONS && START_BLOCK === 2) {
        timeline.push(buildShortReminder('第 3 部分', '继续留意<b>提示图</b>前一张'));
      } else {
        timeline.push(b3VoiceTrial);
      }
      timeline.push(...buildB3(b3Rows));
      timeline.push(buildAttentionProbe(jsPsych, 'nback', 'after_B3'));
      timeline.push(makeWriteProgressTrial(2));
    }

    // ===== B4 (conditional) =====
    // Gate check
    timeline.push({
      type: jsPsychCallFunction,
      func: function() {
        const b2Acc = blockSummaries.B2 ? blockSummaries.B2.accuracy : 0;
        const b3Acc = blockSummaries.B3 ? blockSummaries.B3.accuracy : 0;
        const b3Dur = b3Duration;

        const gateOk = b2Acc >= GATE_ACC && b3Acc >= GATE_ACC && b3Dur <= GATE_TIME_S;
        window._nback_b4_gate = gateOk;

        if (!gateOk) {
          const reasons = [];
          if (b2Acc < GATE_ACC) reasons.push(`B2正确率${Math.round(b2Acc*100)}%`);
          if (b3Acc < GATE_ACC) reasons.push(`B3正确率${Math.round(b3Acc*100)}%`);
          if (b3Dur > GATE_TIME_S) reasons.push(`B3用时${Math.round(b3Dur)}秒`);
          blockSummaries.B4 = { status: 'skipped', reason: reasons.join('; ') };
        }
      },
    });

    // B4 — Voice-guided instruction
    // 2026-04-16 戴敬力终版,8 步语音 / 10 句音频(s1+s2 各双句)
    // 用户用编辑器拖完坐标后回填 (region 数值取自 region-editor 输出)
    // 音频 b4_s01..b4_s10 需在 generate_nback_audio.py 改 10 条新文本并重跑 TTS
    const b4VoiceTrial = {
      type: jsPsychCallFunction,
      async: true,
      func: async function(done) {
        await VoiceGuide.show({
          image: 'img/block4.webp',
          btnRegion: { x: '79.3%', y: '3.5%', w: '14.8%', h: '6.2%' },
          buttonText: '开始练习',
          pauseBetween: 500,
          steps: [
            // step 1 — 左侧"第1步"面板 (2 句)
            { region: { x: '3.2%', y: '8.8%', w: '22%', h: '82%' }, lines: [
              { audio: `${AUDIO_BASE}/b4_s01.mp3?v=20260416c`, subtitle: '接下来会一张一张出现图片' },
              { audio: `${AUDIO_BASE}/b4_s02.mp3?v=20260416c`, subtitle: '请观察前两张图' },
            ] },
            // step 2 — 右侧"第2步"标题+说明 (2 句)
            { region: { x: '25%', y: '11.5%', w: '67.3%', h: '39.2%' }, lines: [
              { audio: `${AUDIO_BASE}/b4_s03.mp3?v=20260416c`, subtitle: '从第三张开始，每张图都要和上上张比' },
              { audio: `${AUDIO_BASE}/b4_s04.mp3?v=20260416c`, subtitle: '图片相同时需要按下按钮' },
            ] },
            // step 3 — 双框: 第3张 + 第1张
            { regions: [
                { x: '54%',   y: '34%',   w: '10%',   h: '14%'   },
                { x: '27.4%', y: '34.6%', w: '11.4%', h: '13.4%' },
              ], lines: [
              { audio: `${AUDIO_BASE}/b4_s05.mp3?v=20260416c`, subtitle: '比如当第3张出来时，就回忆上上张是什么样' },
            ] },
            // step 4 — "按这里"按钮区
            { region: { x: '32.8%', y: '63.3%', w: '22.1%', h: '21.1%' }, lines: [
              { audio: `${AUDIO_BASE}/b4_s06.mp3?v=20260416c`, subtitle: '一模一样，就点"按这里"按钮' },
            ] },
            // step 5 — 双框: 第4张 + 第2张
            { regions: [
                { x: '66.8%', y: '34.6%', w: '12%',   h: '13.1%' },
                { x: '40.3%', y: '34.2%', w: '12.1%', h: '14.3%' },
              ], lines: [
              { audio: `${AUDIO_BASE}/b4_s07.mp3?v=20260416c`, subtitle: '第4张出来，再回忆上上张' },
            ] },
            // step 6 — 顶部"图片不同"区
            { region: { x: '40.4%', y: '22.6%', w: '38.9%', h: '26.4%' }, lines: [
              { audio: `${AUDIO_BASE}/b4_s08.mp3?v=20260416c`, subtitle: '不一样的话什么都不做，等下一张' },
            ] },
            // step 7 — 双框: 第5张 + 第3张
            { regions: [
                { x: '80.1%', y: '34.3%', w: '11.3%', h: '13.8%' },
                { x: '53.7%', y: '34.6%', w: '11.5%', h: '13.2%' },
              ], lines: [
              { audio: `${AUDIO_BASE}/b4_s09.mp3?v=20260416c`, subtitle: '第5张同样，跟上上张比' },
            ] },
            // step 8 — 继续按钮
            { region: { x: '78.5%', y: '2.8%', w: '16.3%', h: '7.6%' }, lines: [
              { audio: `${AUDIO_BASE}/b4_s10.mp3?v=20260416c`, subtitle: '明白了就点击开始练习' },
            ] },
          ],
        });
        done();
      },
    };

    // B4 conditional node
    const b4Timeline = [
      b4VoiceTrial,
      blockInstrPage('B4'),
      ...buildB4(b4Rows),
    ];

    timeline.push({
      timeline: b4Timeline,
      conditional_function: function() {
        return window._nback_b4_gate === true;
      },
    });

    // Skip message if B4 not run
    timeline.push({
      timeline: [{
        type: jsPsychHtmlButtonResponse,
        stimulus: `<div class="instruction-page">
          <div class="instruction-body">请稍作休息，即将结束。</div>
        </div>`,
        choices: ['继续'],
        button_html: (c) => `<button class="jspsych-btn" style="margin-top:20px;">${c}</button>`,
      }],
      conditional_function: function() {
        return window._nback_b4_gate !== true;
      },
    });

    // 清除进度计数
    timeline.push({ type: jsPsychCallFunction, func: function() {
      var el = document.getElementById('_nback_progress');
      if (el) el.remove();
    }});

    // ===== Save Data =====
    let _dataSaved = false;
    timeline.push({
      type: jsPsychCallFunction,
      async: true,
      func: async function(done) {
        if (_dataSaved) { done(); return; }
        _dataSaved = true;
        const ts = formatTimestamp();
        const csvFn = `Nback_${SUBJECT_ID}_${ts}.csv`;
        let csvData = generateCSV();
        // F4 (2026-04-19): 续写场景合并上次 CSV
        if (window.ProgressAPI && window.ProgressAPI.getPrior) {
          const priorCSV = window.ProgressAPI.getPrior('nback', SUBJECT_ID);
          if (priorCSV) {
            csvData = window.ProgressAPI.merge(priorCSV, csvData);
            console.log('[nback] merged prior CSV,final rows:', csvData.split('\n').length - 2);
          }
        }
        const jsonFn = `Nback_${SUBJECT_ID}_${ts}_summary.json`;
        const jsonData = generateSummaryJSON();
        await trySaveData(csvFn, csvData, jsonFn, jsonData);
        if (typeof LocalPack !== 'undefined') {
          LocalPack.add(csvFn, csvData);
          LocalPack.add(jsonFn, jsonData);
        }
        checkpoint.clear(); // final save succeeded, remove checkpoint
        // Stop camera recording and save video
        try { await ParadigmCamera.stopAndSave(); } catch (e) { console.warn('[nback] camera stop skipped:', e.message); }
        done();
      },
    });

    // (End screen is handled by showEndScreen in on_finish callback)

    // Camera recording (optional — graceful skip if not enabled)
    try { await ParadigmCamera.init('nback', SUBJECT_ID); } catch (e) { console.warn('[nback] camera init skipped:', e.message); }

    // Run
    jsPsych.run(timeline);
  }

  // ==================== Init ====================
  const jsPsych = initJsPsych({
    display_element: 'jspsych-target',
    on_finish: function() {
      console.log('N-back experiment complete');
      showEndScreen('nback', SUBJECT_ID);
    },
  });

  main();

})();
