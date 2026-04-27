/**
 * SART (Sustained Attention to Response Task) - Web Battery
 * --------------------------------------------------
 * Port of SART PsychoPy (main.py + managers) to jsPsych 8.
 *
 * Design (Robertson et al., 1997):
 *   Digits 1-9, Go/No-Go  (No-Go digit = 3)
 *   Single "tap" button at bottom
 *   Practice: 9 trials (7 go + 2 nogo at positions 4,7)
 *     Pass: >= 6 go correct AND >= 1 nogo correct, max 2 attempts
 *   Formal: 1 block x 36 trials (9 digits x 4 reps, no consecutive 3s)
 *   Followed by 1 attention probe (1-9)
 *   Timing: digit 1250ms -> blank 1250ms  (total 2500ms / trial)
 *   SDT metrics: d', A', criterion c
 */

/* ================================================================
   Configuration
   ================================================================ */

const CONFIG = {
  nogoDigit: 3,
  timing: {
    stimulusDuration: 1250,
    blankDuration: 1250,
    trialDuration: 2500,
    feedbackDuration: 800,
  },
  rtValidRange: [150, 2000],
  practice: {
    totalTrials: 9,
    goTrials: 7,
    nogoTrials: 2,
    nogoPositions: [4, 7],
    goMinCorrect: 6,
    nogoMinCorrect: 1,
    maxAttempts: 2,
  },
  formal: {
    totalTrials: 36,   /* 9 digits x 4 reps = 36 trials */
    repetitions: 4,
    blocks: 1,         /* Product doc: 36 trials total, 1 probe at end */
  },
};

const DIGITS = [1, 2, 3, 4, 5, 6, 7, 8, 9];
const GO_DIGITS = DIGITS.filter(function (d) { return d !== CONFIG.nogoDigit; });

/* ================================================================
   Checkpoint (incremental save) — inline since not using ES modules
   ================================================================ */

var _ckpt = (function () {
  var saving = false, lastTime = 0, pending = false;
  var paradigm = '', sid = '', getData = null;
  var MIN = 5000;

  function doSave() {
    if (saving) { pending = true; return; }
    var csv = getData(); if (!csv) return;
    saving = true; lastTime = Date.now();
    var lsKey = 'checkpoint_' + paradigm + '_' + sid;
    var fname = paradigm + '_' + sid + '_checkpoint.csv';
    try { localStorage.setItem(lsKey, csv); } catch (e) { /* ignore */ }
    fetch(window.location.origin + '/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paradigm: paradigm, subject_id: sid, filename: fname, content: csv }),
    }).catch(function () {
      console.debug('[Checkpoint] ' + paradigm + ' server save failed, localStorage backup exists');
    }).then(function () {
      saving = false;
      if (pending) { pending = false; doSave(); }
    });
  }

  return {
    init: function (p, subjectId, getDataFn) { paradigm = p; sid = subjectId; getData = getDataFn; },
    save: function () {
      var elapsed = Date.now() - lastTime;
      if (elapsed < MIN) {
        if (!pending) {
          pending = true;
          setTimeout(function () { if (pending) { pending = false; doSave(); } }, MIN - elapsed);
        }
        return;
      }
      doSave();
    },
    forceSave: function () { doSave(); },
    clear: function () {
      try { localStorage.removeItem('checkpoint_' + paradigm + '_' + sid); } catch (e) { /* ignore */ }
    },
  };
})();

/* ================================================================
   URL Params & Utils
   ================================================================ */

function getUrlParams() {
  var p = new URLSearchParams(window.location.search);
  return { subjectId: p.get('sid') || '', session: p.get('session') || 'S001' };
}

function timestamp() {
  var d = new Date();
  var pad = function (n) { return String(n).padStart(2, '0'); };
  return d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + '_' + pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds());
}

function shuffleArray(arr) {
  var a = arr.slice();
  for (var i = a.length - 1; i > 0; i--) {
    var j = Math.floor(Math.random() * (i + 1));
    var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
  }
  return a;
}

/* ================================================================
   Sequence Generation
   ================================================================ */

function generatePracticeSequence() {
  var cfg = CONFIG.practice;
  var goDigits = shuffleArray(GO_DIGITS).slice(0, cfg.goTrials);
  var seq = [];
  var goIdx = 0;
  for (var i = 1; i <= cfg.totalTrials; i++) {
    if (cfg.nogoPositions.indexOf(i) >= 0) {
      seq.push({ digit: CONFIG.nogoDigit, trial_type: 'nogo', trial_index: i });
    } else {
      seq.push({ digit: goDigits[goIdx++], trial_type: 'go', trial_index: i });
    }
  }
  return seq;
}

