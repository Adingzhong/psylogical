/**
 * 看眼读心 (RMET - Reading the Mind in the Eyes Test)
 * --------------------------------------------------
 * Port of 社会认知/RMET【以此为基准】/RMET.py to jsPsych 8.
 *
 * Design (照抄原版):
 *   1 练习 + 10 正式,3 选项简化中文版
 *   时序: 注视点 2000ms → 刺激+3选项 (无限时) → [反馈 2000ms 仅练习] → ITI 1000ms
 *   图片: 1000×300 px 眼部切片 (3.33:1),显示为 716×215 CSS px (~15°×4.5° 视角)
 *   按钮: 3 个灰色按钮左中右,中间按钮 Fitts 加宽 (对齐 N-back B1/B2)
 *   反馈: 统一 web-battery 非惩罚性 (✓对了 / 没关系再看仔细)
 *
 * 文献依据:
 *   - Baron-Cohen et al. (1997, 2001) Reading the Mind in the Eyes Test
 *   - 15° 视角宽度 = Baron-Cohen 2001 revised version 标准
 */

/* ================================================================
   Trial Data (从 marterial/options_new.xlsx 复制)
   ================================================================ */

const PRACTICE_TRIAL = {
  order: 'practice',
  stimulation: 'P',
  option1: '失望',
  option2: '震惊',
  option3: '担忧',
  answer: '震惊',
};

const FORMAL_TRIALS = [
  { order: 1,  stimulation: 'trial1',  option1: '被逗乐', option2: '好奇',     option3: '失望',     answer: '被逗乐' },
  { order: 2,  stimulation: 'trial2',  option1: '冷漠',   option2: '不安',     option3: '困惑',     answer: '冷漠' },
  { order: 3,  stimulation: 'trial3',  option1: '讽刺',   option2: '尴尬',     option3: '兴奋',     answer: '兴奋' },
  { order: 4,  stimulation: 'trial4',  option1: '被逗乐', option2: '好奇',     option3: '失望',     answer: '被逗乐' },
  { order: 5,  stimulation: 'trial5',  option1: '失望',   option2: '惊慌',     option3: '担忧',     answer: '惊慌' },
  { order: 6,  stimulation: 'trial6',  option1: '冷漠',   option2: '心事重重', option3: '困惑',     answer: '冷漠' },
  { order: 7,  stimulation: 'trial7',  option1: '好奇',   option2: '被逗乐',   option3: '失望',     answer: '被逗乐' },
  { order: 8,  stimulation: 'trial8',  option1: '指责',   option2: '困惑',     option3: '谨慎',     answer: '指责' },
  { order: 9,  stimulation: 'trial9',  option1: '沮丧',   option2: '心事重重', option3: '惊恐',     answer: '心事重重' },
  { order: 10, stimulation: 'trial10', option1: '不安',   option2: '冷漠',     option3: '心事重重', answer: '冷漠' },
];

/* ================================================================
   Config & Constants
   ================================================================ */

const STIMULI_BASE = '../../stimuli/rmet/';
const AUDIO_BASE = '../../audio/rmet';

const TIMING = {
  fixation: 2000,        // 注视点 2s (原版 core.wait(2.0))
  feedbackDuration: 2000, // 反馈 2s (原版 core.wait(2.0),仅练习)
  iti: 1000,             // ITI 1s (原版 core.wait(1.0))
};

/* ================================================================
   Checkpoint (inline,非阻塞增量保存)
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

  forceSave: function () {
    clearTimeout(this._timer);
    this._pending = false;
    this._doSave();
  },

  clear: function () {
    clearTimeout(this._timer);
    try { localStorage.removeItem('checkpoint_' + this._paradigm + '_' + this._sid); } catch (e) { /* ignore */ }
  },
};

/* ================================================================
   URL Params & Utils
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
  const pad = function (n) { return String(n).padStart(2, '0'); };
  return d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + '_' +
         pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds());
}

/* ================================================================
   Data Collection
   ================================================================ */

const params = getUrlParams();
const subjectId = params.subjectId || 'TEST_' + Date.now();

const trialRecords = [];
let globalTrialIndex = 0;

