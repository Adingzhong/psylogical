/**
 * Flanker Task (Web Battery)
 * --------------------------------------------------
 * Port of flanker_psychopy.py to jsPsych 8.
 *
 * Design:
 *   5-arrow display, judge centre arrow direction (left/right buttons).
 *   Conditions: Congruent / Incongruent / Neutral  x  Left / Right  + Popout variants
 *   Practice: 6 trials (<70% accuracy retry, max 3 rounds)
 *   Formal: 2 blocks x 24 trials, focus-rating between blocks (1-9)
 *   Timing: fixation 500ms -> stimulus (max 2000ms) -> blank 750ms
 */

/* ================================================================
   Checkpoint: incremental data saving (inline, no module dependency)
   Non-blocking — save failures never affect experiment flow.
   ================================================================ */

const _checkpoint = {
  _saving: false,
  _lastTime: 0,
  _pending: false,
  _timer: null,
  _MIN_INTERVAL: 5000,
  _paradigm: '',
  _sid: '',
  _fn: null,

  init: function (paradigm, sid, getDataFn) {
    this._paradigm = paradigm;
    this._sid = sid;
    this._fn = getDataFn;
  },

  _doSave: function () {
    if (this._saving || !this._fn) { this._pending = true; return; }
    var csv = this._fn();
    if (!csv) return;
    this._saving = true;
    this._lastTime = Date.now();
    var self = this;
    var filename = this._paradigm + '_' + this._sid + '_checkpoint.csv';
    var lsKey = 'checkpoint_' + this._paradigm + '_' + this._sid;
    try { localStorage.setItem(lsKey, csv); } catch (e) { /* ignore */ }
    fetch(window.location.origin + '/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paradigm: self._paradigm, subject_id: self._sid, filename: filename, content: csv }),
    }).catch(function () {}).finally(function () {
      self._saving = false;
      if (self._pending) { self._pending = false; self._doSave(); }
    });
  },

  /** Throttled save — safe to call after every trial (5s min interval) */
  save: function () {
    var elapsed = Date.now() - this._lastTime;
    if (elapsed < this._MIN_INTERVAL) {
      if (!this._pending) {
        this._pending = true;
        var self = this;
        clearTimeout(this._timer);
        this._timer = setTimeout(function () {
          if (self._pending) { self._pending = false; self._doSave(); }
        }, this._MIN_INTERVAL - elapsed);
      }
      return;
    }
    this._doSave();
  },

  /** Immediate save — use at block boundaries */
  forceSave: function () {
    clearTimeout(this._timer);
    this._pending = false;
    this._doSave();
  },

  /** Clear checkpoint data (experiment completed normally) */
  clear: function () {
    clearTimeout(this._timer);
    try { localStorage.removeItem('checkpoint_' + this._paradigm + '_' + this._sid); } catch (e) { /* ignore */ }
  },
};

/* ================================================================
   Config & Constants
   ================================================================ */

const STIMULI_BASE = '../../stimuli/flanker/';

const TIMING = {
  preFixationBlank: 1000,
  fixation: 500,
  // maxResponse 4000ms — 依据:Krueger CE et al. (2009). Neurology 73(5):349-355
  //   (中科院医学 1 区, IF 9.9, 对早期额颞痴呆 FTD 患者施测 Flanker)
  //   原文 verbatim: "The stimuli were presented until the subject pressed a key
  //   (with a maximum exposure of 4 seconds)."
  // 说明:Flanker 效应 = RT_incongruent − RT_congruent(差值分数),绝对 RT 不影响效应。
  //   老年 motor slowing 是已知混淆,限时太短反而截断慢响应者数据,加重混淆。
  //   另:CSV 输出增加 rt_over_2s / rt_over_3s 标志列,供后处理按任意阈值筛选。
  maxResponse: 4000,
  postResponseBlank: 750,
  feedbackDuration: 1500,
  countdownStep: 1000,
};

const PRACTICE_TRIALS_N = 6;
const PRACTICE_PASS_ACCURACY = 0.70;
const MAX_PRACTICE_ROUNDS = 3;
const FORMAL_BLOCKS = 2;
const TRIALS_PER_BLOCK = 24;

