/**
 * Interpersonal Distance Task (Web Battery)
 * --------------------------------------------------
 * Port of interpersonal_distance.py to jsPsych 8.
 *
 * Design:
 *   Two figures (self + other), other approaches the participant.
 *   Participant clicks "stop" button when uncomfortable.
 *   2 practice + 8 formal trials
 *   Conditions: gender(male/female) x relationship(stranger/friend) x side(left/right)
 *   Movement speed: 80px/s (scaled to viewport)
 *   Data: RT, final distance (pixels), response made
 *
 *   Uses the original PsychoPy character images (self.webp, male1/male2.webp,
 *   female1/female2.webp) from stimuli/interpersonal/ for figure rendering.
 */

/* ================================================================
   Config & Constants
   ================================================================ */

const MOVE_SPEED_BASE = 140; // px/s at reference width 2560（原80过慢，~25s过屏→~15s）
const REFERENCE_WIDTH = 2560;
const ITI_RANGE = [1000, 1500]; // ms

/* ================================================================
   URL Params & Utils
   ================================================================ */

function getUrlParams() {
  const p = new URLSearchParams(window.location.search);
  return {
    subjectId: p.get('sid') || '',
    sex: p.get('sex') || '男',
    session: p.get('session') || 'S001',
  };
}

function timestamp() {
  const d = new Date();
  const pad = function (n) { return String(n).padStart(2, '0'); };
  return d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + '_' + pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds());
}

function shuffleArray(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function randomInRange(min, max) {
  return min + Math.random() * (max - min);
}

/* ================================================================
   Checkpoint (inlined — non-module env)
   ================================================================ */

var _cpSaving = false;
var _cpLastSave = 0;
var _cpPending = false;
var _cpMinInterval = 5000;

var checkpoint = {
  _filename: '',
  _lsKey: '',
  _getDataFn: null,

  init: function (paradigm, sid, getDataFn) {
    this._filename = paradigm + '_' + sid + '_checkpoint.csv';
    this._lsKey = 'checkpoint_' + paradigm + '_' + sid;
    this._getDataFn = getDataFn;
  },

  _doSave: function () {
    if (_cpSaving) { _cpPending = true; return; }
    var csv = this._getDataFn ? this._getDataFn() : null;
    if (!csv) return;

    _cpSaving = true;
    _cpLastSave = Date.now();

    try { localStorage.setItem(this._lsKey, csv); } catch (e) { /* ignore */ }

    var self = this;
    fetch(window.location.origin + '/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        paradigm: 'interpersonal',
        subject_id: subjectId,
        filename: self._filename,
        content: csv,
      }),
    }).catch(function () {
      console.debug('[Checkpoint] interpersonal server save failed, localStorage backup exists');
    }).finally(function () {
      _cpSaving = false;
      if (_cpPending) { _cpPending = false; self._doSave(); }
    });
  },

  save: function () {
    var elapsed = Date.now() - _cpLastSave;
    if (elapsed < _cpMinInterval) {
      if (!_cpPending) {
        _cpPending = true;
        var self = this;
        setTimeout(function () {
          if (_cpPending) { _cpPending = false; self._doSave(); }
        }, _cpMinInterval - elapsed);
      }
      return;
    }
    this._doSave();
  },

  forceSave: function () {
    this._doSave();
  },

  clear: function () {
    try { localStorage.removeItem(this._lsKey); } catch (e) { /* ignore */ }
  },
};

/* ================================================================
   Data Collection
   ================================================================ */

const params = getUrlParams();
const subjectId = params.subjectId || 'TEST_' + Date.now();
const subjectSex = params.sex;

const trialRecords = [];

