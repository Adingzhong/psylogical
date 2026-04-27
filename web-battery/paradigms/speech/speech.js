/**
 * Speech Assessment / VFT (Web Battery)
 * --------------------------------------------------
 * Based on PPT paradigm structure:
 *   1. Semantic Fluency   (categories: animals, fruits)
 *   2. Verbal Fluency Test (characters: 书, 水)
 *   3. Action Fluency     (locations: 公园, 厨房)
 *   4. Scene Description  (Cookie Theft + Chinese scenes)
 *   5. Reading Tasks      (number grid, poems)
 *
 * NO timers / countdowns - all manual "next" button
 * Recording: MediaRecorder API (audio/webm)
 * Fallback: graceful degradation if microphone unavailable
 * Data: CSV trial log + audio blobs uploaded to /api/upload
 */

/* ================================================================
   Config
   ================================================================ */

/* Stimuli image base path (relative to HTML) */
var STIM_BASE = '../../stimuli/speech/';

/* ================================================================
   Task definitions matching PPT slides
   ================================================================ */

/* Task 1: Semantic Fluency (slides 2-3) */
var SEMANTIC_FLUENCY_ITEMS = [
  { id: 1, category: '蔬菜', image: 'slide02_img001.webp?v=20260416c', prompt: '有哪些种类的蔬菜？' },
  { id: 2, category: '水果', image: 'slide03_img002.webp', prompt: '有哪些种类的水果？' },
];

/* Task 2: Verbal Fluency Test / VFT (slides 4-6) */
var VFT_ITEMS = [
  { id: 1, character: '书', image: 'slide05_img004.webp', prompt: '说出所有包含这个字的词' },
  { id: 2, character: '水', image: 'slide06_img005.webp', prompt: '说出所有包含这个字的词' },
];

/* Task 3: Action Fluency (slides 7-9) */
var ACTION_FLUENCY_ITEMS = [
  { id: 1, location: '公园', image: 'slide08_img007.webp', prompt: '大声说出，我们可以在这里干嘛' },
  { id: 2, location: '厨房', image: 'slide09_img008.webp', prompt: '大声说出，我们可以在这里干嘛' },
];

/* Task 4: Scene Description (slides 10-11) */
var SCENE_ITEMS = [
  { id: 1, name: 'cookie_theft_western',  image: 'slide10_img009.webp', prompt: '详细描述这张图片' },
  { id: 2, name: 'cao_chong_weighing',    image: 'slide11_img011.webp', prompt: '详细描述这张图片' },
];

/* Task 5: Reading (slides 14-16) */
var READING_ITEMS = [
  { id: 1, name: 'number_grid', image: 'slide14_img019.webp', prompt: '大声朗读上面的内容' },
  { id: 2, name: 'jing_ye_si',  image: 'slide15_img020.webp', prompt: '大声朗读上面的这首诗' },
  { id: 3, name: 'chun_xiao',   image: 'slide16_img021.webp', prompt: '大声朗读上面的这首诗' },
];

/* ================================================================
   URL Params
   ================================================================ */

function getUrlParams() {
  var p = new URLSearchParams(window.location.search);
  return {
    subjectId: p.get('sid') || '',
    session: p.get('session') || 'S001',
  };
}

function timestamp() {
  var d = new Date();
  var pad = function(n) { return String(n).padStart(2, '0'); };
  return d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + '_' +
         pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds());
}

var params = getUrlParams();
var subjectId = params.subjectId || 'TEST_' + Date.now();

/* ================================================================
   F4 (2026-04-19): Block-level resume
   block 0 = semantic_fluency, 1 = verbal_fluency, 2 = action_fluency,
   3 = scene_description, 4 = reading
   ================================================================ */
var START_BLOCK = 0;
var SKIP_INSTRUCTIONS = false;
if (window.ProgressAPI && window.ProgressAPI.getResumeParams) {
  var _rp = window.ProgressAPI.getResumeParams();
  START_BLOCK = _rp.startBlock;
  SKIP_INSTRUCTIONS = _rp.skipInstructions;
}
var SPEECH_TOTAL_BLOCKS = 5;
if (START_BLOCK >= SPEECH_TOTAL_BLOCKS) {
  console.warn('[speech] startBlock', START_BLOCK, '>= totalBlocks, falling back to 0');
  START_BLOCK = 0;
  SKIP_INSTRUCTIONS = false;
  if (window.ProgressAPI) window.ProgressAPI.clear('speech', subjectId);
}
window.__paradigmName = 'speech';
window.__subjectId = subjectId;
window.__totalBlocks = SPEECH_TOTAL_BLOCKS;
window.__currentBlockIdx = START_BLOCK;
window.__blockOrder = ['semantic_fluency','verbal_fluency','action_fluency','scene_description','reading'];
window.__balance = null;

// F4: 写 progress 的 trial
function speechWriteProgressTrial(blockIdx) {
  if (!window.ProgressAPI || !window.ProgressAPI.write) return null;
  return {
    type: jsPsychCallFunction,
    func: function() {
      window.ProgressAPI.write('speech', subjectId, {
        lastCompletedBlockIdx: blockIdx,
        totalBlocks: SPEECH_TOTAL_BLOCKS,
        blockOrder: window.__blockOrder,
      });
      window.__currentBlockIdx = blockIdx + 1;
    },
  };
}