function hasConsecutiveNogo(digits) {
  for (var i = 0; i < digits.length - 1; i++) {
    if (digits[i] === CONFIG.nogoDigit && digits[i + 1] === CONFIG.nogoDigit) return true;
  }
  return false;
}

function generateFormalSequence() {
  var digits = [];
  for (var r = 0; r < CONFIG.formal.repetitions; r++) {
    digits = digits.concat(DIGITS);
  }
  for (var attempt = 0; attempt < 1000; attempt++) {
    var shuffled = shuffleArray(digits);
    if (!hasConsecutiveNogo(shuffled)) {
      return shuffled.map(function (d, i) {
        return { digit: d, trial_type: d === CONFIG.nogoDigit ? 'nogo' : 'go', trial_index: i + 1 };
      });
    }
  }
  return shuffleArray(digits).map(function (d, i) {
    return { digit: d, trial_type: d === CONFIG.nogoDigit ? 'nogo' : 'go', trial_index: i + 1 };
  });
}

/* ================================================================
   Data Collection
   ================================================================ */

var trialRecords = [];
var probeRecords = [];
var urlParams = getUrlParams();
var subjectId = urlParams.subjectId || 'TEST_' + Date.now();
var globalTrialIndex = 0;

/* Initialize checkpoint — uses generateCSV (defined below) via lazy reference */
_ckpt.init('sart', subjectId, function () { return generateCSV(); });

function recordSARTTrial(trialInfo, blockType, responseMade, rt) {
  globalTrialIndex++;
  var isNogo = trialInfo.trial_type === 'nogo';
  var accuracy = isNogo ? (responseMade ? 0 : 1) : (responseMade ? 1 : 0);

  var errorType = '';
  if (isNogo && responseMade) errorType = 'commission';
  else if (!isNogo && !responseMade) errorType = 'omission';

  var phase = blockType.indexOf('practice') === 0 ? 'practice' : 'formal';
  var blockNumber = 0;
  var match = blockType.match(/(\d+)/);
  if (match) blockNumber = parseInt(match[1]);

  var record = {
    subject_id: subjectId,
    global_trial_index: globalTrialIndex,
    block_type: blockType,
    block_number: blockNumber,
    trial_index: trialInfo.trial_index,
    digit: trialInfo.digit,
    trial_type: trialInfo.trial_type,
    response_made: responseMade ? 1 : 0,
    reaction_time_ms: rt !== null ? Math.round(rt * 10) / 10 : '',
    rt_ms: rt !== null ? Math.round(rt) : '',
    accuracy: accuracy,
    error_type: errorType,
    phase: phase,
    timestamp: new Date().toISOString(),
    rt_hold: _sartHoldDuration !== null ? _sartHoldDuration : '',
    drift_max: _sartStartX !== null ? Math.round(Math.sqrt(_sartDriftMaxSq)) : '',
    drift_path: _sartStartX !== null ? Math.round(_sartDriftPath) : '',
    drift_end: _sartDriftEnd || '',
    tap_count: _sartTapCount,
    input_type: _sartInputType || '',
  };
  trialRecords.push(record);
  return record;
}

function recordProbe(blockIndex, rating) {
  probeRecords.push({
    block_index: blockIndex,
    attention_rating: rating,
    probe_ts: new Date().toISOString(),
  });
}

/* ================================================================
   SDT Computation
   ================================================================ */

function probit(p) {
  if (p <= 0) return -5;
  if (p >= 1) return 5;
  if (p < 0.5) return -probit(1 - p);
  var t = Math.sqrt(-2 * Math.log(1 - p));
  return t - (2.515517 + 0.802853 * t + 0.010328 * t * t) / (1 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t * t * t);
}