function recordTrial(spec, isPractice, response, rtMs) {
  globalTrialIndex += 1;
  const isCorrect = response === spec.answer ? 1 : 0;
  const rtSec = rtMs !== null ? (rtMs / 1000) : null;
  const record = {
    subject_id: subjectId,
    trial_index: spec.order,              // 原版列 (practice 或 1..10)
    trial_index_global: globalTrialIndex,
    is_practice: isPractice,
    phase_name: isPractice ? 'practice' : 'formal',
    order: spec.order,
    stimulation: spec.stimulation,
    option1: spec.option1,
    option2: spec.option2,
    option3: spec.option3,
    answer: spec.answer,
    response: response || '',
    accuracy: isCorrect,
    is_correct: isCorrect,
    rt: rtSec !== null ? rtSec.toFixed(6) : '',
    rt_ms: rtMs !== null ? Math.round(rtMs) : '',
    reaction_time: rtSec !== null ? rtSec.toFixed(6) : '',
    timestamp_hms: new Date().toTimeString().split(' ')[0],
  };
  trialRecords.push(record);
  return record;
}

/* ================================================================
   CSV Export
   ================================================================ */

function generateTrialCSV() {
  const BOM = '\uFEFF';
  const fields = [
    'subject_id', 'trial_index', 'trial_index_global', 'is_practice', 'phase_name',
    'order', 'stimulation', 'option1', 'option2', 'option3', 'answer', 'response',
    'accuracy', 'is_correct', 'rt', 'rt_ms', 'reaction_time', 'timestamp_hms',
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

let _dataSaved = false;

async function saveData() {
  if (_dataSaved) return;
  _dataSaved = true;

  const ts = timestamp();
  const trialFilename = `RMET_${subjectId}_${ts}.csv`;
  const trialCSV = generateTrialCSV();

  // Register for local ZIP packing
  if (typeof LocalPack !== 'undefined') {
    LocalPack.add(trialFilename, trialCSV);
  }

  // Try server save
  let serverOk = false;
  try {
    const resp = await safeFetch(window.location.origin + '/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paradigm: 'rmet', subject_id: subjectId, filename: trialFilename, content: trialCSV }),
    });
    if (!resp.ok) throw new Error('server error');
    serverOk = true;
  } catch (e) {
    // LocalPack 有兜底,不单独 a.click() 下载 (Edge 会拦截)
    console.warn('[RMET] server save failed, LocalPack has backup:', e);
  }

  // localStorage 兜底:服务器成功就清(防跨被试累积),失败才留
  try {
    if (serverOk) localStorage.removeItem('rmet_backup_' + subjectId);
    else localStorage.setItem('rmet_backup_' + subjectId, trialCSV);
  } catch (e) { /* ignore */ }
}

/* ================================================================
   jsPsych Init
   ================================================================ */

const subjectIdStr = subjectId;

_checkpoint.init('rmet', subjectIdStr, generateTrialCSV);

const jsPsych = initJsPsych({
  display_element: 'jspsych-target',
  on_finish: function () {
    // saveData() 在 timeline 最后的 call-function 里 await
    showEndScreen('rmet', subjectIdStr);
  },
});

/* ================================================================
   Helpers: Instruction HTML
   ================================================================ */

function makeInstructionHTML(title, body, hint) {
  var hintHTML = hint
    ? '<div style="margin-top:14px;font-size:24px;color:var(--text-secondary);font-style:italic">' + hint + '</div>'
    : '';
  return '<div class="instr-page">' +
    '<div class="instr-title">' + title + '</div>' +
    '<div class="instr-body">' + body + '</div>' +
    hintHTML +
    '</div>';
}

function instructionTrial(title, body, hint) {
  return {
    type: jsPsychHtmlButtonResponse,
    stimulus: makeInstructionHTML(title, body, hint),
    choices: ['开始'],
    button_html: function (choice) {
      return '<button class="jspsych-btn" style="margin-top:12px;">' + choice + '</button>';
    },
    button_layout: 'grid',
  };
}

/* ================================================================
   Build Trial Nodes
   ================================================================ */

function buildTrialNodes(spec, isPractice, trialNum, totalTrials) {
  const nodes = [];
  const progressLabel = isPractice ? '练习' : '';
  const progressHTML = trialNum && totalTrials
    ? '<div class="rmet-progress">' + progressLabel + ' ' + trialNum + ' / ' + totalTrials + '</div>'
    : '';

  /* 1. 注视点 (2000ms) — 原版 fixation height=100, black on white */
  nodes.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: progressHTML + '<div class="rmet-fixation">+</div>',
    choices: 'NO_KEYS',
    trial_duration: TIMING.fixation,
  });

  /* 2. 刺激 + 3 选项按钮 (无限时) */
  const imgPath = STIMULI_BASE + spec.stimulation + '.jpg';
  const options = [spec.option1, spec.option2, spec.option3];

  nodes.push({
    type: jsPsychHtmlButtonResponse,
    stimulus: progressHTML +
      '<div class="rmet-stimulus-container">' +
      '<img class="rmet-stimulus-img" src="' + imgPath + '" alt="eyes">' +
      '</div>',
    choices: options,
    button_html: function (choice, index) {
      return '<button class="rmet-response-btn" data-option-index="' + index + '">' + choice + '</button>';
    },
    button_layout: 'flex',
    response_ends_trial: true,
    /* 无 trial_duration:无限等待 (原版 while True) */
    on_start: function () {
      if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
        ParadigmCamera.addEvent('stimulus_onset', {
          trial_index: spec.order,
          stimulation: spec.stimulation,
          phase: isPractice ? 'practice' : 'formal',
        });
      }
    },
    on_finish: function (data) {
      if (typeof TouchHardening !== 'undefined') TouchHardening.correctRT(data);
      const chosen = data.response !== null && data.response !== undefined
        ? options[data.response]
        : null;
      const record = recordTrial(spec, isPractice, chosen, data.rt);
      /* 把本 trial 的 accuracy / answer 注入 jsPsych data 方便反馈 trial 读取 */
      data.rmet_accuracy = record.accuracy;
      data.rmet_answer = spec.answer;
      data.rmet_response = chosen;
      if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
        ParadigmCamera.addEvent('response', {
          trial_index: spec.order,
          response: chosen,
          rt: data.rt,
          correct: record.accuracy,
          phase: isPractice ? 'practice' : 'formal',
        });
      }
      if (!isPractice) { _checkpoint.save(); }
    },
  });

  /* 3. 练习反馈 (仅练习,2000ms) — 统一非惩罚性 */
  if (isPractice) {
    nodes.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: function () {
        const prev = jsPsych.data.get().last(1).values()[0];
        if (prev.rmet_accuracy === 1) {
          return '<div class="practice-feedback correct">✓ 对了</div>';
        }
        return '<div class="practice-feedback incorrect">没关系,再看仔细</div>';
      },
      choices: 'NO_KEYS',
      trial_duration: TIMING.feedbackDuration,
    });
  }

  /* 4. ITI 空白 (1000ms) — 原版 core.wait(1.0) */
  nodes.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div class="rmet-blank"></div>',
    choices: 'NO_KEYS',
    trial_duration: TIMING.iti,
  });

  return nodes;
}