/* ================================================================
   Microphone & Recording
   ================================================================ */

var micAvailable = false;
var mediaStream = null;

/** Attempt to get microphone access. Returns true if available. */
async function initMicrophone() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    console.warn('Microphone unavailable: mediaDevices missing, likely non-HTTPS context');
    micAvailable = false;
    return false;
  }

  try {
    /* On Surface tablets, specify constraints that work reliably */
    var constraints = {
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: { ideal: 44100 },
      }
    };
    mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
    micAvailable = true;
    return true;
  } catch (e) {
    console.warn('Microphone not available:', e.message);
    /* Retry with basic constraints (fallback for older browsers/devices) */
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micAvailable = true;
      return true;
    } catch (e2) {
      console.warn('Microphone fallback also failed:', e2.message);
      micAvailable = false;
      return false;
    }
  }
}

/**
 * Create a recorder session.
 * Returns { start, stop, getBlob } or null if mic unavailable.
 */
function createRecorder() {
  if (!micAvailable || !mediaStream) return null;

  /* Ensure the stream is still active */
  var tracks = mediaStream.getAudioTracks();
  if (!tracks.length || tracks[0].readyState === 'ended') {
    console.warn('Audio track ended, cannot create recorder');
    return null;
  }

  var chunks = [];
  /* Try multiple MIME types for Surface compatibility */
  var mimeType = '';
  var candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg', 'audio/mp4'];
  for (var i = 0; i < candidates.length; i++) {
    if (MediaRecorder.isTypeSupported(candidates[i])) {
      mimeType = candidates[i];
      break;
    }
  }
  var options = mimeType ? { mimeType: mimeType } : {};
  var recorder;
  try {
    recorder = new MediaRecorder(mediaStream, options);
  } catch (e) {
    console.warn('MediaRecorder creation failed:', e);
    return null;
  }

  recorder.ondataavailable = function(ev) {
    if (ev.data && ev.data.size > 0) chunks.push(ev.data);
  };

  return {
    start: function() { chunks = []; recorder.start(1000); },
    stop: function() {
      return new Promise(function(resolve) {
        recorder.onstop = function() {
          var blob = new Blob(chunks, { type: mimeType || 'audio/webm' });
          resolve(blob);
        };
        if (recorder.state === 'recording') {
          recorder.stop();
        } else {
          resolve(new Blob([], { type: mimeType || 'audio/webm' }));
        }
      });
    },
    getState: function() { return recorder.state; },
  };
}

/** Save audio: local download + server upload in parallel */
async function uploadAudio(blob, filename) {
  if (typeof LocalPack !== 'undefined') {
    LocalPack.add(filename, blob);
  }
  // 音频已注册到LocalPack，showEndScreen的ZIP统一打包下载。
  // 不再单独a.click()下载——Edge会拦截连续多次下载。
  // 2. Also upload to server (async, best-effort)
  try {
    var formData = new FormData();
    formData.append('file', blob, filename);
    formData.append('subject_id', subjectId);
    formData.append('paradigm', 'speech');
    var resp = await fetch(window.location.origin + '/api/upload', {
      method: 'POST',
      body: formData,
    });
    if (resp.ok) {
      console.log('[Speech] audio also uploaded to server');
      return { success: true };
    }
  } catch (e) {
    console.warn('[Speech] server upload failed (local copy saved):', e);
  }
  return { success: true, local: true };
}

/* ================================================================
   Data Collection
   ================================================================ */

var trialRecords = [];
var audioFiles = [];

function recordTrial(taskType, itemId, itemName, durationMs, recorded, audioFilename) {
  var rec = {
    subject_id: subjectId,
    task_type: taskType,
    item_id: itemId,
    item_name: itemName,
    duration_ms: Math.round(durationMs),
    mic_available: micAvailable ? 1 : 0,
    recorded: recorded ? 1 : 0,
    audio_filename: audioFilename || '',
    timestamp_iso: new Date().toISOString(),
  };
  trialRecords.push(rec);
  return rec;
}

/* ================================================================
   Checkpoint (incremental save) — inline since not using ES modules
   ================================================================ */

var _ckpt = (function () {
  var saving = false, lastTime = 0, pending = false, timer = null;
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
          clearTimeout(timer);
          timer = setTimeout(function () { if (pending) { pending = false; doSave(); } }, MIN - elapsed);
        }
        return;
      }
      doSave();
    },
    forceSave: function () { clearTimeout(timer); pending = false; doSave(); },
    clear: function () {
      clearTimeout(timer);
      try { localStorage.removeItem('checkpoint_' + paradigm + '_' + sid); } catch (e) { /* ignore */ }
    },
  };
})();

/* Initialize checkpoint — uses generateCSV (defined below) via lazy reference */
_ckpt.init('speech', subjectId, function () { return generateCSV(); });

/* ================================================================
   CSV Export
   ================================================================ */