/* Image path resolution (mirrors resolve_trial_image_path from Python) */
const IMAGE_MAP = {
  Congruent: {
    normal: { left: 'congruent/z.webp', right: 'congruent/y.webp' },
    popout: {
      left: { '1': 'congruent-pop/d4.webp', '2': 'congruent-pop/d3.webp', '3': 'congruent-pop/b6.webp', '4': 'congruent-pop/d5.webp', '5': 'congruent-pop/d6.webp' },
      right: { '1': 'congruent-pop/5a.webp', '2': 'congruent-pop/4a.webp', '3': 'congruent-pop/3a.webp', '4': 'congruent-pop/6a.webp', '5': 'congruent-pop/7a.webp' },
    },
  },
  Incongruent: {
    normal: { left: 'incongruent/a2.webp', right: 'incongruent/a1.webp' },
    popout: {
      left: { '1': 'incongruent-pop/Z1.webp', '2': 'incongruent-pop/Z2.webp', '3': 'incongruent-pop/Z3.webp', '4': 'incongruent-pop/Z4.webp', '5': 'incongruent-pop/Z5.webp' },
      right: { '1': 'incongruent-pop/Y1.webp', '2': 'incongruent-pop/Y2.webp', '3': 'incongruent-pop/Y3.webp', '4': 'incongruent-pop/Y4.webp', '5': 'incongruent-pop/Y5.webp' },
    },
  },
  Neutral: {
    normal: { left: 'neutral/c2.webp', right: 'neutral/c1.webp' },
    popout: { left: { '3': 'neutral-pop/c4.webp' }, right: { '3': 'neutral-pop/c3.webp' } },
  },
};

function resolveImagePath(trialType, targetDir, isPopout, popoutPosition) {
  const entry = IMAGE_MAP[trialType];
  if (!isPopout) return STIMULI_BASE + entry.normal[targetDir];
  return STIMULI_BASE + entry.popout[targetDir][popoutPosition];
}

/* Collect all image paths for preloading */
function getAllImagePaths() {
  const paths = [];
  for (const type of ['Congruent', 'Incongruent', 'Neutral']) {
    const e = IMAGE_MAP[type];
    paths.push(STIMULI_BASE + e.normal.left);
    paths.push(STIMULI_BASE + e.normal.right);
    for (const dir of ['left', 'right']) {
      for (const pos of Object.keys(e.popout[dir])) {
        paths.push(STIMULI_BASE + e.popout[dir][pos]);
      }
    }
  }
  return paths;
}

/* ================================================================
   URL Params
   ================================================================ */

function getUrlParams() {
  const p = new URLSearchParams(window.location.search);
  return {
    subjectId: p.get('sid') || '',
    session: p.get('session') || 'S001',
  };
}

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

/* ================================================================
   Trial Generation
   ================================================================ */

function getFlankerDirection(trialType, targetDir) {
  if (trialType === 'Congruent') return targetDir;
  if (trialType === 'Incongruent') return targetDir === 'left' ? 'right' : 'left';
  return 'neutral';
}

function createTrial(index, isPractice, trialType, targetDir, isPopout, popoutType, popoutPosition, blockIndex, practiceRound, phaseName) {
  return {
    trial_index: index,
    is_practice: isPractice,
    trial_type: trialType,
    is_popout: isPopout,
    popout_type: popoutType,
    popout_position: popoutPosition,
    target_dir: targetDir,
    flanker_dir: getFlankerDirection(trialType, targetDir),
    block_index: blockIndex,
    practice_round: practiceRound,
    phase_name: phaseName,
    image_path: resolveImagePath(trialType, targetDir, isPopout, popoutPosition),
  };
}

/* Shuffle with constraint: no more than 3 consecutive same trial_type or target_dir */
function hasValidRuns(arr, attr, maxRun) {
  maxRun = maxRun || 3;
  let run = 1;
  for (let i = 1; i < arr.length; i++) {
    if (arr[i][attr] === arr[i - 1][attr]) {
      run++;
      if (run > maxRun) return false;
    } else {
      run = 1;
    }
  }
  return true;
}

function shuffleArray(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function shuffleWithConstraints(trials, maxAttempts) {
  maxAttempts = maxAttempts || 10000;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const shuffled = shuffleArray(trials);
    if (hasValidRuns(shuffled, 'trial_type') && hasValidRuns(shuffled, 'target_dir')) {
      return shuffled;
    }
  }
  // Fallback: return random shuffle anyway
  return shuffleArray(trials);
}

/* Practice trial templates (mirrors Python round_templates) */
const PRACTICE_TEMPLATES = {
  1: [
    ['Congruent', 'left', false, 'na', 'NA'],
    ['Congruent', 'right', true, 'target', '3'],
    ['Incongruent', 'right', false, 'na', 'NA'],
    ['Incongruent', 'left', true, 'flanker', '4'],
    ['Neutral', 'left', false, 'na', 'NA'],
    ['Neutral', 'right', true, 'target', '3'],
  ],
  2: [
    ['Congruent', 'right', false, 'na', 'NA'],
    ['Congruent', 'left', true, 'flanker', '1'],
    ['Incongruent', 'left', false, 'na', 'NA'],
    ['Incongruent', 'right', true, 'target', '3'],
    ['Neutral', 'right', false, 'na', 'NA'],
    ['Neutral', 'left', true, 'target', '3'],
  ],
  3: [
    ['Congruent', 'left', false, 'na', 'NA'],
    ['Congruent', 'right', true, 'flanker', '5'],
    ['Incongruent', 'right', false, 'na', 'NA'],
    ['Incongruent', 'left', true, 'target', '3'],
    ['Neutral', 'right', false, 'na', 'NA'],
    ['Neutral', 'left', true, 'target', '3'],
  ],
};