function computeSDT() {
  var formalTrials = trialRecords.filter(function (t) { return t.phase === 'formal'; });
  if (formalTrials.length === 0) return {};

  var go = formalTrials.filter(function (t) { return t.trial_type === 'go'; });
  var nogo = formalTrials.filter(function (t) { return t.trial_type === 'nogo'; });
  var goCorrect = go.filter(function (t) { return t.accuracy === 1; }).length;
  var nogoCorrect = nogo.filter(function (t) { return t.accuracy === 1; }).length;
  var commissionN = nogo.filter(function (t) { return t.error_type === 'commission'; }).length;
  var omissionN = go.filter(function (t) { return t.error_type === 'omission'; }).length;

  var goAcc = go.length > 0 ? goCorrect / go.length : 0;
  var nogoAcc = nogo.length > 0 ? nogoCorrect / nogo.length : 0;
  var commissionRate = nogo.length > 0 ? commissionN / nogo.length : 0;

  var overallAcc = formalTrials.length > 0 ? (goCorrect + nogoCorrect) / formalTrials.length : 0;
  var omissionRate = go.length > 0 ? omissionN / go.length : 0;

  /* RT filtering: absolute threshold 150-2000ms, then 3-SD outlier removal */
  var goRTs = go.filter(function (t) {
    return t.accuracy === 1 && t.reaction_time_ms !== '' && t.reaction_time_ms >= 150 && t.reaction_time_ms <= 2000;
  }).map(function (t) { return t.reaction_time_ms; });

  var goRTMean = goRTs.length > 0 ? goRTs.reduce(function (a, b) { return a + b; }, 0) / goRTs.length : 0;
  var goRTSD = 0;
  if (goRTs.length > 1) {
    goRTSD = Math.sqrt(goRTs.reduce(function (s, v) { return s + (v - goRTMean) * (v - goRTMean); }, 0) / (goRTs.length - 1));
  }

  /* 3-SD outlier removal (matching PsychoPy version) */
  var rtExcludedRel = 0;
  if (goRTs.length >= 3 && goRTSD > 0) {
    var cleanRTs = goRTs.filter(function (rt) {
      return Math.abs(rt - goRTMean) <= 3 * goRTSD;
    });
    rtExcludedRel = goRTs.length - cleanRTs.length;
    goRTs = cleanRTs;
    goRTMean = goRTs.length > 0 ? goRTs.reduce(function (a, b) { return a + b; }, 0) / goRTs.length : 0;
    if (goRTs.length > 1) {
      goRTSD = Math.sqrt(goRTs.reduce(function (s, v) { return s + (v - goRTMean) * (v - goRTMean); }, 0) / (goRTs.length - 1));
    }
  }

  var goRTCoV = goRTMean > 0 ? goRTSD / goRTMean : 0;

  var hitRate = goAcc;
  var faRate = commissionRate;
  if (go.length > 0) hitRate = Math.max(0.5 / go.length, Math.min(1 - 0.5 / go.length, hitRate));
  if (nogo.length > 0) faRate = Math.max(0.5 / nogo.length, Math.min(1 - 0.5 / nogo.length, faRate));

  var zHit = probit(hitRate);
  var zFA = probit(faRate);
  var dPrime = Math.round((zHit - zFA) * 10000) / 10000;
  var criterionC = Math.round(-0.5 * (zHit + zFA) * 10000) / 10000;

  var aPrime = 0.5;
  if (hitRate !== faRate) {
    if (hitRate >= faRate) {
      aPrime = 0.5 + ((hitRate - faRate) * (1 + hitRate - faRate)) / (4 * hitRate * (1 - faRate));
    } else {
      aPrime = 0.5 - ((faRate - hitRate) * (1 + faRate - hitRate)) / (4 * faRate * (1 - hitRate));
    }
  }
  aPrime = Math.round(aPrime * 10000) / 10000;

  /* Skill Index = (nogo_accuracy / go_rt_mean) * 1000 */
  var skillIndex = goRTMean > 0 ? nogoAcc / goRTMean * 1000 : 0;

  return {
    total_trials: formalTrials.length,
    go_trials_n: go.length,
    nogo_trials_n: nogo.length,
    go_accuracy: Math.round(goAcc * 10000) / 10000,
    nogo_accuracy: Math.round(nogoAcc * 10000) / 10000,
    overall_accuracy: Math.round(overallAcc * 10000) / 10000,
    commission_errors: commissionN,
    commission_error_rate: Math.round(commissionRate * 10000) / 10000,
    omission_errors: omissionN,
    omission_error_rate: Math.round(omissionRate * 10000) / 10000,
    go_rt_mean: Math.round(goRTMean * 100) / 100,
    go_rt_sd: Math.round(goRTSD * 100) / 100,
    go_rt_cov: Math.round(goRTCoV * 10000) / 10000,
    d_prime: dPrime,
    criterion_c: criterionC,
    a_prime: aPrime,
    skill_index: Math.round(skillIndex * 10000) / 10000,
    rt_excluded_3sd: rtExcludedRel,
  };
}