function recordTrial(trialType, trialNum, condition, rt, distance, responseMade) {
  const record = {
    subject_id: subjectId,
    sex: subjectSex,
    trial_type: trialType,
    trial_num: trialNum,
    other_gender: condition.other_gender,
    relationship: condition.relationship,
    self_side: condition.self_side,
    rt_ms: rt !== null ? Math.round(rt) : 0,
    rt: rt !== null ? (rt / 1000).toFixed(3) : '0.000',
    distance: distance !== null ? Math.round(distance) : 0,
    response_made: responseMade ? 1 : 0,
    accuracy: 1, // Always 1 for this task (no right/wrong)
    phase: trialType,
    timestamp_hms: new Date().toTimeString().split(' ')[0],
  };
  trialRecords.push(record);
  return record;
}

/* ================================================================
   Trial Conditions
   ================================================================ */

function buildPracticeTrials() {
  // 练习覆盖两种性别：trial1=陌生异性，trial2=朋友同性，避免两次都是同一性别
  var opposite = subjectSex === '男' ? 'female' : 'male';
  var same = subjectSex === '男' ? 'male' : 'female';
  return [
    { other_gender: opposite, relationship: 'stranger', self_side: 'left' },
    { other_gender: same,     relationship: 'friend',   self_side: 'right' },
  ];
}

function buildFormalTrials() {
  const conditions = [];
  ['male', 'female'].forEach(function (og) {
    ['stranger', 'friend'].forEach(function (rel) {
      ['left', 'right'].forEach(function (side) {
        conditions.push({ other_gender: og, relationship: rel, self_side: side });
      });
    });
  });
  return shuffleArray(conditions);
}

/* ================================================================
   Figure Rendering (Real character images)
   ================================================================ */

const STIMULI_BASE = '../../stimuli/interpersonal/';

/* Preload all character images */
['self.webp', 'self_female.webp', 'male1.webp', 'male2.webp', 'female1.webp', 'female2.webp'].forEach(function (name) {
  var img = new Image();
  img.src = STIMULI_BASE + name;
});

function getFigureImageSrc(type, gender, relationship) {
  if (type === 'self') {
    return STIMULI_BASE + (subjectSex === '女' ? 'self_female.webp' : 'self.webp');
  }
  /* other: male1/male2, female1/female2 (1 = stranger, 2 = friend) */
  var suffix = relationship === 'stranger' ? '1' : '2';
  return STIMULI_BASE + gender + suffix + '.webp';
}

function getFigureHTML(type, gender, relationship) {
  var src = getFigureImageSrc(type, gender, relationship);
  var label = '';
  if (type === 'self') {
    label = '我';
  } else {
    label = relationship === 'stranger'
      ? (gender === 'male' ? '陌生男' : '陌生女')
      : (gender === 'male' ? '朋友(男)' : '朋友(女)');
  }
  return '<div class="figure-character">' +
    '<img src="' + src + '" class="figure-img" draggable="false" alt="' + label + '">' +
    '<div class="figure-label">' + label + '</div>' +
    '</div>';
}

/* ================================================================
   Interactive Trial (Canvas-based animation)
   ================================================================ */

/**
 * Run a single interpersonal distance trial using requestAnimationFrame.
 * This is done as a custom jsPsych plugin-like function wrapped in
 * html-keyboard-response with manual DOM control.
 *
 * Returns a Promise that resolves with { rt, distance, responseMade }.
 */