function buildPracticeTrials(practiceRound) {
  const roundIndex = ((practiceRound - 1) % MAX_PRACTICE_ROUNDS) + 1;
  const template = PRACTICE_TEMPLATES[roundIndex];
  const trials = template.map(function (t, i) {
    return createTrial(i + 1, true, t[0], t[1], t[2], t[3], t[4], 0, practiceRound, 'practice');
  });
  const shuffled = shuffleWithConstraints(trials);
  shuffled.forEach(function (t, i) { t.trial_index = i + 1; });
  return shuffled;
}

function sampleFromArray(arr, n) {
  const shuffled = shuffleArray(arr);
  return shuffled.slice(0, n);
}

function buildFormalBlocks() {
  const congruentLeftPos = sampleFromArray([1, 2], 2);
  const congruentRightPos = sampleFromArray([4, 5], 2);
  const incongruentLeftPos = sampleFromArray([4, 5], 2);
  const incongruentRightPos = sampleFromArray([1, 2], 2);

  const blocks = [];
  let globalIdx = 1;
  let presentedIdx = 1;

  for (let blockIdx = 0; blockIdx < 2; blockIdx++) {
    const block = [];
    const currentBlock = blockIdx + 1;

    // Congruent: 2 left normal, 2 right normal
    for (let i = 0; i < 2; i++) {
      block.push(createTrial(globalIdx++, false, 'Congruent', 'left', false, 'na', 'NA', currentBlock, 0, 'formal'));
    }
    for (let i = 0; i < 2; i++) {
      block.push(createTrial(globalIdx++, false, 'Congruent', 'right', false, 'na', 'NA', currentBlock, 0, 'formal'));
    }
    // Congruent popout: target at 3
    block.push(createTrial(globalIdx++, false, 'Congruent', 'left', true, 'target', '3', currentBlock, 0, 'formal'));
    block.push(createTrial(globalIdx++, false, 'Congruent', 'right', true, 'target', '3', currentBlock, 0, 'formal'));
    // Congruent popout: flanker
    block.push(createTrial(globalIdx++, false, 'Congruent', 'left', true, 'flanker', String(congruentLeftPos[blockIdx]), currentBlock, 0, 'formal'));
    block.push(createTrial(globalIdx++, false, 'Congruent', 'right', true, 'flanker', String(congruentRightPos[blockIdx]), currentBlock, 0, 'formal'));

    // Incongruent: 2 left normal, 2 right normal
    for (let i = 0; i < 2; i++) {
      block.push(createTrial(globalIdx++, false, 'Incongruent', 'left', false, 'na', 'NA', currentBlock, 0, 'formal'));
    }
    for (let i = 0; i < 2; i++) {
      block.push(createTrial(globalIdx++, false, 'Incongruent', 'right', false, 'na', 'NA', currentBlock, 0, 'formal'));
    }
    block.push(createTrial(globalIdx++, false, 'Incongruent', 'left', true, 'target', '3', currentBlock, 0, 'formal'));
    block.push(createTrial(globalIdx++, false, 'Incongruent', 'right', true, 'target', '3', currentBlock, 0, 'formal'));
    block.push(createTrial(globalIdx++, false, 'Incongruent', 'left', true, 'flanker', String(incongruentLeftPos[blockIdx]), currentBlock, 0, 'formal'));
    block.push(createTrial(globalIdx++, false, 'Incongruent', 'right', true, 'flanker', String(incongruentRightPos[blockIdx]), currentBlock, 0, 'formal'));

    // Neutral: 2 left normal, 2 right normal, 2 left popout, 2 right popout
    for (let i = 0; i < 2; i++) {
      block.push(createTrial(globalIdx++, false, 'Neutral', 'left', false, 'na', 'NA', currentBlock, 0, 'formal'));
    }
    for (let i = 0; i < 2; i++) {
      block.push(createTrial(globalIdx++, false, 'Neutral', 'right', false, 'na', 'NA', currentBlock, 0, 'formal'));
    }
    for (let i = 0; i < 2; i++) {
      block.push(createTrial(globalIdx++, false, 'Neutral', 'left', true, 'target', '3', currentBlock, 0, 'formal'));
    }
    for (let i = 0; i < 2; i++) {
      block.push(createTrial(globalIdx++, false, 'Neutral', 'right', true, 'target', '3', currentBlock, 0, 'formal'));
    }

    // 24 trials per block total
    const shuffled = shuffleWithConstraints(block);
    shuffled.forEach(function (t, i) { t.trial_index = presentedIdx + i; });
    presentedIdx += shuffled.length;
    blocks.push(shuffled);
  }
  return blocks;
}

/* ================================================================
   Data Collection
   ================================================================ */

const trialRecords = [];
const ratingRecords = [];
let globalTrialIndex = 1;