function generateCSV() {
  var BOM = '\uFEFF';
  var fields = [
    'subject_id', 'task_type', 'item_id', 'item_name',
    'duration_ms', 'mic_available', 'recorded', 'audio_filename', 'timestamp_iso',
  ];
  var csv = BOM + fields.join(',') + '\n';
  trialRecords.forEach(function(r) {
    csv += fields.map(function(f) {
      var v = r[f];
      if (v === undefined || v === null) return '';
      var s = String(v);
      if (s.indexOf(',') >= 0 || s.indexOf('"') >= 0) {
        return '"' + s.replace(/"/g, '""') + '"';
      }
      return s;
    }).join(',') + '\n';
  });
  return csv;
}

var _dataSaved = false;

async function saveData() {
  if (_dataSaved) return;
  _dataSaved = true;

  var ts = timestamp();
  var filename = 'Speech_' + subjectId + '_' + ts + '.csv';
  var csvContent = generateCSV();

  // F4 (2026-04-19): 续写场景合并上次 CSV
  if (window.ProgressAPI && window.ProgressAPI.getPrior) {
    var priorCSV = window.ProgressAPI.getPrior('speech', subjectId);
    if (priorCSV) {
      csvContent = window.ProgressAPI.merge(priorCSV, csvContent);
      console.log('[Speech] merged prior CSV,final rows:', csvContent.split('\n').length - 2);
    }
  }

  if (typeof LocalPack !== 'undefined') {
    LocalPack.add(filename, csvContent);
  }

  var serverOk = false;
  try {
    var resp = await safeFetch(window.location.origin + '/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        paradigm: 'speech',
        subject_id: subjectId,
        filename: filename,
        content: csvContent,
      }),
    });
    if (!resp.ok) throw new Error('server error');
    serverOk = true;
  } catch (e) {
    console.warn('[Speech] server save failed, LocalPack has backup:', e);
  }

  // localStorage 兜底:服务器成功就清(防跨被试累积),失败才留
  try {
    if (serverOk) localStorage.removeItem('speech_backup_' + subjectId);
    else localStorage.setItem('speech_backup_' + subjectId, csvContent);
  } catch (e) { /* ignore */ }
}

/* ================================================================
   Instruction Helpers
   ================================================================ */

function makeInstructionHTML(title, body, hint) {
  var hintHTML = hint ? '<div style="margin-top:12px;font-size:24px;color:var(--text-secondary);font-style:italic">' + hint + '</div>' : '';
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
    choices: ['继续'],
    button_html: function(choice) {
      return '<button class="jspsych-btn instr-continue-btn">' + choice + '</button>';
    },
  };
}

/* Instruction trial that shows a PPT image as the instruction */
function imageInstructionTrial(imageSrc, title) {
  return {
    type: jsPsychHtmlButtonResponse,
    stimulus: '<div class="instr-page">' +
      (title ? '<div class="instr-title">' + title + '</div>' : '') +
      '<div style="margin:12px 0"><img src="' + STIM_BASE + imageSrc + '" ' +
      'style="max-width:850px;max-height:50vh;border-radius:16px;border:2px solid var(--border)" /></div>' +
      '</div>',
    choices: ['继续'],
    button_html: function(choice) {
      return '<button class="jspsych-btn instr-continue-btn">' + choice + '</button>';
    },
  };
}

/* ================================================================
   Recording Indicator UI (音量条 + 正计时 + 目标提示)
   ================================================================ */

// isActive: 麦克风可用;showGoal: 是否显示"/60s"目标(朗读任务传 false)
function recIndicatorHTML(isActive, showGoal) {
  if (isActive) {
    var goalSuffix = showGoal ? '<span class="rec-goal" id="recGoal"> / 60s</span>' : '';
    return '<div class="rec-indicator" id="recIndicator">' +
      '<div class="rec-dot"></div>' +
      '<span class="rec-label">录音中</span>' +
      '<span class="rec-timer" id="recTimer">0s</span>' +
      goalSuffix +
      '<canvas class="rec-volume" id="recVolume" width="80" height="18"></canvas>' +
      '</div>';
  }
  return '<div class="rec-indicator inactive" id="recIndicator">' +
    '<div class="rec-dot"></div>' +
    '<span class="rec-label">麦克风不可用（数据仍在记录）</span>' +
    '</div>';
}

var _recTimerInterval = null;
var _recStartTime = 0;
var _goalReached = false;

// 正计时 — 到 60s 时目标后缀变绿打勾
function startRecTimer() {
  _recStartTime = Date.now();
  _goalReached = false;
  _recTimerInterval = setInterval(function() {
    var el = document.getElementById('recTimer');
    var goal = document.getElementById('recGoal');
    if (el) {
      var elapsed = Math.floor((Date.now() - _recStartTime) / 1000);
      el.textContent = elapsed + 's';
      if (goal && elapsed >= 60 && !_goalReached) {
        _goalReached = true;
        goal.textContent = ' / 60s ✓';
        goal.style.color = '#2E7D32';
      }
    }
  }, 200);
}

function stopRecTimer() {
  if (_recTimerInterval) {
    clearInterval(_recTimerInterval);
    _recTimerInterval = null;
  }
}

/* ================================================================
   音量可视化 (让主试随时确认麦克风正常收音)
   ================================================================ */
var _audioCtx = null;
var _analyser = null;
var _volumeRAF = null;