/* ================================================================
   CSV / JSON Export
   ================================================================ */

function generateCSV() {
  var BOM = '\uFEFF';
  var fields = [
    'subject_id', 'global_trial_index', 'block_type', 'block_number',
    'trial_index', 'digit', 'trial_type',
    'response_made', 'reaction_time_ms', 'rt_ms', 'accuracy', 'error_type',
    'phase', 'timestamp',
    'rt_hold', 'drift_max', 'drift_path', 'drift_end', 'tap_count', 'input_type',
  ];
  var csv = BOM + fields.join(',') + '\n';
  trialRecords.forEach(function (r) {
    csv += fields.map(function (f) {
      var v = r[f];
      if (v === undefined || v === null) return '';
      return String(v);
    }).join(',') + '\n';
  });
  return csv;
}

function generateSummaryJSON() {
  return JSON.stringify({
    participant: { subject_id: subjectId },
    behavioral_metrics: computeSDT(),
    probes: probeRecords,
  }, null, 2);
}

function downloadBlob(content, filename, mimeType) {
  var blob = new Blob([content], { type: mimeType || 'text/plain' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

var _dataSaved = false;
async function saveData() {
  if (_dataSaved) return;
  _dataSaved = true;
  var ts = timestamp();
  var csvFilename = 'SART_' + subjectId + '_' + ts + '.csv';
  var jsonFilename = 'SART_' + subjectId + '_' + ts + '_summary.json';
  var csvContent = generateCSV();
  var jsonContent = generateSummaryJSON();

  // Register files for local ZIP packing
  if (typeof LocalPack !== 'undefined') {
    LocalPack.add(csvFilename, csvContent);
    LocalPack.add(jsonFilename, jsonContent);
  }

  var serverOk = false;
  try {
    var resp = await safeFetch(window.location.origin + '/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paradigm: 'sart', subject_id: subjectId, filename: csvFilename, content: csvContent }),
    });
    if (!resp.ok) throw new Error('server error');
    var resp2 = await safeFetch(window.location.origin + '/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paradigm: 'sart', subject_id: subjectId, filename: jsonFilename, content: jsonContent }),
    });
    if (!resp2.ok) throw new Error('server error');
    serverOk = true;
  } catch (e) {
    console.warn('[SART] server save failed, LocalPack has backup:', e);
  }

  // localStorage 兜底:服务器成功就清(防跨被试累积),失败才留
  try {
    if (serverOk) localStorage.removeItem('sart_backup_' + subjectId);
    else localStorage.setItem('sart_backup_' + subjectId, csvContent);
  } catch (e) { /* ignore */ }

  /* Clear checkpoint — experiment completed normally, full data saved */
  _ckpt.clear();
}

/* ================================================================
   jsPsych Init
   ================================================================ */

var jsPsych = initJsPsych({
  display_element: 'jspsych-target',
  on_finish: function () {
    // 藏掉persistent按钮
    var wrap = document.getElementById('sart-persistent-btn-wrap');
    if (wrap) wrap.style.display = 'none';
    // saveData() is awaited in the timeline call-function trial — not here
    showEndScreen('sart', subjectId);
  },
});

/* ================================================================
   HTML Builders
   ================================================================ */

function makeInstructionHTML(title, body, hint) {
  if (hint === undefined || hint === null) hint = '(按下方按钮继续)';
  return '<div class="sart-instr-page">' +
    '<div class="sart-instr-title">' + title + '</div>' +
    '<div class="sart-instr-body">' + body + '</div>' +
    (hint ? '<div class="sart-instr-hint">' + hint + '</div>' : '') +
    '</div>';
}

function instructionTrial(title, body, hint, btnLabel) {
  btnLabel = btnLabel || '继续';
  return {
    type: jsPsychHtmlButtonResponse,
    stimulus: makeInstructionHTML(title, body, hint),
    choices: [btnLabel],
    button_html: function (choice) {
      return '<button class="sart-instr-btn">' + choice + '</button>';
    },
  };
}

/* --- Persistent button state (avoids DOM rebuild flash) --- */
var _sartBtn = null;
var _sartTrialStart = 0;
var _sartResponseMade = false;
var _sartResponseRT = null;
var _sartHoldStart = null;     // pointerdown 时间戳
var _sartStartX = null;        // pointerdown 位置
var _sartStartY = null;
var _sartDriftMaxSq = 0;
var _sartDriftPath = 0;
var _sartLastMoveX = 0;
var _sartLastMoveY = 0;
var _sartTapCount = 0;
var _sartInputType = null;
var _sartHoldDuration = null;
var _sartDriftEnd = 0;

function _ensureSartBtn() {
  if (_sartBtn) return;
  _sartBtn = document.getElementById('sart-persistent-btn');

  // 响应记录在 pointerdown（按下即记录，不等松开）
  // RT = pointerdown 时刻（认知心理学标准，Bjorklund 1991）
  // 视觉反馈完全由 CSS :active 处理，不用 TouchHardening（避免两套系统打架）
  _sartBtn.addEventListener('pointerdown', function (e) {
    _sartTapCount++;
    if (!_sartResponseMade) {
      _sartResponseMade = true;
      _sartResponseRT = performance.now() - _sartTrialStart;
      _sartHoldStart = performance.now();
      _sartStartX = e.clientX;
      _sartStartY = e.clientY;
      _sartLastMoveX = e.clientX;
      _sartLastMoveY = e.clientY;
      _sartDriftMaxSq = 0;
      _sartDriftPath = 0;
      _sartInputType = e.pointerType || null;
      // 已答题：按钮变浅绿，表示"这题按过了"
      _sartBtn.style.background = '#C8E6C9';
    }
  });

  _sartBtn.addEventListener('pointermove', function (e) {
    if (_sartStartX === null) return;
    var dx = e.clientX - _sartStartX;
    var dy = e.clientY - _sartStartY;
    var distSq = dx * dx + dy * dy;
    if (distSq > _sartDriftMaxSq) _sartDriftMaxSq = distSq;
    _sartDriftPath += Math.sqrt(
      Math.pow(e.clientX - _sartLastMoveX, 2) + Math.pow(e.clientY - _sartLastMoveY, 2)
    );
    _sartLastMoveX = e.clientX;
    _sartLastMoveY = e.clientY;
  });

  _sartBtn.addEventListener('pointerup', function (e) {
    if (_sartHoldStart !== null) {
      _sartHoldDuration = Math.round(performance.now() - _sartHoldStart);
      _sartDriftEnd = Math.round(Math.sqrt(
        Math.pow(e.clientX - _sartStartX, 2) + Math.pow(e.clientY - _sartStartY, 2)
      ));
    }
  });
}

function buildSARTTrialNodes(trialInfo, blockType, showFeedback) {
  var nodes = [];

  /* Combined digit + blank: digit shown for 1250ms, total trial 2500ms.
     Uses persistent button (never rebuilt) to eliminate inter-trial flash.
     jsPsychHtmlKeyboardResponse with NO_KEYS — button response injected manually. */
  nodes.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: (function() {
      var isPractice = blockType.indexOf('practice') !== -1;
      var total = isPractice ? CONFIG.practice.totalTrials : CONFIG.formal.totalTrials;
      var label = isPractice ? '练习 ' : '';
      return '<div style="position:fixed;top:12px;right:24px;color:rgba(255,255,255,0.4);font-size:36px;font-family:var(--font);pointer-events:none;">' + label + trialInfo.trial_index + ' / ' + total + '</div>' +
        '<div class="sart-digit">' + trialInfo.digit + '</div>';
    })(),
    choices: 'NO_KEYS',
    stimulus_duration: CONFIG.timing.stimulusDuration,
    trial_duration: CONFIG.timing.trialDuration,
    response_ends_trial: false,
    on_start: function () {
      if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
        var phase = blockType.indexOf('practice') === 0 ? 'practice' : 'formal';
        ParadigmCamera.addEvent('stimulus_onset', { trial_index: trialInfo.trial_index, digit: trialInfo.digit, is_nogo: trialInfo.trial_type === 'nogo', phase: phase });
      }
    },
    on_load: function () {
      _ensureSartBtn();
      _sartResponseMade = false;
      _sartResponseRT = null;
      _sartHoldStart = null;
      _sartStartX = null;
      _sartStartY = null;
      _sartDriftMaxSq = 0;
      _sartDriftPath = 0;
      _sartLastMoveX = 0;
      _sartLastMoveY = 0;
      _sartTapCount = 0;
      _sartInputType = null;
      _sartHoldDuration = null;
      _sartDriftEnd = 0;
      // 重置按钮视觉状态
      _sartBtn.classList.remove('elderly-pressing');
      _sartBtn.classList.remove('elderly-confirmed');
      _sartBtn.style.background = '';  // 恢复白色
      _sartTrialStart = performance.now();
      // 2026-04-19: SART trial 才显示按钮,非 trial(指导语/探针/保存)默认 hidden
      var _wrap = document.getElementById('sart-persistent-btn-wrap');
      if (_wrap) _wrap.style.display = 'flex';
    },
    on_finish: function (data) {
      // 2026-04-19: trial 结束立即隐藏按钮 — 下一个 SART trial on_load 会重新 show
      var _wrap = document.getElementById('sart-persistent-btn-wrap');
      if (_wrap) _wrap.style.display = 'none';
      // Inject persistent-button response into trial data
      if (_sartResponseMade) {
        data.response = 0;
        data.rt = _sartResponseRT;
      } else {
        data.response = null;
        data.rt = null;
      }
      if (typeof TouchHardening !== 'undefined') TouchHardening.correctRT(data);
      var responseMade = data.response !== null;
      var rt = data.rt;
      var record = recordSARTTrial(trialInfo, blockType, responseMade, rt);
      data.sart_accuracy = record.accuracy;
      data.sart_error_type = record.error_type;
      data.sart_trial_type = trialInfo.trial_type;
      data.sart_digit = trialInfo.digit;
      if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
        ParadigmCamera.addEvent('response', { trial_index: trialInfo.trial_index, rt: rt, correct: record.accuracy, phase: record.phase });
      }
      /* Checkpoint: save after each formal trial */
      if (record.phase === 'formal') { _ckpt.save(); }
    },
  });

  if (showFeedback) {
    nodes.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: function () {
        var prev = jsPsych.data.get().last(1).values()[0];
        if (prev.sart_accuracy === 1) {
          return '<div class="practice-feedback correct">✓ 对了</div>';
        }
        if (prev.sart_error_type === 'commission') {
          return '<div class="practice-feedback incorrect">看到3不要按哦</div>';
        }
        return '<div class="practice-feedback incorrect">记得要按哦</div>';
      },
      choices: 'NO_KEYS',
      // 2026-04-19: 正确反馈快过,错误保留久让老人反应
      trial_duration: function () {
        var prev = jsPsych.data.get().last(1).values()[0];
        return prev.sart_accuracy === 1 ? 800 : 2000;
      },
    });
  }

  return nodes;
}