function recordTrial(spec, response, rt, isTimeout) {
  const accuracy = isTimeout ? 0 : (response === spec.target_dir ? 1 : 0);
  const record = {
    subject_id: subjectId,
    trial_index: spec.trial_index,
    trial_index_global: globalTrialIndex++,
    is_practice: spec.is_practice,
    trial_type: spec.trial_type,
    is_popout: spec.is_popout,
    popout_type: spec.popout_type,
    popout_position: spec.popout_position,
    target_dir: spec.target_dir,
    flanker_dir: spec.flanker_dir,
    block_index: spec.block_index,
    practice_round: spec.practice_round,
    phase_name: spec.phase_name,
    keyPressed: response || 'none',
    response_key: response || 'none',
    accuracy: accuracy,
    reaction_time: rt !== null ? Math.round(rt * 1000) / 1000 : '',
    rt_ms: rt !== null ? Math.round(rt) : '',
    timeout: isTimeout,
    is_anticipatory: (rt !== null && rt < 200) ? 1 : 0,
    // rt_over_X 标志:供后处理按阈值筛选(采集时不截断数据)
    // timeout 情况算 1(>任何阈值);非 timeout 按 rt_ms 比较
    rt_over_2s: isTimeout || (rt !== null && rt > 2000) ? 1 : 0,
    rt_over_3s: isTimeout || (rt !== null && rt > 3000) ? 1 : 0,
  };
  trialRecords.push(record);
  return record;
}

function recordRating(blockIndex, rating) {
  ratingRecords.push({
    subject_id: subjectId,
    block_index: blockIndex,
    focus_rating: rating,
    rating_ts: new Date().toISOString(),
  });
}

/* ================================================================
   CSV Export
   ================================================================ */

function generateTrialCSV() {
  const BOM = '\uFEFF';
  const fields = [
    'subject_id', 'trial_index', 'trial_index_global', 'is_practice', 'trial_type',
    'is_popout', 'popout_type', 'popout_position', 'target_dir', 'flanker_dir',
    'block_index', 'practice_round', 'phase_name', 'keyPressed', 'response_key',
    'accuracy', 'reaction_time', 'rt_ms', 'timeout', 'is_anticipatory',
    'rt_over_2s', 'rt_over_3s',
  ];
  let csv = BOM + fields.join(',') + '\n';
  trialRecords.forEach(function (r) {
    csv += fields.map(function (f) {
      const v = r[f];
      if (v === undefined || v === null) return '';
      return String(v);
    }).join(',') + '\n';
  });
  return csv;
}

function generateRatingCSV() {
  // 从 lib/attention-probe.js 的全局收集器读,不依赖从未调用过的 recordRating
  const BOM = '\uFEFF';
  const fields = ['subject_id', 'paradigm', 'position', 'focus_rating', 'rt_ms', 'rating_ts'];
  let csv = BOM + fields.join(',') + '\n';
  const probes = (window._attentionProbeData || []).filter(function (p) { return p.paradigm === 'flanker'; });
  probes.forEach(function (p) {
    csv += [subjectId, p.paradigm, p.position, p.rating, p.rt_ms, p.timestamp].join(',') + '\n';
  });
  return csv;
}

function downloadCSV(content, filename) {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

let _dataSaved = false;

async function saveData() {
  if (_dataSaved) return;
  _dataSaved = true;

  const ts = timestamp();
  const trialFilename = `Flanker_${subjectId}_${ts}.csv`;
  const ratingFilename = `Flanker_${subjectId}_${ts}_ratings.csv`;
  const trialCSV = generateTrialCSV();
  const ratingCSV = generateRatingCSV();

  // Register files for local ZIP packing
  if (typeof LocalPack !== 'undefined') {
    LocalPack.add(trialFilename, trialCSV);
    LocalPack.add(ratingFilename, ratingCSV);
  }

  // Try server save first
  let serverOk = false;
  try {
    const resp = await safeFetch(window.location.origin + '/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paradigm: 'flanker', subject_id: subjectId, filename: trialFilename, content: trialCSV }),
    });
    if (!resp.ok) throw new Error('server error');
    const resp2 = await safeFetch(window.location.origin + '/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paradigm: 'flanker', subject_id: subjectId, filename: ratingFilename, content: ratingCSV }),
    });
    if (!resp2.ok) throw new Error('server error');
    serverOk = true;
  } catch (e) {
    // 数据已在LocalPack，ZIP统一打包。不再单独a.click()下载——Edge会拦截。
    console.warn('[Flanker] server save failed, LocalPack has backup:', e);
  }

  // localStorage backup — 服务器成功就清掉(防跨被试累积拖慢 localStorage),失败才留着兜底
  try {
    if (serverOk) {
      localStorage.removeItem('flanker_backup_' + subjectId);
    } else {
      localStorage.setItem('flanker_backup_' + subjectId, trialCSV);
    }
  } catch (e) { /* ignore */ }
}

/* ================================================================
   jsPsych Initialization
   ================================================================ */