function setupAnalyser() {
  if (_analyser || !mediaStream) return;
  try {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    _audioCtx = new AC();
    var source = _audioCtx.createMediaStreamSource(mediaStream);
    _analyser = _audioCtx.createAnalyser();
    _analyser.fftSize = 256;
    _analyser.smoothingTimeConstant = 0.5;
    source.connect(_analyser);
  } catch (e) {
    console.warn('Audio analyser setup failed:', e);
    _analyser = null;
  }
}

function startVolumeMeter() {
  setupAnalyser();
  if (!_analyser) return;
  var canvas = document.getElementById('recVolume');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var W = canvas.width, H = canvas.height;
  var data = new Uint8Array(_analyser.fftSize);

  function draw() {
    _analyser.getByteTimeDomainData(data);
    // RMS 计算(0-1)
    var sum = 0;
    for (var i = 0; i < data.length; i++) {
      var n = (data[i] - 128) / 128;
      sum += n * n;
    }
    var rms = Math.sqrt(sum / data.length);
    var level = Math.min(rms * 4, 1);  // 放大 4x,说话正常大小刚好满格
    // 画背景 + 条
    ctx.fillStyle = '#E0E0E0';
    ctx.fillRect(0, 0, W, H);
    var barW = W * level;
    // 颜色:静 → 灰,小声 → 黄,正常 → 绿
    ctx.fillStyle = level > 0.25 ? '#43A047' : level > 0.05 ? '#FB8C00' : '#BDBDBD';
    ctx.fillRect(0, 0, barW, H);
    _volumeRAF = requestAnimationFrame(draw);
  }
  draw();
}

function stopVolumeMeter() {
  if (_volumeRAF) cancelAnimationFrame(_volumeRAF);
  _volumeRAF = null;
}

/* ================================================================
   麦克风收音测试 (2026-04-19 加)
   在 Speech 指导语后、第一项任务前插一个测试页:
     - 大画布显示音量条
     - 初始按钮 disabled
     - 检测到 volume > 阈值持续 500ms → 启用按钮
   目的: 防止 "getUserMedia 成功但实际不收音" (麦克风被其他应用占/系统静音)
   ================================================================ */
var _micTestRAF = null;

function startMicTestMeter() {
  setupAnalyser();
  if (!_analyser) return;
  var canvas = document.getElementById('micTestMeter');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var data = new Uint8Array(_analyser.fftSize);
  var W = canvas.width, H = canvas.height;
  var loudStartMs = null;
  // 门槛尽量宽松:正常轻声说话就能过
  var RMS_THRESHOLD = 0.008;   // 非常低,小声哼一下都能过
  var REQUIRED_HOLD_MS = 300;  // 0.3 秒 (之前 0.5 太久)
  var VISUAL_GAIN = 15;        // 视觉放大 15x,小声也能看到条明显跳

  function draw() {
    _analyser.getByteTimeDomainData(data);
    var sum = 0;
    for (var i = 0; i < data.length; i++) {
      var n = (data[i] - 128) / 128;
      sum += n * n;
    }
    var rms = Math.sqrt(sum / data.length);
    var level = Math.min(rms * VISUAL_GAIN, 1);
    // 画条
    ctx.fillStyle = '#E0E0E0';
    ctx.fillRect(0, 0, W, H);
    // 颜色阈值也放宽: 很小声就能变绿
    ctx.fillStyle = level > 0.12 ? '#43A047' : level > 0.04 ? '#FB8C00' : '#BDBDBD';
    ctx.fillRect(0, 0, W * level, H);

    // 持续检测 — 阈值低 + 持续时间短,主试说一两句就过
    if (rms > RMS_THRESHOLD) {
      if (loudStartMs === null) loudStartMs = Date.now();
      else if (Date.now() - loudStartMs >= REQUIRED_HOLD_MS) {
        var btn = document.getElementById('micTestConfirm');
        var status = document.getElementById('micTestStatus');
        if (btn && btn.disabled) {
          btn.disabled = false;
          btn.style.opacity = '1';
          if (status) {
            status.textContent = '已检测到声音,可以继续';
            status.style.color = '#43A047';
          }
        }
      }
    } else {
      loudStartMs = null;
    }
    _micTestRAF = requestAnimationFrame(draw);
  }
  draw();
}

function stopMicTestMeter() {
  if (_micTestRAF) cancelAnimationFrame(_micTestRAF);
  _micTestRAF = null;
}

/* ================================================================
   Generic recording trial builder (NO countdown, manual advance)
   ================================================================ */

/**
 * Build a trial that shows an image stimulus, records audio,
 * and waits for the participant to click "下一个" / "完成".
 *
 * @param {object} opts
 *   taskType:    string   - e.g. 'semantic_fluency'
 *   itemId:      number
 *   itemName:    string
 *   imageSrc:    string   - filename under STIM_BASE
 *   prompt:      string   - bottom prompt text
 *   taskLabel:   string   - top-left label e.g. "语义流畅性 1/2"
 *   buttonLabel: string   - button text, default "下一个"
 *   imgStyle:    string   - optional extra CSS for img
 *   totalItems:  number   - total items in this task (for progress bar)
 *   currentIdx:  number   - 0-based index (for progress bar)
 */