/* ================================================================
   Build Probe (attention rating 1-9)
   ================================================================ */

function buildProbe(blockIndex) {
  return {
    type: jsPsychHtmlButtonResponse,
    stimulus: '<div class="sart-instr-page">' +
      '<div class="sart-instr-title">请评价刚才对任务的专注程度</div>' +
      '<div style="margin-top:16px;font-size:26px;color:#888">1 = 完全不专注 &nbsp;&nbsp;&nbsp; 9 = 非常专注</div>' +
      '<div class="rating-buttons" style="margin-top:28px">' +
      [1, 2, 3, 4, 5, 6, 7, 8, 9].map(function (n) {
        return '<button class="rating-btn" data-rating="' + n + '" ' +
          'onclick="document.querySelectorAll(\'.rating-btn\').forEach(function(b){b.classList.remove(\'selected\')});' +
          'this.classList.add(\'selected\');window._sartRating=' + n + ';' +
          'var cb=document.getElementById(\'sart-probe-confirm\');if(cb){cb.disabled=false;cb.style.opacity=1;}">' + n + '</button>';
      }).join('') +
      '</div></div>',
    choices: ['确认'],
    button_html: function (choice) {
      return '<button class="sart-instr-btn" id="sart-probe-confirm" disabled style="opacity:0.4">' + choice + '</button>';
    },
    on_load: function () {
      window._sartRating = null;
      /* Checkpoint: force save before rating probe */
      _ckpt.forceSave();
    },
    on_finish: function () {
      recordProbe(blockIndex, window._sartRating || 5);
    },
  };
}