const params = getUrlParams();
const subjectId = params.subjectId || 'TEST_' + Date.now();

/* Initialize checkpoint for incremental saving */
_checkpoint.init('flanker', subjectId, generateTrialCSV);

// Flanker: 指导语白底，试次阶段黑底（300ms 渐变过渡）
document.body.style.transition = 'background 0.5s ease, color 0.5s ease';
function setTrialBackground(on) {
  document.body.style.background = on ? '#000000' : '#FFFFFF';
  document.body.style.color = on ? '#FFFFFF' : '#1A1A2E';
}

const jsPsych = initJsPsych({
  display_element: 'jspsych-target',
  on_finish: function () {
    // saveData() is awaited in the timeline call-function trial — not here
    showEndScreen('flanker', subjectId);
  },
});

/* ================================================================
   Instruction HTML builders (elderly-friendly redesign)
   ================================================================ */

/**
 * Build a warm, high-contrast instruction page.
 * Design principles:
 *   - White bg, dark text, blue accents (already from common.css)
 *   - Title 52px bold, body 38px, generous line-height
 *   - Max 900px width, centered
 *   - Each page conveys ONE core message
 *   - Large "继续" button at bottom
 */
function makeInstructionHTML(title, body, hint, pageNum, totalPages) {
  if (hint === undefined || hint === null) hint = '';
  var hintHTML = hint ? '<div style="margin-top:14px;font-size:24px;color:var(--text-secondary);font-style:italic">' + hint + '</div>' : '';
  var progressHTML = '';
  if (pageNum && totalPages) {
    progressHTML = '<div style="position:fixed;top:12px;right:24px;color:rgba(0,0,0,0.4);font-size:36px;font-family:var(--font);">' + pageNum + ' / ' + totalPages + '</div>';
  }
  return progressHTML + '<div class="instr-page">' +
    '<div class="instr-title">' + title + '</div>' +
    '<div class="instr-body">' + body + '</div>' +
    hintHTML +
    '</div>';
}

/* Helper: wrap a stimulus image path in a styled img tag for instructions */
function instrImg(src, width, label) {
  width = width || '320px';
  var labelHTML = label ? '<div style="font-size:24px;color:var(--primary);margin-top:6px;font-weight:600">' + label + '</div>' : '';
  return '<div style="display:inline-block;text-align:center;vertical-align:middle;margin:8px 12px">' +
    '<img src="' + src + '" style="width:' + width + ';height:auto;border-radius:8px;border:2px solid var(--border);background:#222">' +
    labelHTML +
    '</div>';
}

/* Helper: build a numbered step row with text + optional image */
function instrStep(num, heading, detail, imgHTML) {
  imgHTML = imgHTML || '';
  return '<div style="display:flex;align-items:center;gap:18px;margin:12px 0;text-align:left;max-width:900px;width:100%">' +
    '<div style="flex-shrink:0;width:48px;height:48px;border-radius:50%;background:var(--primary);color:#fff;font-size:26px;font-weight:bold;display:flex;align-items:center;justify-content:center">' + num + '</div>' +
    '<div style="flex:1">' +
    '<div style="font-size:30px;font-weight:bold;color:var(--text)">' + heading + '</div>' +
    (detail ? '<div style="font-size:24px;color:var(--text-secondary);margin-top:3px">' + detail + '</div>' : '') +
    '</div>' +
    (imgHTML ? '<div style="flex-shrink:0">' + imgHTML + '</div>' : '') +
    '</div>';
}

function instructionTrial(title, body, hint, pageNum, totalPages) {
  return {
    type: jsPsychHtmlButtonResponse,
    stimulus: makeInstructionHTML(title, body, hint, pageNum, totalPages),
    choices: ['继续'],
    button_html: function (choice) {
      return '<button class="jspsych-btn instr-continue-btn">' + choice + '</button>';
    },
  };
}

/* ================================================================
   Build Timeline
   ================================================================ */

const timeline = [];

/* --- Voice-guided instruction audio base --- */
const AUDIO_BASE = '../../audio/flanker';

/* --- Preload 图片 + 音频 — 必须等所有 audio 都下完才进 instruction,
       否则 VoiceGuide 播放时会卡顿(慢网/首次访问 SW 缓存空) --- */
var _flankerAudioFiles = [];
for (var _ai = 1; _ai <= 10; _ai++) _flankerAudioFiles.push(AUDIO_BASE + '/s' + String(_ai).padStart(2,'0') + '.mp3');
_flankerAudioFiles.push(AUDIO_BASE + '/t3_s01.mp3', AUDIO_BASE + '/t3_s02.mp3');