function buildRecordingTrial(opts) {
  var _rec = null;
  var _startTime = 0;

  var progress = opts.totalItems ? Math.round(((opts.currentIdx + 1) / opts.totalItems) * 100) : 0;
  var imgStyle = opts.imgStyle || 'max-width:800px;max-height:48vh;border-radius:16px;border:2px solid var(--border)';
  // 朗读任务已知时长,不显示 60s 目标;流畅性/场景描述显示(让老人尽量说到 1 分钟)
  var showGoal = opts.taskType !== 'reading';

  return {
    type: jsPsychHtmlButtonResponse,
    stimulus: function() {
      return (opts.totalItems ? '<div class="speech-progress" style="width:' + progress + '%"></div>' : '') +
        '<div class="speech-container">' +
        '<div class="speech-task-label">' + (opts.taskLabel || '') + '</div>' +
        (showGoal ? '<div class="speech-duration-hint">尽可能说够一分钟</div>' : '') +
        '<div class="speech-stimulus">' +
        '<img src="' + STIM_BASE + opts.imageSrc + '" style="' + imgStyle + '" />' +
        '<div class="naming-prompt" style="margin-top:8px">' + opts.prompt + '</div>' +
        '</div>' +
        recIndicatorHTML(micAvailable, showGoal) +
        '</div>';
    },
    choices: [opts.buttonLabel || '下一个'],
    button_html: function(choice) {
      return '<button class="jspsych-btn" style="margin-top:10px">' + choice + '</button>';
    },
    /* NO trial_duration — fully manual */
    response_ends_trial: true,
    data: { task: opts.taskType, item_id: opts.itemId, item_name: opts.itemName },
    on_load: function() {
      _rec = createRecorder();
      _startTime = Date.now();
      if (_rec) {
        _rec.start();
      }
      startRecTimer();
      startVolumeMeter();  // 启动音量可视化(让主试确认麦克风正常)

      /* -----------------------------------------------------------
       * Surface 触屏 ghost-click 防护
       * -----------------------------------------------------------
       * Surface/Edge 上,上一个 trial 触摸结束后,浏览器会在 ~300ms 时
       * 合成一个原生 click 事件,恰好落到新 trial 刚 render 的按钮上,
       * 导致"点一下前进 2 个试次"。
       * 这里在新 trial 加载后的前 700ms 拦截任何 click 事件,让幽灵点击
       * 掉进真空。700ms 之后恢复正常。
       * ---------------------------------------------------------- */
      var _loadTime = Date.now();
      var _btngroup = document.getElementById('jspsych-html-button-response-btngroup');
      if (_btngroup) {
        _btngroup.addEventListener('click', function (e) {
          if (Date.now() - _loadTime < 700) {
            e.stopImmediatePropagation();
            e.preventDefault();
          }
        }, true);  // capture 阶段,赶在 jsPsych 的 handler 之前
      }

      /* ParadigmCamera event: recording item start */
      if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
        ParadigmCamera.addEvent('recording_item_start', { task_type: opts.taskType, item_id: opts.itemId, item_name: opts.itemName });
      }
    },
    on_finish: function(data) {
      stopRecTimer();
      stopVolumeMeter();
      var durationMs = Date.now() - _startTime;
      var ext = 'webm';
      var audioFilename = opts.taskType + '_' + subjectId + '_item' + opts.itemId + '_' + timestamp() + '.' + ext;

      if (_rec) {
        _rec.stop().then(function(blob) {
          if (blob.size > 0) {
            uploadAudio(blob, audioFilename);
            audioFiles.push(audioFilename);
          }
        });
        recordTrial(opts.taskType, opts.itemId, opts.itemName, durationMs, true, audioFilename);
      } else {
        recordTrial(opts.taskType, opts.itemId, opts.itemName, durationMs, false, '');
      }
      _rec = null;
      /* ParadigmCamera event: recording item end */
      if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
        ParadigmCamera.addEvent('recording_item_end', { task_type: opts.taskType, item_id: opts.itemId, duration_ms: Math.round(durationMs) });
      }
      /* Checkpoint save after each recording trial */
      _ckpt.save();
    },
  };
}

/* ================================================================
   jsPsych Initialization
   ================================================================ */

var jsPsych = initJsPsych({
  display_element: 'jspsych-target',
  on_finish: function() {
    // saveData() is awaited in the timeline call-function trial — not here
    showEndScreen('speech', subjectId);
  },
});

var timeline = [];

/* ================================================================
   Preload all stimulus images
   ================================================================ */

var _speechPreloadImages = (function() {
  var imgs = [];
  SEMANTIC_FLUENCY_ITEMS.forEach(function(item) { imgs.push(STIM_BASE + item.image); });
  VFT_ITEMS.forEach(function(item) { imgs.push(STIM_BASE + item.image); });
  ACTION_FLUENCY_ITEMS.forEach(function(item) { imgs.push(STIM_BASE + item.image); });
  SCENE_ITEMS.forEach(function(item) { imgs.push(STIM_BASE + item.image); });
  READING_ITEMS.forEach(function(item) { imgs.push(STIM_BASE + item.image); });
  // Instruction images referenced by imageInstructionTrial()
  imgs.push(STIM_BASE + 'slide04_img003.webp'); // VFT instruction
  imgs.push(STIM_BASE + 'slide07_img006.webp'); // Action fluency instruction
  return imgs;
})();