/* ================================================================
   Build Timeline
   ================================================================ */

const timeline = [];

/* Preload 11 图 + 7 音频 — 必须等所有 audio 都下完才能进 instruction,
   否则 VoiceGuide 播放时会卡顿(慢网/首次访问 SW 缓存空) */
const _audioFiles = [];
for (let i = 1; i <= 7; i++) {
  _audioFiles.push(AUDIO_BASE + '/s' + String(i).padStart(2, '0') + '.mp3');
}
const _imageFiles = [STIMULI_BASE + 'P.jpg'];
for (let i = 1; i <= 10; i++) {
  _imageFiles.push(STIMULI_BASE + 'trial' + i + '.jpg');
}
_imageFiles.push('img/rules.webp');

timeline.push({
  type: jsPsychPreload,
  images: _imageFiles,
  audio: _audioFiles,
  show_progress_bar: true,
  message: '<p style="font-size:28px;font-family:var(--font)">正在加载,请稍候...</p>',
  continue_after_error: true,
});
// 2026-04-19: 预加载后检查失败资源
timeline.push({
  type: jsPsychCallFunction, async: true,
  func: function(done) {
    if (typeof TouchHardening !== 'undefined' && TouchHardening.checkLoadFailures) {
      TouchHardening.checkLoadFailures({ paradigmName: 'RMET 看眼读心' }).then(function() { done(); });
    } else { done(); }
  },
});