timeline.push({
  type: jsPsychPreload,
  images: getAllImagePaths().concat(['img/rules.webp']),
  audio: _flankerAudioFiles,
  show_progress_bar: true,
  message: '<p style="font-size:28px;font-family:var(--font)">正在加载，请稍候...</p>',
  continue_after_error: true,
});
// 2026-04-19: 预加载后检查失败资源,有失败则弹框告警主试
timeline.push({
  type: jsPsychCallFunction, async: true,
  func: function(done) {
    if (typeof TouchHardening !== 'undefined' && TouchHardening.checkLoadFailures) {
      TouchHardening.checkLoadFailures({ paradigmName: 'Flanker' }).then(function() { done(); });
    } else { done(); }
  },
});

timeline.push({
  type: jsPsychCallFunction,
  async: true,
  func: async function(done) {
    await VoiceGuide.show({
      image: 'img/rules.webp',
      btnRegion: { x: '80.1%', y: '4.9%', w: '15%', h: '8.2%' },
      buttonText: '开始练习',
      pauseBetween: 500,
      steps: [
        { region: { x: '6.4%', y: '15.6%', w: '56.1%', h: '13.7%' }, lines: [
          { audio: `${AUDIO_BASE}/s01.mp3`, subtitle: '接下来做箭头判断' },
          { audio: `${AUDIO_BASE}/s02.mp3`, subtitle: '屏幕上会出现一排箭头' },
        ] },
        { region: { x: '43.3%', y: '16.1%', w: '11.4%', h: '12.3%' }, lines: [
          { audio: `${AUDIO_BASE}/s03.mp3`, subtitle: '圈出来的就是中间那个，您只看它' },
        ] },
        { region: { x: '8.8%', y: '59.4%', w: '22.7%', h: '29.9%' }, lines: [
          { audio: `${AUDIO_BASE}/s04.mp3`, subtitle: '中间箭头朝左，按左边按钮' },
        ] },
        { region: { x: '37.8%', y: '58.9%', w: '22.1%', h: '30.2%' }, lines: [
          { audio: `${AUDIO_BASE}/s05.mp3`, subtitle: '朝右，按右边按钮' },
        ] },
        { region: { x: '67%', y: '36.6%', w: '25.9%', h: '18.8%' }, lines: [
          { audio: `${AUDIO_BASE}/s06.mp3`, subtitle: '两侧的箭头方向不用管它' },
        ] },
        { region: { x: '67.2%', y: '61.2%', w: '25.9%', h: '19%' }, lines: [
          { audio: `${AUDIO_BASE}/s07.mp3`, subtitle: '有时候箭头会变颜色' },
          { audio: `${AUDIO_BASE}/s08.mp3`, subtitle: '也不用管，只看中间的方向' },
        ] },
        { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
          { audio: `${AUDIO_BASE}/s09.mp3`, subtitle: '明白了就点击开始练习' },
        ] },
      ],
    });
    done();
  },
});

/* (Pages 3-5 removed — all rules covered by VoiceGuide above) */

/* ================================================================
   Custom Trial Plugin (inline)
   ================================================================ */

/* Since jsPsych 8 button-response plugins reset the DOM each trial,
   we build a lightweight custom trial using html-keyboard-response
   with manual button handling for the stimulus phase. */

function buildFlankerTrialNode(spec, isPractice, trialNum, totalTrials) {
  const nodes = [];

  /* 1. Pre-fixation blank (黑底) */
  nodes.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div class="flanker-blank"></div>',
    choices: 'NO_KEYS',
    trial_duration: TIMING.preFixationBlank,
  });

  /* 2. Fixation cross (白色+号, 6vh, 黑底居中, 原版FIXATION_HEIGHT=0.06) */
  nodes.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div class="flanker-fixation">+</div>',
    choices: 'NO_KEYS',
    trial_duration: TIMING.fixation,
  });

  /* 3. Stimulus with response buttons */
  var progressHTML = '';
  if (trialNum && totalTrials) {
    var label = isPractice ? '练习' : '';
    progressHTML = '<div style="position:fixed;top:12px;right:24px;color:rgba(255,255,255,0.6);font-size:36px;font-family:var(--font);pointer-events:none;">' + label + ' ' + trialNum + ' / ' + totalTrials + '</div>';
  }
  nodes.push({
    type: jsPsychHtmlButtonResponse,
    stimulus: progressHTML + '<div class="flanker-stimulus"><img src="' + spec.image_path + '"></div>',
    on_start: function() {
      if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
        ParadigmCamera.addEvent('stimulus_onset', { trial_index: spec.trial_index, condition: spec.condition, image: spec.image_name, phase: spec.is_practice ? 'practice' : 'formal' });
      }
    },
    choices: ['左', '右'],
    button_html: function (choice, index) {
      var side = index === 0 ? 'left' : 'right';
      return '<button class="response-btn" data-dir="' + side + '">' + choice + '</button>';
    },
    button_layout: 'flex',
    trial_duration: TIMING.maxResponse,
    response_ends_trial: true,
    stimulus_duration: TIMING.maxResponse,
    on_finish: function (data) {
      if (typeof TouchHardening !== 'undefined') TouchHardening.correctRT(data);
      var responseDir = null;
      var isTimeout = (data.response === null);
      if (!isTimeout) {
        responseDir = data.response === 0 ? 'left' : 'right';
      }
      var record = recordTrial(spec, responseDir, data.rt, isTimeout);
      data.flanker_accuracy = record.accuracy;
      data.flanker_target_dir = spec.target_dir;
      data.flanker_response = responseDir;
      if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
        ParadigmCamera.addEvent('response', { trial_index: spec.trial_index, response: responseDir, rt: data.rt, correct: record.accuracy, phase: spec.is_practice ? 'practice' : 'formal' });
      }
      /* Incremental checkpoint save after each trial (non-blocking, throttled) */
      if (!spec.is_practice) { _checkpoint.save(); }
    },
  });

  /* 4. Practice feedback — 统一非惩罚性反馈, 1秒 */
  if (isPractice) {
    nodes.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: function () {
        var prev = jsPsych.data.get().last(1).values()[0];
        if (prev.flanker_accuracy === 1) {
          return '<div class="practice-feedback correct">✓ 对了</div>';
        }
        var correctDir = prev.flanker_target_dir;
        var arrow = correctDir === 'left' ? '←' : '→';
        return '<div class="practice-feedback incorrect">' +
          '看中间箭头哦' +
          '<div class="detail">中间箭头朝' + (correctDir === 'left' ? '左' : '右') + ' ' + arrow + '</div>' +
          '</div>';
      },
      choices: 'NO_KEYS',
      trial_duration: 2000,
    });
  }

  /* 5. Post-response blank (黑底, 原版POST_RESPONSE_BLANK=0.75s) */
  nodes.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div class="flanker-blank"></div>',
    choices: 'NO_KEYS',
    trial_duration: TIMING.postResponseBlank,
  });

  return nodes;
}