function runAnimatedTrial(displayElement, condition, trialLabel, trialNum, totalTrials) {
  return new Promise(function (resolve) {
    const screenW = window.innerWidth;
    const screenH = window.innerHeight;
    const scale = screenW / REFERENCE_WIDTH;
    const moveSpeed = MOVE_SPEED_BASE * scale; // px/s scaled

    /* Positions */
    const selfX = condition.self_side === 'left' ? screenW * 0.1 : screenW * 0.9;
    const otherStartX = condition.self_side === 'left' ? screenW * 0.9 : screenW * 0.1;
    const moveDir = condition.self_side === 'left' ? -1 : 1;

    /* Figure width for centering (half of rendered figure width) */
    var figImgH = Math.min(screenH * 0.38, 450);
    var figHalfW = Math.round(figImgH * (1100 / 1673) / 2);

    /* Build scene HTML */
    const sceneHTML =
      '<div class="task-scene" id="ipd-scene">' +
      '<div class="trial-counter">' + trialLabel + ' ' + trialNum + '/' + totalTrials + '</div>' +
      '<div id="ipd-self" style="position:absolute;top:50%;transform:translateY(-50%);left:' + (selfX - figHalfW) + 'px">' +
      getFigureHTML('self', subjectSex === '男' ? 'male' : 'female', '') +
      '</div>' +
      '<div id="ipd-other" style="position:absolute;top:50%;transform:translateY(-50%);left:' + (otherStartX - figHalfW) + 'px">' +
      getFigureHTML('other', condition.other_gender, condition.relationship) +
      '</div>' +
      '<div class="stop-btn-area">' +
      '<button class="stop-btn" id="ipd-stop-btn">停</button>' +
      '</div>' +
      '</div>';

    displayElement.innerHTML = sceneHTML;

    const otherEl = document.getElementById('ipd-other');
    const stopBtn = document.getElementById('ipd-stop-btn');

    let responseMade = false;
    let rt = null;
    let finalDistance = null;
    let startTime = null;
    let animFrame = null;
    let currentX = otherStartX;

    function getCurrentDistance() {
      return Math.abs(selfX - currentX);
    }

    /* Stop handler */
    function onStop() {
      if (responseMade) return;
      responseMade = true;
      // 优先用 pointerdown 时刻（认知决策时间），fallback 到 pointerup 时刻
      if (window.__touchRT && window.__touchRT.downTime != null) {
        rt = window.__touchRT.downTime - startTime;
      } else {
        rt = performance.now() - startTime;
      }
      finalDistance = getCurrentDistance();
      if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
        ParadigmCamera.addEvent('stop_pressed', { trial_index: trialNum, distance_px: Math.round(finalDistance), rt: Math.round(rt) });
      }
      stopBtn.style.background = '#999';
      stopBtn.style.transform = 'scale(0.95)';

      /* Hold for 500ms then resolve */
      setTimeout(function () {
        if (animFrame) cancelAnimationFrame(animFrame);
        document.removeEventListener('keydown', onKeyDown);
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('trial_end', { trial_index: trialNum });
        }
        resolve({ rt: rt, distance: finalDistance, responseMade: true });
      }, 500);
    }

    if (typeof TouchHardening !== 'undefined') {
      // mouseAlso:true 确保鼠标和触控笔都能触发（电脑测试 + 平板均有效）
      // trackRT:true 记录 pointerdown 时刻，用于 RT 校正（按下=认知决策时刻）
      TouchHardening.setupButton(stopBtn, onStop, { trackRT: true, debounce: false, mouseAlso: true });
    } else {
      stopBtn.addEventListener('click', onStop);
    }

    /* Keyboard fallback */
    function onKeyDown(e) {
      if (e.key === ' ' || e.code === 'Space') {
        e.preventDefault();
        onStop();
      }
      if (e.key === 'Escape') {
        if (animFrame) cancelAnimationFrame(animFrame);
        resolve({ rt: null, distance: null, responseMade: false });
      }
    }
    document.addEventListener('keydown', onKeyDown);

    /* Animation loop */
    function animate(ts) {
      if (!startTime) startTime = ts;
      const elapsed = (ts - startTime) / 1000; // seconds

      if (!responseMade) {
        const moveDistance = moveSpeed * elapsed;
        currentX = otherStartX + moveDir * moveDistance;
        otherEl.style.left = (currentX - figHalfW) + 'px';

        /* Check if other has reached self position */
        if ((moveDir === -1 && currentX <= selfX) || (moveDir === 1 && currentX >= selfX)) {
          responseMade = true;
          rt = (ts - startTime);
          finalDistance = 0;
          setTimeout(function () {
            cancelAnimationFrame(animFrame);
            document.removeEventListener('keydown', onKeyDown);
            if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
              ParadigmCamera.addEvent('trial_end', { trial_index: trialNum });
            }
            resolve({ rt: rt, distance: 0, responseMade: true });
          }, 500);
          return;
        }
      }

      if (!responseMade) animFrame = requestAnimationFrame(animate);
    }

    /* Initial pause (500ms) before movement starts */
    setTimeout(function () {
      if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
        ParadigmCamera.addEvent('trial_start', {
          trial_index: trialNum,
          character: condition.other_gender + '_' + condition.relationship,
          side: condition.self_side,
          phase: trialLabel
        });
      }
      animFrame = requestAnimationFrame(animate);
    }, 500);

    /* Cleanup handler */
    window._ipdCleanup = function () {
      if (animFrame) cancelAnimationFrame(animFrame);
      document.removeEventListener('keydown', onKeyDown);
    };
  });
}