/* ================================================================
   Timeline Assembly
   ================================================================ */

var timeline = [];

/* ---- Preload 图片 + 音频 — 必须等所有 audio 都下完才进 instruction,
       否则 VoiceGuide 播放时会卡顿(慢网/首次访问 SW 缓存空) ---- */
var SART_AUDIO = '../../audio/sart';
var _sartAudioFiles = [];
for (var _si = 1; _si <= 11; _si++) _sartAudioFiles.push(SART_AUDIO + '/s' + String(_si).padStart(2,'0') + '.mp3');
timeline.push({
  type: jsPsychPreload,
  images: ['img/rules.webp'],
  audio: _sartAudioFiles,
  show_progress_bar: true,
  message: '<p style="font-size:32px;">正在加载，请稍候...</p>',
  continue_after_error: true,
});
// 2026-04-19: 预加载后检查失败资源
timeline.push({
  type: jsPsychCallFunction, async: true,
  func: function(done) {
    if (typeof TouchHardening !== 'undefined' && TouchHardening.checkLoadFailures) {
      TouchHardening.checkLoadFailures({ paradigmName: 'SART' }).then(function() { done(); });
    } else { done(); }
  },
});

/* ---- Voice-guided instruction ---- */
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
        { region: { x: '8.2%', y: '41.6%', w: '16.5%', h: '25.6%' }, lines: [
          { audio: SART_AUDIO + '/s01.mp3', subtitle: '屏幕上会一个一个出现数字' },
          { audio: SART_AUDIO + '/s02.mp3', subtitle: '其中有一个捣蛋数字，就是三' },
        ] },
        { region: { x: '35.1%', y: '34.6%', w: '29.6%', h: '13.2%' }, lines: [
          { audio: SART_AUDIO + '/s03.mp3', subtitle: '除了三以外的数字都是安全数字' },
          { audio: SART_AUDIO + '/s04.mp3', subtitle: '看到安全数字，请按下按钮' },
        ] },
        { region: { x: '39.2%', y: '51.8%', w: '22%', h: '30%' }, lines: [
          { audio: SART_AUDIO + '/s05.mp3', subtitle: '比如看到七，按一下按钮' },
        ] },
        { region: { x: '69.3%', y: '33.8%', w: '13.2%', h: '16.6%' }, lines: [
          { audio: SART_AUDIO + '/s06.mp3', subtitle: '但是看到三的时候，不要按' },
          { audio: SART_AUDIO + '/s07.mp3', subtitle: '忍住就好' },
        ] },
        { region: { x: '62.2%', y: '30.3%', w: '27.8%', h: '53%' }, lines: [
          { audio: SART_AUDIO + '/s08.mp3', subtitle: '三出现的时候，什么都不用做，等下一个数字' },
        ] },
        { region: { x: '36.4%', y: '35.6%', w: '27.4%', h: '9%' }, lines: [
          { audio: SART_AUDIO + '/s09.mp3', subtitle: '除了三不按，其他数字都要按，越快越好' },
        ] },
        { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
          { audio: SART_AUDIO + '/s10.mp3', subtitle: '明白了就点击开始练习' },
        ] },
      ],
    });
    done();
  },
});