/* ================================================================
   Practice Phase
   ================================================================ */

let practiceAccuracy = 0;
let practiceRoundsCompleted = 0;

function buildPracticeRoundNodes(roundNum) {
  var trials = buildPracticeTrials(roundNum);
  var nodes = [];

  /* Countdown 3-2-1 (黑底白色大数字, 原版COUNTDOWN_HEIGHT=0.12) */
  for (var c = 3; c >= 1; c--) {
    nodes.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: '<div class="flanker-countdown">' + c + '</div>',
      choices: 'NO_KEYS',
      trial_duration: TIMING.countdownStep,
    });
  }

  /* Practice trials */
  trials.forEach(function (spec, idx) {
    var trialNodes = buildFlankerTrialNode(spec, true, idx + 1, trials.length);
    trialNodes.forEach(function (n) { nodes.push(n); });
  });

  /* After practice: check accuracy for THIS round */
  var capturedRound = roundNum;
  nodes.push({
    type: jsPsychCallFunction,
    func: function () {
      var practiceRecords = trialRecords.filter(function (r) {
        return r.is_practice && r.practice_round === capturedRound;
      });
      var correct = practiceRecords.reduce(function (sum, r) { return sum + r.accuracy; }, 0);
      practiceAccuracy = practiceRecords.length > 0 ? correct / practiceRecords.length : 0;
      practiceRoundsCompleted = capturedRound;
    },
  });

  return nodes;
}

/* (Practice intro page removed — VoiceGuide ends with "开始练习" button) */

/* 切换到黑底（试次阶段） */
timeline.push({ type: jsPsychCallFunction, func: function() { setTrialBackground(true); } });

/* Practice round 1 (always runs) */
timeline.push({ timeline: buildPracticeRoundNodes(1) });

/* Conditional: if failed, show retry (白底) + practice round 2 (黑底) */
timeline.push({
  timeline: [
    /* 切回白底显示再练习指导语 */
    { type: jsPsychCallFunction, func: function() { setTrialBackground(false); } },
    instructionTrial(
      '再练习一次',
      instrStep('1', '先看中间箭头', '不要看两侧的箭头',
        instrImg(STIMULI_BASE + 'incongruent/a1.webp', '200px', '只看中间')) +
      instrStep('2', '朝左按左、朝右按右', '方向和按钮一致') +
      instrStep('3', '忽略颜色变化', '看到黄色箭头也只看中间方向'),
      '按下方按钮再试一次'
    ),
    /* 切回黑底进入试次 */
    { type: jsPsychCallFunction, func: function() { setTrialBackground(true); } },
  ].concat(buildPracticeRoundNodes(2)),
  conditional_function: function () {
    return practiceAccuracy < PRACTICE_PASS_ACCURACY && practiceRoundsCompleted < MAX_PRACTICE_ROUNDS;
  },
});