/* ================================================================
   CSV Export
   ================================================================ */

function generateCSV() {
  const BOM = '\uFEFF';
  const fields = [
    'subject_id', 'sex', 'trial_type', 'trial_num', 'other_gender',
    'relationship', 'self_side', 'rt', 'rt_ms', 'distance',
    'response_made', 'accuracy', 'phase', 'timestamp_hms',
  ];
  let csv = BOM + fields.join(',') + '\n';
  trialRecords.forEach(function (r) {
    csv += fields.map(function (f) {
      var v = r[f];
      if (v === undefined || v === null) return '';
      return String(v);
    }).join(',') + '\n';
  });
  return csv;
}

/* Init checkpoint now that generateCSV is available */
checkpoint.init('interpersonal', subjectId, generateCSV);

function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType || 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
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
  const ts = timestamp();
  const filename = 'IPD_' + subjectId + '_' + ts + '.csv';
  const csvContent = generateCSV();

  if (typeof LocalPack !== 'undefined') {
    LocalPack.add(filename, csvContent);
  }

  let serverOk = false;
  try {
    const resp = await safeFetch(window.location.origin + '/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paradigm: 'interpersonal', subject_id: subjectId, filename: filename, content: csvContent }),
    });
    if (!resp.ok) throw new Error('server error');
    serverOk = true;
  } catch (e) {
    console.warn('[Interpersonal] server save failed, LocalPack has backup:', e);
  }

  // localStorage 兜底:服务器成功就清(防跨被试累积),失败才留
  try {
    if (serverOk) localStorage.removeItem('ipd_backup_' + subjectId);
    else localStorage.setItem('ipd_backup_' + subjectId, csvContent);
  } catch (e) { /* ignore */ }
}

/* ================================================================
   jsPsych Init
   ================================================================ */

const jsPsych = initJsPsych({
  display_element: 'jspsych-target',
});

/* ================================================================
   HTML Builders
   ================================================================ */

function makeInstructionHTML(title, body, hint) {
  hint = hint || '';
  return '<div class="instruction-page" style="height:auto;min-height:calc(100vh - 160px);padding-bottom:0">' +
    '<div class="instruction-title">' + title + '</div>' +
    '<div class="instruction-body">' + body + '</div>' +
    (hint ? '<div style="margin-top:24px;font-size:24px;color:var(--text-secondary)">' + hint + '</div>' : '') +
    '</div>';
}

function instructionTrial(title, body, hint) {
  return {
    type: jsPsychHtmlButtonResponse,
    stimulus: makeInstructionHTML(title, body, hint),
    choices: ['继续'],
    button_html: function (choice) {
      return '<button class="jspsych-btn" style="margin:20px auto;min-height:96px">' + choice + '</button>';
    },
  };
}

/* ================================================================
   Build Timeline
   ================================================================ */

const timeline = [];

/* --- Instruction 1 --- */
timeline.push(instructionTrial(
  '人际距离',
  '屏幕上会出现两个人<br><br>' +
  '一个代表您自己<br>另一个人会慢慢向您走来'
));

/* --- Instruction 2 --- */
timeline.push(instructionTrial(
  '您只需要做一件事',
  '当对方走得<b>太近</b>，让您不舒服时<br><br>' +
  '请点屏幕下方的 <b>"停"</b> 按钮<br><br>' +
  '没有对错，按您的真实感觉就好'
));