/* VoiceGuide: 4 步区域高亮 + 分步旁白 (和 Flanker 一致的标准 API) */
timeline.push({
  type: jsPsychCallFunction,
  async: true,
  func: async function (done) {
    await VoiceGuide.show({
      image: 'img/rules.webp',
      btnRegion: { x: '80.1%', y: '4.9%', w: '15%', h: '8.2%' },  // "继续" 按钮 (人工标注)
      buttonText: '开始练习',
      pauseBetween: 400,
      steps: [
        /* 第1步: 观察眼睛图片 */
        { region: { x: '16%', y: '30.4%', w: '31.6%', h: '17%' }, lines: [
          { audio: `${AUDIO_BASE}/s01.mp3`, subtitle: '接下来做一个看眼睛的游戏' },
          { audio: `${AUDIO_BASE}/s02.mp3`, subtitle: '屏幕上会出现一张眼睛部位的图片' },
        ] },
        /* 第2步: 阅读 3 个词语 */
        { region: { x: '7.3%', y: '73.9%', w: '49.4%', h: '13%' }, lines: [
          { audio: `${AUDIO_BASE}/s03.mp3`, subtitle: '图片下面有三个词语' },
          { audio: `${AUDIO_BASE}/s04.mp3`, subtitle: '这三个词描述图中人物的感受' },
        ] },
        /* 第3步: 选择最符合的一项 */
        { region: { x: '64%', y: '57.8%', w: '28.7%', h: '20.2%' }, lines: [
          { audio: `${AUDIO_BASE}/s05.mp3`, subtitle: '凭您的第一直觉作答' },
          { audio: `${AUDIO_BASE}/s06.mp3`, subtitle: '选出最符合的一项点击' },
        ] },
        /* "继续" 按钮区域 */
        { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
          { audio: `${AUDIO_BASE}/s07.mp3`, subtitle: '准备好了就点击右上角按钮' },
        ] },
      ],
    });
    done();
  },
});

/* ================================================================
   Practice Phase (1 试次,无通过门控 — 原版设计)
   ================================================================ */

(function () {
  const practiceNodes = buildTrialNodes(PRACTICE_TRIAL, true, 1, 1);
  practiceNodes.forEach(function (n) { timeline.push(n); });
})();

/* 练习结束提醒 → 正式测试 */
timeline.push({
  type: jsPsychHtmlButtonResponse,
  stimulus: makeInstructionHTML(
    '练习结束',
    '<div style="font-size:34px;color:var(--text);margin-bottom:12px">接下来是正式测试</div>' +
    '<div style="font-size:32px;font-weight:bold;color:var(--primary);margin:16px 0">请凭第一直觉又快又准地作答</div>' +
    '<div style="font-size:28px;color:var(--text-secondary)">正式测试<b>不会</b>提示对错</div>'
  ),
  choices: ['开始正式测试'],
  button_html: function (choice) {
    return '<button class="jspsych-btn" style="margin-top:12px;">' + choice + '</button>';
  },
  button_layout: 'grid',
});

/* 3-2-1 倒计时 (白底深色大字, 给被试从"点了开始"到"第一题"的反应时间) */
for (var _c = 3; _c >= 1; _c--) {
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div style="font-size:14vh;color:#1A1A2E;font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">' + _c + '</div>',
    choices: 'NO_KEYS',
    trial_duration: 1000,
  });
}

/* ================================================================
   Formal Phase (10 试次)
   ================================================================ */

FORMAL_TRIALS.forEach(function (spec, idx) {
  const nodes = buildTrialNodes(spec, false, idx + 1, FORMAL_TRIALS.length);
  nodes.forEach(function (n) { timeline.push(n); });
});

/* Force checkpoint save at end of formal trials */
timeline.push({ type: jsPsychCallFunction, func: function () { _checkpoint.forceSave(); } });

/* ================================================================
   Attention Probe (结尾一次)
   ================================================================ */

timeline.push(buildAttentionProbe(jsPsych, 'rmet', 'end'));

/* ================================================================
   End: save + stop camera + clear checkpoint + end screen
   ================================================================ */

timeline.push({
  type: jsPsychCallFunction,
  async: true,
  func: async function (done) {
    try {
      if (typeof ParadigmCamera !== 'undefined') await ParadigmCamera.stopAndSave();
    } catch (e) { console.warn('[RMET] camera stop error:', e); }
    await saveData();
    _checkpoint.clear();
    done();
  },
});

/* Run: camera init → jsPsych timeline */
(async function () {
  try {
    if (typeof ParadigmCamera !== 'undefined') await ParadigmCamera.init('rmet', subjectIdStr);
  } catch (e) { console.warn('[RMET] camera init error:', e); }
  jsPsych.run(timeline);
})();