timeline.push({
  type: jsPsychPreload,
  images: _speechPreloadImages,
  show_progress_bar: true,
  message: '正在加载，请稍候...',
  continue_after_error: true,
});
// 2026-04-19: 预加载后检查失败资源
timeline.push({
  type: jsPsychCallFunction, async: true,
  func: function(done) {
    if (typeof TouchHardening !== 'undefined' && TouchHardening.checkLoadFailures) {
      TouchHardening.checkLoadFailures({ paradigmName: '语音测评' }).then(function() { done(); });
    } else { done(); }
  },
});

/* ================================================================
   Mic Permission (welcome 任务总览页已删除 — 师兄说不需要预览全部任务)
   ================================================================ */

/* Request microphone access */
timeline.push({
  type: jsPsychCallFunction,
  async: true,
  func: async function(done) {
    await initMicrophone();
    done();
  },
});

/* Show mic status */
timeline.push({
  type: jsPsychHtmlButtonResponse,
  stimulus: function() {
    if (micAvailable) {
      return makeInstructionHTML(
        '麦克风已就绪',
        '我们检测到您的麦克风工作正常。<br><br>' +
        '接下来请保持<b>正常说话音量</b>，<br>' +
        '不需要特别大声或小声。<br><br>' +
        '<span style="font-size:26px;color:var(--text-secondary)">每项完成后请点击按钮进入下一项</span>'
      );
    }
    return makeInstructionHTML(
      '麦克风不可用',
      '未检测到麦克风，或者浏览器未授权。<br><br>' +
      '您仍然可以完成所有任务，<br>但<b>不会录制语音</b>。<br><br>' +
      '<span style="font-size:26px;color:var(--text-secondary)">任务流程和操作不受影响</span>'
    );
  },
  choices: ['开始'],
  button_html: function(choice) {
    return '<button class="jspsych-btn instr-continue-btn">' + choice + '</button>';
  },
});

/* ================================================================
   麦克风收音测试 (2026-04-19 加)
   主试对着麦克风说话,音量条跳动 & 持续 500ms 超阈值 → 按钮启用
   保障: 防止"getUserMedia 成功但实际不收音"的静默故障
   仅在 micAvailable=true 时走此 trial,否则跳过
   ================================================================ */
timeline.push({
  timeline: [{
    type: jsPsychHtmlButtonResponse,
    stimulus:
      '<div class="instr-page" style="padding:40px 24px">' +
      '<div class="instr-title">麦克风收音测试</div>' +
      '<div class="instr-body" style="margin-bottom:20px">' +
        '请主试对着麦克风说几句话(比如 "喂喂喂" 或 "1、2、3")<br>' +
        '观察下方音量条是否跳动<br><br>' +
        '<b>条子能动=麦克风正常,再点击下方按钮继续</b>' +
      '</div>' +
      '<canvas id="micTestMeter" width="500" height="40" ' +
        'style="border-radius:8px;background:#E0E0E0;display:block;margin:18px auto;"></canvas>' +
      '<div id="micTestStatus" style="font-size:22px;color:#999;margin-top:6px">' +
        '等待检测到声音…' +
      '</div>' +
      '</div>',
    choices: ['确认麦克风可用,开始测试'],
    button_html: function(choice) {
      // disabled 初始状态 + 低透明度,检测通过后 JS 里 enable
      return '<button class="jspsych-btn instr-continue-btn" id="micTestConfirm" ' +
        'disabled style="opacity:0.4;margin-top:16px;">' + choice + '</button>';
    },
    on_load: function() {
      startMicTestMeter();
    },
    on_finish: function() {
      stopMicTestMeter();
    },
  }],
  conditional_function: function() { return micAvailable; },
});

/* ================================================================
   Task 1: Semantic Fluency (语义流畅性)
   ================================================================ */

var totalSemanticItems = SEMANTIC_FLUENCY_ITEMS.length;

// F4 (2026-04-19): Task 1 仅在 START_BLOCK<=0 时推入
if (START_BLOCK <= 0) {
  timeline.push(instructionTrial(
    '第一项：语义流畅性',
    '屏幕上会出现一个<b>类别</b>，<br>' +
    '请您尽可能多地<b>说出属于该类别的词</b>。<br><br>' +
    '例如类别是"蔬菜"，就说 "白菜、萝卜、西红柿..."<br><br>' +
    '说完后点击"下一个"进入下一题。',
    '一共 ' + totalSemanticItems + ' 个类别'
  ));

  /* ParadigmCamera event: task_start for semantic_fluency */
  timeline.push({ type: jsPsychCallFunction, func: function() {
    if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
      ParadigmCamera.addEvent('task_start', { task_type: 'semantic_fluency' });
    }
  }});

  SEMANTIC_FLUENCY_ITEMS.forEach(function(item, idx) {
    timeline.push(buildRecordingTrial({
      taskType: 'semantic_fluency',
      itemId: item.id,
      itemName: item.category,
      imageSrc: item.image,
      prompt: item.prompt,
      taskLabel: '语义流畅性 ' + (idx + 1) + ' / ' + totalSemanticItems,
      buttonLabel: idx < totalSemanticItems - 1 ? '下一个' : '完成此项',
      totalItems: totalSemanticItems,
      currentIdx: idx,
    }));
  });

  /* ParadigmCamera event: task_end for semantic_fluency */
  timeline.push({ type: jsPsychCallFunction, func: function() {
    if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
      ParadigmCamera.addEvent('task_end', { task_type: 'semantic_fluency' });
    }
  }});

  /* Checkpoint: force save after semantic fluency completes */
  timeline.push({ type: jsPsychCallFunction, func: function() { _ckpt.forceSave(); } });

  /* F4: 写 progress 标记 block 0 完成 */
  var _sp0 = speechWriteProgressTrial(0); if (_sp0) timeline.push(_sp0);
}