/* ---- 白→黑过渡：3-2-1倒计时 ---- */
var _countdownStyle = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:#000;display:flex;align-items:center;justify-content:center;';
var _countdownFont = 'color:#fff;font-size:120px;font-weight:bold;';
['3', '2', '1'].forEach(function (n) {
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div style="' + _countdownStyle + '"><span style="' + _countdownFont + '">' + n + '</span></div>',
    choices: 'NO_KEYS',
    trial_duration: 1000,
    // 2026-04-19: 倒计时无需特殊处理 — persistent-btn 默认 display:none,
    // SART trial on_load 才 show,on_finish 立即 hide。倒计时不是 SART trial,按钮自然隐藏。
  });
});

/* ---- Practice Phase ---- */

var practicePassed = false;

function buildPracticeNodes(attemptNum) {
  var blockType = 'practice' + attemptNum;
  var sequence = generatePracticeSequence();
  var nodes = [];
  sequence.forEach(function (info) {
    buildSARTTrialNodes(info, blockType, true).forEach(function (n) { nodes.push(n); });
  });
  nodes.push({
    type: jsPsychCallFunction,
    func: function () {
      var recs = trialRecords.filter(function (r) { return r.block_type === blockType; });
      var goOK = recs.filter(function (r) { return r.trial_type === 'go' && r.accuracy === 1; }).length;
      var nogoOK = recs.filter(function (r) { return r.trial_type === 'nogo' && r.accuracy === 1; }).length;
      practicePassed = goOK >= CONFIG.practice.goMinCorrect && nogoOK >= CONFIG.practice.nogoMinCorrect;
      if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
        ParadigmCamera.addEvent('practice_end', { attempt: attemptNum, passed: practicePassed });
      }
      /* Checkpoint: force save after practice ends */
      _ckpt.forceSave();
    },
  });
  return nodes;
}