/* Conditional: if still failed, practice round 3 (同样切换背景) */
timeline.push({
  timeline: [
    /* 切回白底显示最后一次练习指导语 */
    { type: jsPsychCallFunction, func: function() { setTrialBackground(false); } },
    instructionTrial(
      '最后一次练习',
      instrStep('1', '找到中间的箭头', '一排箭头中最中间的那个') +
      instrStep('2', '判断它朝哪边', '朝左按左按钮，朝右按右按钮') +
      instrStep('3', '不用管其他箭头', '两侧的箭头和颜色都不重要'),
      '按下方按钮开始最后一次练习'
    ),
    /* 切回黑底进入试次 */
    { type: jsPsychCallFunction, func: function() { setTrialBackground(true); } },
  ].concat(buildPracticeRoundNodes(3)),
  conditional_function: function () {
    return practiceAccuracy < PRACTICE_PASS_ACCURACY && practiceRoundsCompleted < MAX_PRACTICE_ROUNDS;
  },
});

/* 切回白底（指导语） */
timeline.push({ type: jsPsychCallFunction, func: function() { setTrialBackground(false); } });

/* Practice end — T3 audio reminder before formal test */
let _t3Audio = null;
timeline.push({
  type: jsPsychHtmlButtonResponse,
  stimulus: function () {
    return makeInstructionHTML(
      '练习结束，做得很好！',
      '<div style="font-size:30px;color:var(--text);margin-bottom:10px">正式测试前，记住：</div>' +
      '<div style="font-size:34px;font-weight:bold;color:var(--primary);margin:16px 0">中间朝左按左，朝右按右</div>' +
      '<div style="font-size:28px;color:var(--text-secondary)">正式测试<b>不会</b>提示对错，请尽量又快又准</div>'
    );
  },
  choices: ['开始'],
  button_html: function (choice) {
    return '<button class="jspsych-btn instr-continue-btn">' + choice + '</button>';
  },
  on_load: function () {
    /* Play T3 audio sequence */
    (async function () {
      try {
        _t3Audio = new Audio(AUDIO_BASE + '/t3_s01.mp3');
        await _t3Audio.play();
        await new Promise(function (r) { _t3Audio.onended = r; });
        await new Promise(function (r) { setTimeout(r, 500); });
        _t3Audio = new Audio(AUDIO_BASE + '/t3_s02.mp3');
        await _t3Audio.play();
        await new Promise(function (r) { _t3Audio.onended = r; });
      } catch (e) { /* audio play failed, continue silently */ }
    })();
  },
  on_finish: function () {
    if (_t3Audio) { _t3Audio.pause(); _t3Audio = null; }
  },
});

/* ================================================================
   Formal Phase
   ================================================================ */

const formalBlocks = buildFormalBlocks();
const totalFormalTrials = formalBlocks[0].length + formalBlocks[1].length; // 跨block总进度

/* 切到黑底（正式试次） */
timeline.push({ type: jsPsychCallFunction, func: function() { setTrialBackground(true); } });

/* Block 1 */
(function () {
  /* Countdown before block 1 (黑底白色大数字) */
  for (let c = 3; c >= 1; c--) {
    timeline.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: '<div class="flanker-countdown">' + c + '</div>',
      choices: 'NO_KEYS',
      trial_duration: TIMING.countdownStep,
    });
  }

  formalBlocks[0].forEach(function (spec, idx) {
    const nodes = buildFlankerTrialNode(spec, false, idx + 1, totalFormalTrials);
    nodes.forEach(function (n) { timeline.push(n); });
  });
})();

/* Force checkpoint save at block boundary (block 1 complete) */
timeline.push({ type: jsPsychCallFunction, func: function() { _checkpoint.forceSave(); } });

/* 切回白底（休息/评分） */
timeline.push({ type: jsPsychCallFunction, func: function() { setTrialBackground(false); } });

/* Break + Focus Rating between blocks — 统一注意力探针 */
timeline.push(buildAttentionProbe(jsPsych, 'flanker', 'after_block_1'));

/* 切到黑底（Block 2 试次） */
timeline.push({ type: jsPsychCallFunction, func: function() { setTrialBackground(true); } });

/* Block 2 */
(function () {
  formalBlocks[1].forEach(function (spec, idx) {
    const nodes = buildFlankerTrialNode(spec, false, formalBlocks[0].length + idx + 1, totalFormalTrials);
    nodes.forEach(function (n) { timeline.push(n); });
  });
})();

/* ================================================================
   End
   ================================================================ */

/* Force checkpoint save after block 2 (all formal trials complete) */
timeline.push({ type: jsPsychCallFunction, func: function() { _checkpoint.forceSave(); } });

/* 切回白底（结束页） */
timeline.push({ type: jsPsychCallFunction, func: function() { setTrialBackground(false); } });

timeline.push({
  type: jsPsychCallFunction,
  async: true,
  func: async function (done) {
    await ParadigmCamera.stopAndSave();
    await saveData();
    /* Experiment completed normally — clear checkpoint data */
    _checkpoint.clear();
    done();
  },
});

/* Run (with camera init before jsPsych starts) */
(async function () {
  await ParadigmCamera.init('flanker', subjectId);
  jsPsych.run(timeline);
})();