/* ================================================================
   Task 2: Verbal Fluency Test / VFT (词语流畅性)
   ================================================================ */

var totalVFT = VFT_ITEMS.length;

// F4: Task 2 仅在 START_BLOCK<=1 时推入
if (START_BLOCK <= 1) {
  /* Show VFT instruction image from PPT (slide04) */
  if (!(SKIP_INSTRUCTIONS && START_BLOCK === 1)) {
    timeline.push(imageInstructionTrial('slide04_img003.webp', '第二项：词语流畅性（VFT）'));
  } else {
    timeline.push(instructionTrial('第二项：词语流畅性', '接着测试 — 看到字就说出含它的词', ''));
  }

  /* ParadigmCamera event: task_start for verbal_fluency */
  timeline.push({ type: jsPsychCallFunction, func: function() {
    if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
      ParadigmCamera.addEvent('task_start', { task_type: 'verbal_fluency' });
    }
  }});

  VFT_ITEMS.forEach(function(item, idx) {
    timeline.push(buildRecordingTrial({
      taskType: 'verbal_fluency',
      itemId: item.id,
      itemName: item.character,
      imageSrc: item.image,
      prompt: item.prompt,
      taskLabel: '词语流畅性 ' + (idx + 1) + ' / ' + totalVFT,
      buttonLabel: idx < totalVFT - 1 ? '下一个' : '完成此项',
      totalItems: totalVFT,
      currentIdx: idx,
    }));
  });

  /* ParadigmCamera event: task_end for verbal_fluency */
  timeline.push({ type: jsPsychCallFunction, func: function() {
    if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
      ParadigmCamera.addEvent('task_end', { task_type: 'verbal_fluency' });
    }
  }});

  /* Checkpoint: force save after VFT completes */
  timeline.push({ type: jsPsychCallFunction, func: function() { _ckpt.forceSave(); } });

  /* 注意力探针（VFT结束后） */
  timeline.push(buildAttentionProbe(jsPsych, 'speech', 'after_vft'));

  /* F4: 写 progress 标记 block 1 完成 */
  var _sp1 = speechWriteProgressTrial(1); if (_sp1) timeline.push(_sp1);
}

/* ================================================================
   Task 3: Action Fluency (动作流畅性)
   ================================================================ */

var totalAction = ACTION_FLUENCY_ITEMS.length;

// F4: Task 3 仅在 START_BLOCK<=2 时推入
if (START_BLOCK <= 2) {
  /* Show action fluency instruction image from PPT (slide07) */
  if (!(SKIP_INSTRUCTIONS && START_BLOCK === 2)) {
    timeline.push(imageInstructionTrial('slide07_img006.webp', '第三项：动作流畅性'));
  } else {
    timeline.push(instructionTrial('第三项：动作流畅性', '接着测试 — 说出某个地方会做的事', ''));
  }

  /* ParadigmCamera event: task_start for action_fluency */
  timeline.push({ type: jsPsychCallFunction, func: function() {
    if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
      ParadigmCamera.addEvent('task_start', { task_type: 'action_fluency' });
    }
  }});

  ACTION_FLUENCY_ITEMS.forEach(function(item, idx) {
    timeline.push(buildRecordingTrial({
      taskType: 'action_fluency',
      itemId: item.id,
      itemName: item.location,
      imageSrc: item.image,
      prompt: item.prompt,
      taskLabel: '动作流畅性 ' + (idx + 1) + ' / ' + totalAction,
      buttonLabel: idx < totalAction - 1 ? '下一个' : '完成此项',
      totalItems: totalAction,
      currentIdx: idx,
    }));
  });

  /* ParadigmCamera event: task_end for action_fluency */
  timeline.push({ type: jsPsychCallFunction, func: function() {
    if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
      ParadigmCamera.addEvent('task_end', { task_type: 'action_fluency' });
    }
  }});

  /* Checkpoint: force save after action fluency completes */
  timeline.push({ type: jsPsychCallFunction, func: function() { _ckpt.forceSave(); } });

  /* F4: 写 progress 标记 block 2 完成 */
  var _sp2 = speechWriteProgressTrial(2); if (_sp2) timeline.push(_sp2);
}

/* ================================================================
   Task 4: Scene Description (场景描述)
   ================================================================ */

var totalScene = SCENE_ITEMS.length;