/* --- Practice intro --- */
timeline.push(instructionTrial(
  '先来练习一下',
  '对方向您走来时<br>觉得太近了就点 <b>"停"</b>',
  ''
));

/* ================================================================
   Practice Trials (2 trials)
   ================================================================ */

const practiceConditions = buildPracticeTrials();

practiceConditions.forEach(function (condition, idx) {
  /* Fixation */
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div class="fixation-screen">+</div>',
    choices: 'NO_KEYS',
    trial_duration: 1000,
  });

  /* Animated trial */
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div id="ipd-trial-container" style="width:100vw;height:100vh"></div>',
    choices: 'NO_KEYS',
    trial_duration: null, // controlled by our animation
    on_load: function () {
      var container = document.getElementById('ipd-trial-container');
      if (!container) container = jsPsych.getDisplayElement();
      runAnimatedTrial(container, condition, '练习', idx + 1, practiceConditions.length)
        .then(function (result) {
          recordTrial('practice', idx + 1, condition, result.rt, result.distance, result.responseMade);
          checkpoint.save();
          jsPsych.finishTrial();
        });
    },
  });

  /* ITI */
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div class="fixation-screen">+</div>',
    choices: 'NO_KEYS',
    trial_duration: Math.round(randomInRange(ITI_RANGE[0], ITI_RANGE[1])),
  });
});

/* --- Checkpoint: force save after practice, before formal --- */
timeline.push({
  type: jsPsychCallFunction,
  func: function () { checkpoint.forceSave(); },
});

/* --- Formal intro --- */
timeline.push(instructionTrial(
  '正式开始',
  '练习结束，做得很好！<br><br>' +
  '接下来共 8 次，方法一样<br>觉得太近了就点 <b>"停"</b>'
));

/* ================================================================
   Formal Trials (8 trials)
   ================================================================ */

const formalConditions = buildFormalTrials();

formalConditions.forEach(function (condition, idx) {
  /* Fixation */
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div class="fixation-screen">+</div>',
    choices: 'NO_KEYS',
    trial_duration: 1000,
  });

  /* Animated trial */
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div id="ipd-trial-container" style="width:100vw;height:100vh"></div>',
    choices: 'NO_KEYS',
    trial_duration: null,
    on_load: function () {
      var container = document.getElementById('ipd-trial-container');
      if (!container) container = jsPsych.getDisplayElement();
      runAnimatedTrial(container, condition, '试次', idx + 1, formalConditions.length)
        .then(function (result) {
          recordTrial('formal', idx + 1, condition, result.rt, result.distance, result.responseMade);
          checkpoint.save();
          jsPsych.finishTrial();
        });
    },
  });

  /* ITI */
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: '<div class="fixation-screen">+</div>',
    choices: 'NO_KEYS',
    trial_duration: Math.round(randomInRange(ITI_RANGE[0], ITI_RANGE[1])),
  });
});

/* ================================================================
   注意力探针（正式试次结束后）
   ================================================================ */

timeline.push(buildAttentionProbe(jsPsych, 'interpersonal', 'end'));

/* ================================================================
   End
   ================================================================ */

timeline.push({
  type: jsPsychCallFunction,
  async: true,
  func: function (done) {
    Promise.resolve()
      .then(function () { return ParadigmCamera.stopAndSave(); })
      .catch(function () { /* camera optional */ })
      .then(function () { return saveData(); })
      .then(function () { checkpoint.clear(); done(); })
      .catch(function () { checkpoint.clear(); done(); });
  },
});

timeline.push({
  type: jsPsychCallFunction,
  func: function () {
    showEndScreen('interpersonal', subjectId);
  },
});

/* Run */
(async function () {
  try {
    await ParadigmCamera.init('interpersonal', subjectId);
  } catch (e) {
    console.warn('[interpersonal] camera init skipped:', e.message);
  }
  jsPsych.run(timeline);
})();