/* Attempt 1 */
timeline.push({
  type: jsPsychCallFunction,
  func: function () {
    if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
      ParadigmCamera.addEvent('practice_start', { attempt: 1 });
    }
  },
});
buildPracticeNodes(1).forEach(function (n) { timeline.push(n); });

/* Conditional attempt 2 */
timeline.push({
  timeline: [
    instructionTrial(
      '刚刚出现了一些小错误哦',
      '<div style="line-height:2">' +
        '<p style="font-size:34px;color:#555;margin-bottom:16px">没关系，让我们再练习一次！</p>' +
        '<div class="sart-rule-box nogo-rule" style="font-size:32px">看到 <span style="font-size:40px">3</span> &rarr; 别按！</div>' +
        '<div class="sart-rule-box go-rule" style="font-size:32px">看到其他数字 &rarr; 快按！</div>' +
      '</div>',
      '按下方按钮再试一次',
      '继续'
    ),
    {
      type: jsPsychCallFunction,
      func: function () {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('practice_start', { attempt: 2 });
        }
      },
    },
  ].concat(buildPracticeNodes(2)),
  conditional_function: function () { return !practicePassed; },
});

/* Formal intro */
timeline.push(instructionTrial(
  '热身结束，您做得很好!',
  '<div style="line-height:2">' +
    '<p style="font-size:36px;font-weight:bold;color:#1A1A2E;margin-bottom:16px">接下来正式开始游戏</p>' +
    '<p style="font-size:30px;color:#666;margin-bottom:12px">大约需要 <b>2 分钟</b></p>' +
    '<p style="font-size:30px;color:#666;margin-bottom:16px">这次按错不会提示，请坚持做完</p>' +
    '<div class="sart-rule-box nogo-rule" style="font-size:32px;margin-bottom:12px">' +
      '记住：看到 <span style="font-size:40px">3</span> 忍住不按!' +
    '</div>' +
    '<p style="font-size:28px;color:#888;margin-top:16px">深呼吸，保持专注</p>' +
  '</div>',
  '准备好了就按下方按钮',
  '我明白了，开始'
));

/* ---- Formal Phase: 1 block x 36 trials (9 digits x 4 reps) ---- */

/* Pre-generate all block sequences at page load */
var formalSequences = [];
for (var b = 0; b < CONFIG.formal.blocks; b++) {
  formalSequences.push(generateFormalSequence());
}

/* 3-2-1 倒计时 (黑底白字, 给主试+被试反应时间, 避免"点了开始立刻进入节奏"的猝不及防) */
for (var _c = 3; _c >= 1; _c--) {
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div style="font-size:14vh;color:#FFFFFF;font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">' + _c + '</div>',
    choices: 'NO_KEYS',
    trial_duration: 1000,
  });
}

for (var blockNum = 0; blockNum < CONFIG.formal.blocks; blockNum++) {
  (function (bn) {
    var blockLabel = 'formal_block' + (bn + 1);
    var seq = formalSequences[bn];

    timeline.push({
      type: jsPsychCallFunction,
      func: function () {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('block_start', { block: bn + 1, total_trials: seq.length });
        }
      },
    });

    seq.forEach(function (trialInfo) {
      buildSARTTrialNodes(trialInfo, blockLabel, false).forEach(function (n) {
        timeline.push(n);
      });
    });

    timeline.push({
      type: jsPsychCallFunction,
      func: function () {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('block_end', { block: bn + 1 });
        }
      },
    });

    /* Attention probe after each block */
    timeline.push(buildAttentionProbe(jsPsych, 'sart', 'end'));

    /* Break message between blocks (not after last) */
    if (bn < CONFIG.formal.blocks - 1) {
      timeline.push(instructionTrial(
        '休息一下',
        '<div style="line-height:2">' +
          '<p style="font-size:34px;color:#333">第 <b>' + (bn + 1) + '</b> / ' + CONFIG.formal.blocks + ' 组已完成</p>' +
          '<p style="font-size:30px;color:#888;margin-top:8px">准备好后按按钮继续</p>' +
        '</div>',
        '',
        '继续'
      ));
    }
  })(blockNum);
}

/* ---- Save data, camera stop, cleanup ---- */

timeline.push({
  type: jsPsychCallFunction,
  async: true,
  func: async function (done) {
    await saveData();
    try { await ParadigmCamera.stopAndSave(); } catch (e) { console.warn('[SART] camera stop error:', e); }
    done();
  },
});

/* Run (with camera init before jsPsych starts) */
(async function () {
  await ParadigmCamera.init('sart', subjectId);
  jsPsych.run(timeline);
})();