// F4: Task 4 仅在 START_BLOCK<=3 时推入
if (START_BLOCK <= 3) {
  if (!(SKIP_INSTRUCTIONS && START_BLOCK === 3)) {
    timeline.push(instructionTrial(
      '第四项：场景描述',
      '屏幕上会出现一张图片，<br>' +
      '请您仔细看，然后<b>用自己的话</b><br>' +
      '描述图片中发生了什么。<br><br>' +
      '尽可能说出您看到的所有细节。<br>' +
      '说完后请点击"下一个"。',
      '一共 ' + totalScene + ' 张图片'
    ));
  } else {
    timeline.push(instructionTrial('第四项：场景描述', '接着测试 — 描述图片里发生了什么', ''));
  }

  /* ParadigmCamera event: task_start for scene_description */
  timeline.push({ type: jsPsychCallFunction, func: function() {
    if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
      ParadigmCamera.addEvent('task_start', { task_type: 'scene_description' });
    }
  }});

  SCENE_ITEMS.forEach(function(item, idx) {
    timeline.push(buildRecordingTrial({
      taskType: 'scene_description',
      itemId: item.id,
      itemName: item.name,
      imageSrc: item.image,
      prompt: item.prompt,
      taskLabel: '场景描述 ' + (idx + 1) + ' / ' + totalScene,
      buttonLabel: idx < totalScene - 1 ? '下一个' : '完成此项',
      imgStyle: 'max-width:900px;max-height:50vh;border-radius:16px;border:2px solid var(--border)',
      totalItems: totalScene,
      currentIdx: idx,
    }));
  });

  /* ParadigmCamera event: task_end for scene_description */
  timeline.push({ type: jsPsychCallFunction, func: function() {
    if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
      ParadigmCamera.addEvent('task_end', { task_type: 'scene_description' });
    }
  }});

  /* Checkpoint: force save after scene description completes */
  timeline.push({ type: jsPsychCallFunction, func: function() { _ckpt.forceSave(); } });

  /* F4: 写 progress 标记 block 3 完成 */
  var _sp3 = speechWriteProgressTrial(3); if (_sp3) timeline.push(_sp3);
}

/* ================================================================
   Task 5: Reading (朗读任务)
   ================================================================ */

var totalReading = READING_ITEMS.length;

// F4: Task 5 仅在 START_BLOCK<=4 时推入
if (START_BLOCK <= 4) {
  if (!(SKIP_INSTRUCTIONS && START_BLOCK === 4)) {
    timeline.push(instructionTrial(
      '第五项：朗读任务',
      '屏幕上会出现数字或诗歌，<br>' +
      '请您用<b>正常语速</b>大声朗读出来。<br><br>' +
      '不需要着急，读清楚就好。<br>' +
      '读完后请点击"下一个"。',
      '一共 ' + totalReading + ' 段内容'
    ));
  } else {
    timeline.push(instructionTrial('第五项：朗读任务', '接着测试 — 正常语速朗读出来', ''));
  }

  /* ParadigmCamera event: task_start for reading */
  timeline.push({ type: jsPsychCallFunction, func: function() {
    if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
      ParadigmCamera.addEvent('task_start', { task_type: 'reading' });
    }
  }});

  READING_ITEMS.forEach(function(item, idx) {
    timeline.push(buildRecordingTrial({
      taskType: 'reading',
      itemId: item.id,
      itemName: item.name,
      imageSrc: item.image,
      prompt: item.prompt,
      taskLabel: '朗读任务 ' + (idx + 1) + ' / ' + totalReading,
      buttonLabel: idx < totalReading - 1 ? '下一个' : '完成此项',
      totalItems: totalReading,
      currentIdx: idx,
    }));
  });

  /* ParadigmCamera event: task_end for reading */
  timeline.push({ type: jsPsychCallFunction, func: function() {
    if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
      ParadigmCamera.addEvent('task_end', { task_type: 'reading' });
    }
  }});

  /* Checkpoint: force save after reading completes */
  timeline.push({ type: jsPsychCallFunction, func: function() { _ckpt.forceSave(); } });
}

/* 注意力探针（全部结束后） */
timeline.push(buildAttentionProbe(jsPsych, 'speech', 'end'));

/* Save data, clear checkpoint, stop camera */
timeline.push({
  type: jsPsychCallFunction,
  async: true,
  func: async function(done) {
    await saveData();
    /* Stop paradigm camera recording (no-op if not enabled) */
    try { await ParadigmCamera.stopAndSave(); } catch (e) { console.warn('[Speech] camera stop error:', e); }
    /* Clear checkpoint — experiment completed normally, final CSV is saved */
    _ckpt.clear();
    /* Release microphone */
    if (mediaStream) {
      mediaStream.getTracks().forEach(function(track) { track.stop(); });
      mediaStream = null;
    }
    /* 2026-04-19: AudioContext 也关掉,浏览器每源 ~6 个 AC 的限制会累积 */
    if (_audioCtx) {
      try { _audioCtx.close(); } catch (e) { /* ignore */ }
      _audioCtx = null;
      _analyser = null;
    }
    /* Notify parent window (launcher) */
    try {
      if (window.opener) {
        window.opener.postMessage({ paradigm: 'speech', status: 'done' }, '*');
      }
    } catch (e) { /* ignore */ }
    done();
  },
});

/* Run — wrapped in async IIFE for camera init */
(async function() {
  /* Start paradigm camera (optional — skipped if not enabled in localStorage) */
  try { await ParadigmCamera.init('speech', subjectId); } catch (e) { console.warn('[Speech] camera init error:', e); }
  jsPsych.run(timeline);
})();
