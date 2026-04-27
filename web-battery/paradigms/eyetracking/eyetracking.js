/**
 * eyetracking.js -- 自然注视范式 (Naturalistic Gaze Paradigm) Web版
 *
 * 基于 Wynn et al. (2025) PNAS 122(33) e2505879122
 * PsychoPy版移植为 jsPsych 8 Web版
 *
 * 设计:
 *   Block 1: 20张图片 x 5s, ISI 1.5s 注视点
 *   Block 2: 20张图片 (10张Block1重复 + 10张新图) x 5s, ISI 1.5s
 *   全程前置摄像头后台静默录制
 *
 * 图片来源: CAT2000 显著性数据库 (MIT)
 * 6类别: Indoor, Social, Action, OutdoorManMade, OutdoorNatural, Fractal
 */

/* ===== Utility Functions ===== */

function getUrlParam(key) {
  return new URLSearchParams(window.location.search).get(key) || '';
}

function timestampStr() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function downloadBlob(content, filename, mimeType) {
  const blob = content instanceof Blob
    ? content
    : new Blob([content], { type: mimeType || 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

const BOM = '\uFEFF';

/* ===== Configuration ===== */

const ET_CONFIG = {
  imageDurationMs: 5000,
  isiDurationMs: 1500,
  calibrationPointMs: 2000,
  calibrationGapMs: 300,
  instructionMinWaitMs: 800,

  categories: ['Indoor', 'Social', 'Action', 'OutdoorManMade', 'OutdoorNatural', 'Fractal'],
  imagesPerCategory: 7,
  block1Total: 20,
  block2Total: 20,
  block2Repeated: 10,
  block2Novel: 10,
  seed: 42,

  stimuliBasePath: '../../stimuli/eyetracking/',

  // Calibration positions (as fraction of viewport)
  calibrationPositions: [
    { x: 0.5, y: 0.5 },    // center
    { x: 0.15, y: 0.2 },   // top-left
    { x: 0.85, y: 0.2 },   // top-right
    { x: 0.15, y: 0.8 },   // bottom-left
    { x: 0.85, y: 0.8 },   // bottom-right
  ],

  camera: {
    facingMode: 'user',
    width: 1280,
    height: 720,
  },
};

/* ===== Seeded Random ===== */

class SeededRandom {
  constructor(seed) {
    this.state = seed;
  }
  next() {
    this.state = (this.state * 1664525 + 1013904223) & 0xFFFFFFFF;
    return (this.state >>> 0) / 4294967296;
  }
  shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(this.next() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
  sample(arr, n) {
    const shuffled = this.shuffle(arr);
    return shuffled.slice(0, n);
  }
}

/* ===== Stimulus Manager ===== */

class StimulusManager {
  constructor(config) {
    this.config = config;
    this.rng = new SeededRandom(config.seed);
    this.allImages = {};
    this.block1Trials = [];
    this.block2Trials = [];
    this._loadImages();
    this._generateTrialSequence();
  }

  _loadImages() {
    for (const cat of this.config.categories) {
      const images = [];
      for (let i = 1; i <= this.config.imagesPerCategory; i++) {
        const num = String(i * 2 - 1).padStart(3, '0');  // 001, 003, 005, ...
        images.push({
          path: `${this.config.stimuliBasePath}${cat}/${num}.png`,
          filename: `${num}.png`,
          category: cat,
        });
      }
      this.allImages[cat] = images;
    }
  }

  _generateTrialSequence() {
    // For each category: first 3-4 go to Block 1, next 2 go to Block 2 novel
    const block1Pool = {};
    const block2NovelPool = {};

    for (const cat of this.config.categories) {
      const shuffled = this.rng.shuffle(this.allImages[cat]);
      block1Pool[cat] = shuffled.slice(0, 4);
      block2NovelPool[cat] = shuffled.slice(4, 6);
    }

    // Block 1: 3 per category = 18, + 2 from first 2 categories = 20
    let block1 = [];
    for (const cat of this.config.categories) {
      for (const img of block1Pool[cat].slice(0, 3)) {
        block1.push({ ...img, condition: 'novel', block: 1 });
      }
    }
    // Add 2 more to reach 20
    for (const cat of this.config.categories.slice(0, 2)) {
      if (block1Pool[cat].length > 3) {
        block1.push({ ...block1Pool[cat][3], condition: 'novel', block: 1 });
      }
    }

    // Block 2: 10 repeated from block1 + 10 novel
    const repeated = this.rng.sample(block1, this.config.block2Repeated).map(t => ({
      ...t, condition: 'repeated', block: 2,
    }));

    let novel = [];
    for (const cat of this.config.categories) {
      for (const img of block2NovelPool[cat]) {
        novel.push({ ...img, condition: 'novel', block: 2 });
      }
    }
    novel = novel.slice(0, this.config.block2Novel);

    let block2 = [...repeated, ...novel];

    // Pseudo-random: no adjacent same-category
    this.block1Trials = this._shuffleNoAdjacent(block1);
    this.block2Trials = this._shuffleNoAdjacent(block2);
  }

  _shuffleNoAdjacent(trials, maxAttempts) {
    maxAttempts = maxAttempts || 1000;
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const shuffled = this.rng.shuffle(trials);
      let valid = true;
      for (let i = 0; i < shuffled.length - 1; i++) {
        if (shuffled[i].category === shuffled[i + 1].category) {
          valid = false;
          break;
        }
      }
      if (valid) return shuffled;
    }
    // Fallback: just return shuffled
    return this.rng.shuffle(trials);
  }

  getAllImagePaths() {
    const paths = [];
    for (const t of this.block1Trials) paths.push(t.path);
    for (const t of this.block2Trials) paths.push(t.path);
    return [...new Set(paths)];
  }
}

/* ===== Camera Manager (inline, no ES module) ===== */

class WebCameraRecorder {
  constructor() {
    this.stream = null;
    this.recorder = null;
    this.chunks = [];
    this.timestamps = [];
    this.startTime = 0;
    this.mimeType = '';
    this.available = false;
  }

  async init(options) {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('当前访问地址不支持摄像头。局域网设备请使用 HTTPS 地址打开。');
      }

      const constraints = {
        video: {
          facingMode: options.facingMode || 'user',
          width: { ideal: options.width || 1280 },
          height: { ideal: options.height || 720 },
        },
        audio: false,
      };
      this.stream = await navigator.mediaDevices.getUserMedia(constraints);

      const mimeTypes = [
        'video/webm;codecs=vp9',
        'video/webm;codecs=vp8',
        'video/webm',
        'video/mp4',
      ];
      this.mimeType = mimeTypes.find(t => MediaRecorder.isTypeSupported(t)) || '';
      this.available = true;
      console.log('[Camera] initialized, codec:', this.mimeType);
      return true;
    } catch (e) {
      console.warn('[Camera] init failed:', e);
      this.available = false;
      return false;
    }
  }

  start() {
    if (!this.available || !this.stream) return;
    this.chunks = [];
    this.timestamps = [];
    this.startTime = performance.now();

    const options = this.mimeType ? { mimeType: this.mimeType } : {};
    this.recorder = new MediaRecorder(this.stream, options);
    this.recorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };
    this.recorder.start(30000); // 30s chunks
    console.log('[Camera] recording started');
  }

  addTimestamp(eventName) {
    this.timestamps.push({
      event: eventName,
      time_ms: performance.now() - this.startTime,
      epoch_ms: Date.now(),
    });
  }

  async stop() {
    return new Promise((resolve) => {
      if (!this.recorder || this.recorder.state === 'inactive') {
        resolve({ blob: null, timestamps: this.timestamps });
        return;
      }

      // Timeout protection: if onstop never fires, force-resolve after 10s
      const timeoutId = setTimeout(() => {
        console.error('[Camera] stop() timed out after 10s — force-resolving with collected chunks');
        let blob = null;
        try {
          if (this.chunks.length > 0) {
            blob = new Blob(this.chunks, { type: this.mimeType || 'video/webm' });
          }
        } catch (e) {
          console.error('[Camera] failed to create blob from chunks:', e);
        }
        resolve({ blob, timestamps: this.timestamps });
      }, 10000);

      this.recorder.onstop = () => {
        clearTimeout(timeoutId);
        let blob = null;
        try {
          blob = new Blob(this.chunks, { type: this.mimeType || 'video/webm' });
          console.log(`[Camera] stopped, ${blob.size} bytes, ${this.timestamps.length} markers`);
        } catch (e) {
          console.error('[Camera] failed to create blob:', e);
        }
        resolve({ blob, timestamps: this.timestamps });
      };

      this.recorder.onerror = (e) => {
        clearTimeout(timeoutId);
        console.error('[Camera] MediaRecorder error during stop:', e);
        resolve({ blob: null, timestamps: this.timestamps });
      };

      try {
        this.recorder.stop();
      } catch (e) {
        clearTimeout(timeoutId);
        console.error('[Camera] recorder.stop() threw:', e);
        resolve({ blob: null, timestamps: this.timestamps });
      }
    });
  }

  destroy() {
    try {
      if (this.stream) {
        this.stream.getTracks().forEach(t => {
          try { t.stop(); } catch (e) { /* track already stopped */ }
        });
        this.stream = null;
      }
      this.recorder = null;
    } catch (e) {
      console.error('[Camera] destroy() error (non-fatal):', e);
    }
  }

  timestampsToCSV() {
    const header = 'event,time_ms,epoch_ms\n';
    const rows = this.timestamps.map(
      t => `${t.event},${t.time_ms.toFixed(1)},${t.epoch_ms}`
    ).join('\n');
    return BOM + header + rows;
  }
}

/* ===== Trial Data Collector ===== */

class TrialDataCollector {
  constructor(subjectId) {
    this.subjectId = subjectId;
    this.trials = [];
    this.experimentStartTime = 0;
  }

  setStart() {
    this.experimentStartTime = performance.now();
  }

  recordTrial(block, trialIndex, imageName, category, condition, isRepeated, onsetMs, offsetMs) {
    this.trials.push({
      block,
      trial_index: trialIndex,
      image_name: imageName,
      category,
      condition,
      is_repeated: isRepeated ? 1 : 0,
      onset_ms: onsetMs.toFixed(1),
      offset_ms: offsetMs.toFixed(1),
      duration_ms: (offsetMs - onsetMs).toFixed(1),
      relative_onset_s: ((onsetMs - this.experimentStartTime) / 1000).toFixed(3),
    });
  }

  toCSV() {
    if (this.trials.length === 0) return '';
    const header = Object.keys(this.trials[0]).join(',');
    const rows = this.trials.map(t => Object.values(t).join(','));
    return BOM + header + '\n' + rows.join('\n');
  }

  toSummaryJSON() {
    return JSON.stringify({
      subject_id: this.subjectId,
      experiment: 'Naturalistic Gaze Paradigm',
      version: '1.0.0-web',
      based_on: 'Wynn et al. (2025) PNAS 122(33) e2505879122',
      total_trials: this.trials.length,
      block1_trials: this.trials.filter(t => t.block === 1).length,
      block2_trials: this.trials.filter(t => t.block === 2).length,
      repeated_trials: this.trials.filter(t => t.is_repeated === 1).length,
      parameters: {
        image_duration_ms: ET_CONFIG.imageDurationMs,
        isi_duration_ms: ET_CONFIG.isiDurationMs,
        categories: ET_CONFIG.categories,
      },
    }, null, 2);
  }
}

/* ===== Checkpoint (inline, no ES module) ===== */

const _ckpt = (() => {
  let saving=false, lastTime=0, pending=false, p='', sid='', fn=null;
  const MIN=5000;
  async function doSave(){if(saving){pending=true;return;}const csv=fn();if(!csv)return;saving=true;lastTime=Date.now();try{localStorage.setItem('ckpt_'+p+'_'+sid,csv);}catch(e){}try{await fetch(window.location.origin+'/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paradigm:p,subject_id:sid,filename:p+'_'+sid+'_checkpoint.csv',content:csv})});}catch(e){}saving=false;if(pending){pending=false;doSave();}}
  return{init(a,b,c){p=a;sid=b;fn=c;},save(){if(Date.now()-lastTime<MIN){if(!pending){pending=true;setTimeout(()=>{if(pending){pending=false;doSave();}},MIN-(Date.now()-lastTime));}return;}doSave();},forceSave(){doSave();},clear(){try{localStorage.removeItem('ckpt_'+p+'_'+sid);}catch(e){}}};
})();

/* ===== Main Experiment ===== */

(function() {
  const subjectId = getUrlParam('sid') || 'P001';
  const ts = timestampStr();
  const prefix = `${subjectId}_eyetracking_${ts}`;

  // F4 (2026-04-19): Block-level resume
  // block 0 = Block 1 trials (20 张), block 1 = Block 2 trials (20 张)
  // Calibration/camera setup 不属于 block,总是运行(保证数据质量)
  let START_BLOCK = 0;
  let SKIP_INSTRUCTIONS = false;
  if (window.ProgressAPI && window.ProgressAPI.getResumeParams) {
    const _rp = window.ProgressAPI.getResumeParams();
    START_BLOCK = _rp.startBlock;
    SKIP_INSTRUCTIONS = _rp.skipInstructions;
  }
  const ET_TOTAL_BLOCKS = 2;
  if (START_BLOCK >= ET_TOTAL_BLOCKS) {
    console.warn('[eyetracking] startBlock', START_BLOCK, '>= totalBlocks, falling back to 0');
    START_BLOCK = 0;
    SKIP_INSTRUCTIONS = false;
    if (window.ProgressAPI) window.ProgressAPI.clear('eyetracking', subjectId);
  }
  window.__paradigmName = 'eyetracking';
  window.__subjectId = subjectId;
  window.__totalBlocks = ET_TOTAL_BLOCKS;
  window.__currentBlockIdx = START_BLOCK;
  window.__blockOrder = ['block1','block2'];
  window.__balance = null;

  // Managers
  const stimMgr = new StimulusManager(ET_CONFIG);
  const camera = new WebCameraRecorder();
  const trialData = new TrialDataCollector(subjectId);
  let cameraAvailable = false;

  // Initialize checkpoint with getDataFn → trialData.toCSV()
  _ckpt.init('eyetracking', subjectId, () => trialData.toCSV());

  // Track whether camera resources have been cleaned up (step 12 does stop, on_finish does destroy)
  let cameraCleanedUp = false;

  // Initialize jsPsych
  const jsPsych = initJsPsych({
    display_element: 'jspsych-target',
    on_finish: function() {
      // Safe to call destroy() even after stop() — destroy() just releases the stream/tracks.
      // Guard prevents double-destroy from causing issues if on_finish fires unexpectedly.
      if (!cameraCleanedUp) {
        cameraCleanedUp = true;
        try {
          camera.destroy();
        } catch (e) {
          console.error('[on_finish] camera.destroy() error (non-fatal):', e);
        }
      }
      // Unified end screen
      showEndScreen('eyetracking', subjectId);
    },
  });

  /* ===== Build Timeline ===== */

  const timeline = [];

  /* --- 1. Preload images --- */
  timeline.push({
    type: jsPsychPreload,
    images: stimMgr.getAllImagePaths(),
    show_progress_bar: true,
    message: '<div class="instruction-page"><div class="instruction-body">正在加载图片资源...</div></div>',
    error_message: '<p style="color:red;">部分图片加载失败，实验可能受影响。</p>',
    continue_after_error: true,
  });

  // 2026-04-19: 预加载后检查失败资源
  timeline.push({
    type: jsPsychCallFunction,
    async: true,
    func: function(done) {
      if (typeof TouchHardening !== 'undefined' && TouchHardening.checkLoadFailures) {
        TouchHardening.checkLoadFailures({ paradigmName: '看图片' }).then(function() { done(); });
      } else { done(); }
    },
  });

  /* --- 2. Welcome --- */
  timeline.push({
    type: jsPsychHtmlButtonResponse,
    stimulus: `
      <div class="instruction-page">
        <div class="instruction-title">看图片</div>
        <div class="instruction-body">
          接下来屏幕上会出现一些图片<br><br>
          您只需要<b>自然地看</b>就好<br>
          不用记住什么，也不用做任何操作
        </div>
      </div>
    `,
    choices: ['继续'],
    button_html: (choice) => `<button class="jspsych-btn btn-primary">${choice}</button>`,
  });

  /* --- 2b. How it works --- */
  timeline.push({
    type: jsPsychHtmlButtonResponse,
    stimulus: `
      <div class="instruction-page">
        <div class="instruction-title">温馨提示</div>
        <div class="instruction-body">
          每张图片看 5 秒，会自动换下一张<br><br>
          过程中摄像头会在后台录制<br>
          请保持面部在摄像头范围内
        </div>
      </div>
    `,
    choices: ['继续'],
    button_html: (choice) => `<button class="jspsych-btn btn-primary">${choice}</button>`,
  });

  /* --- 3. Camera init --- */
  timeline.push({
    type: jsPsychHtmlButtonResponse,
    stimulus: `
      <div class="camera-prompt">
        <div class="instruction-title">开启摄像头</div>
        <div class="instruction-body">
          请点击下方按钮开启摄像头<br>
          摄像头只在后台录制，屏幕上看不到
        </div>
        <div class="camera-status" id="cam-status"></div>
        <div style="margin-top:24px;">
          <button class="jspsych-btn btn-primary" id="cam-start-btn" style="min-height:96px">开启摄像头</button>
        </div>
      </div>
    `,
    choices: [],
    response_ends_trial: false,
    trial_duration: null,
    on_load: function() {
      const btn = document.getElementById('cam-start-btn');
      const statusEl = document.getElementById('cam-status');
      btn.addEventListener('click', async function() {
        btn.disabled = true;
        btn.textContent = '正在初始化...';
        statusEl.textContent = '正在请求摄像头权限...';
        statusEl.className = 'camera-status';
        const ok = await camera.init(ET_CONFIG.camera);
        if (ok) {
          cameraAvailable = true;
          statusEl.textContent = '摄像头已就绪';
          statusEl.className = 'camera-status success';
        } else {
          cameraAvailable = false;
          statusEl.textContent = '摄像头不可用（实验仍可继续，但无视频记录）';
          statusEl.className = 'camera-status error';
        }
        // Proceed after short delay
        setTimeout(() => {
          jsPsych.finishTrial({ camera_available: cameraAvailable });
        }, 1500);
      }, { once: true });
    },
  });

  /* --- 3b. Face alignment calibration page --- */
  /*
   * Simple approach for elderly users: show live camera feed with a
   * semi-transparent face outline (oval) overlay. The participant
   * aligns their face within the outline, then taps "ready".
   * No face detection API needed -- just a visual guide.
   * If camera is unavailable, skip this step gracefully.
   */
  timeline.push({
    type: jsPsychHtmlButtonResponse,
    stimulus: `
      <div class="et-face-align-page">
        <div class="et-face-align-title">请对准面部位置</div>
        <div class="et-face-align-subtitle">将面部对准下方的轮廓框内</div>
        <div class="et-face-align-container">
          <video id="face-align-video" autoplay playsinline muted></video>
          <svg class="et-face-outline" viewBox="0 0 400 500" xmlns="http://www.w3.org/2000/svg">
            <ellipse cx="200" cy="230" rx="130" ry="170"
              fill="none" stroke="#4CAF50" stroke-width="4" stroke-dasharray="12,6" opacity="0.9"/>
            <line x1="200" y1="55" x2="200" y2="75" stroke="#4CAF50" stroke-width="3" opacity="0.6"/>
            <line x1="200" y1="395" x2="200" y2="415" stroke="#4CAF50" stroke-width="3" opacity="0.6"/>
            <line x1="65" y1="230" x2="85" y2="230" stroke="#4CAF50" stroke-width="3" opacity="0.6"/>
            <line x1="315" y1="230" x2="335" y2="230" stroke="#4CAF50" stroke-width="3" opacity="0.6"/>
          </svg>
          <div class="et-face-align-nofeed" id="face-align-nofeed" style="display:none">
            <div style="font-size:48px;margin-bottom:16px;color:#999">&#128247;</div>
            <div>摄像头未开启</div>
            <div style="font-size:22px;color:#999;margin-top:8px">可直接继续</div>
          </div>
        </div>
        <div class="et-face-align-hint">请保持面部在框内，然后按下方按钮</div>
      </div>
    `,
    choices: ['位置已对准，继续'],
    button_html: (choice) => `<button class="jspsych-btn btn-primary" style="min-width:320px">${choice}</button>`,
    on_load: function() {
      const video = document.getElementById('face-align-video');
      const nofeed = document.getElementById('face-align-nofeed');
      if (cameraAvailable && camera.stream) {
        video.srcObject = camera.stream;
        video.style.display = 'block';
      } else {
        video.style.display = 'none';
        if (nofeed) nofeed.style.display = 'flex';
      }
    },
    on_finish: function() {
      // Stop showing preview (video element will be removed by jsPsych)
      const video = document.getElementById('face-align-video');
      if (video) video.srcObject = null;
    },
  });

  /* --- 4. Calibration instruction --- */
  timeline.push({
    type: jsPsychHtmlButtonResponse,
    stimulus: `
      <div class="instruction-page">
        <div class="instruction-title">校准准备</div>
        <div class="instruction-body">
          屏幕上会出现 5 个红色圆点<br><br>
          请<b>盯着每个红点看</b>，直到它消失<br>
          很快就好
        </div>
      </div>
    `,
    choices: ['继续'],
    button_html: (choice) => `<button class="jspsych-btn btn-primary">${choice}</button>`,
  });

  /* --- 5. Calibration sequence --- */
  for (let i = 0; i < ET_CONFIG.calibrationPositions.length; i++) {
    const pos = ET_CONFIG.calibrationPositions[i];
    timeline.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: function() {
        const left = pos.x * 100;
        const top = pos.y * 100;
        return `
          <div class="et-calibration-screen">
            <div class="et-calibration-dot" style="left:${left}vw;top:${top}vh;"></div>
          </div>
        `;
      },
      choices: 'NO_KEYS',
      trial_duration: ET_CONFIG.calibrationPointMs,
    });
    // Gap between calibration points
    timeline.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: '<div class="et-calibration-gap"></div>',
      choices: 'NO_KEYS',
      trial_duration: ET_CONFIG.calibrationGapMs,
    });
  }

  /* --- 6. Start camera + mark experiment start --- */
  timeline.push({
    type: jsPsychCallFunction,
    func: function() {
      if (cameraAvailable) {
        camera.start();
        camera.addTimestamp('experiment_start');
      }
      trialData.setStart();
    },
  });

  /* --- 7. Block 1 instruction --- */
  // F4: START_BLOCK=0 时推入 block 1 指导语
  if (START_BLOCK <= 0) {
    timeline.push({
      type: jsPsychHtmlButtonResponse,
      stimulus: `
        <div class="instruction-page">
          <div class="instruction-title">第一组图片</div>
          <div class="instruction-body">
            现在开始看第一组图片<br><br>
            请自然地看，放轻松就好
          </div>
        </div>
      `,
      choices: ['继续'],
      button_html: (choice) => `<button class="jspsych-btn btn-primary">${choice}</button>`,
      on_finish: function() {
        if (cameraAvailable) camera.addTimestamp('block1_start');
      },
    });
  }

  /* --- 8. Block 1 trials --- */
  function buildTrialPair(trial, trialIndex, blockNum) {
    const trials = [];

    // ISI: fixation cross
    trials.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: '<div class="et-fixation">+</div>',
      choices: 'NO_KEYS',
      trial_duration: ET_CONFIG.isiDurationMs,
    });

    // Image
    trials.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: `
        <div class="et-image-container">
          <img src="${trial.path}" alt="stimulus">
        </div>
      `,
      choices: 'NO_KEYS',
      trial_duration: ET_CONFIG.imageDurationMs,
      data: {
        task: 'image_viewing',
        block: blockNum,
        trial_index: trialIndex,
        image_name: trial.filename,
        category: trial.category,
        condition: trial.condition,
        is_repeated: trial.condition === 'repeated',
      },
      on_start: function() {
        // Record onset
        trial._onsetMs = performance.now();
        if (cameraAvailable) {
          camera.addTimestamp(`B${blockNum}_T${trialIndex}_onset_${trial.filename}`);
        }
      },
      on_finish: function(data) {
        const offsetMs = performance.now();
        const onsetMs = trial._onsetMs || (offsetMs - ET_CONFIG.imageDurationMs);
        trialData.recordTrial(
          blockNum,
          trialIndex,
          trial.filename,
          trial.category,
          trial.condition,
          trial.condition === 'repeated',
          onsetMs,
          offsetMs
        );
        if (cameraAvailable) {
          camera.addTimestamp(`B${blockNum}_T${trialIndex}_offset_${trial.filename}`);
        }
        _ckpt.save();
      },
    });

    return trials;
  }

  // Block 1 trials
  // F4: 仅 START_BLOCK<=0 时跑 Block 1
  if (START_BLOCK <= 0) {
    for (let i = 0; i < stimMgr.block1Trials.length; i++) {
      const pair = buildTrialPair(stimMgr.block1Trials[i], i + 1, 1);
      timeline.push(...pair);
    }

    /* --- 9. Block 1 end marker --- */
    timeline.push({
      type: jsPsychCallFunction,
      func: function() {
        if (cameraAvailable) camera.addTimestamp('block1_end');
        _ckpt.forceSave();
      },
    });

    /* --- 10. 注意力探针（Block 1 结束后） --- */
    timeline.push(buildAttentionProbe(jsPsych, 'eyetracking', 'after_block_1'));

    /* F4: 写 progress 标记 block 0 完成 */
    if (window.ProgressAPI && window.ProgressAPI.writeTrial) {
      timeline.push(window.ProgressAPI.writeTrial('eyetracking', subjectId, 0, ET_TOTAL_BLOCKS, {
        blockOrder: ['block1','block2'],
      }));
    }
  }

  /* --- 10b. Block 2 准备 --- */
  timeline.push({
    type: jsPsychCallFunction,
    func: function() {
      if (cameraAvailable) camera.addTimestamp('block2_start');
      _ckpt.forceSave();
    },
  });

  // F4: resume 时 Block 2 之前加个简短过渡页(没有这页老人不知道在做什么)
  if (START_BLOCK === 1 && !SKIP_INSTRUCTIONS) {
    timeline.push({
      type: jsPsychHtmlButtonResponse,
      stimulus: `
        <div class="instruction-page">
          <div class="instruction-title">第二组图片 - 接着看</div>
          <div class="instruction-body">
            接下来是第二组图片<br><br>
            和刚才一样,自然看就好
          </div>
        </div>
      `,
      choices: ['继续'],
      button_html: (choice) => `<button class="jspsych-btn btn-primary">${choice}</button>`,
    });
  }

  /* --- 11. Block 2 trials --- */
  for (let i = 0; i < stimMgr.block2Trials.length; i++) {
    const pair = buildTrialPair(stimMgr.block2Trials[i], i + 1, 2);
    timeline.push(...pair);
  }

  /* --- 12. Block 2 end + stop camera --- */
  timeline.push({
    type: jsPsychCallFunction,
    async: true,
    func: async function(done) {
      // CRITICAL: done() MUST be called no matter what, otherwise jsPsych hangs (blank screen).
      // All async operations are wrapped in try-catch with fallback local downloads.
      try {
        if (cameraAvailable) {
          try {
            camera.addTimestamp('block2_end');
            camera.addTimestamp('experiment_end');
          } catch (e) {
            console.error('[Step12] addTimestamp failed:', e);
          }

          // Stop recording (has internal 10s timeout protection)
          let result = { blob: null, timestamps: [] };
          try {
            result = await camera.stop();
          } catch (e) {
            console.error('[Step12] camera.stop() threw:', e);
          }

          // Save video: local + server in parallel
          if (result.blob && result.blob.size > 0) {
            const videoFilename = `${prefix}_video.webm`;
            if (typeof LocalPack !== 'undefined') {
              LocalPack.add(videoFilename, result.blob);
            }
            // 1. Always download locally first (instant, guaranteed)
            try {
              downloadBlob(result.blob, videoFilename);
              console.log('[Step12] video saved locally');
            } catch (e) {
              console.error('[Step12] local video download failed:', e);
            }
            // 2026-04-19 不再推视频到服务器 — 容量有限,本地已保存
          }

          // Save camera timestamps CSV: local + server
          try {
            const timestampCSV = camera.timestampsToCSV();
            const tsFilename = `${prefix}_camera_timestamps.csv`;
            if (typeof LocalPack !== 'undefined') {
              LocalPack.add(tsFilename, timestampCSV);
            }
            // 1. Local download
            try { downloadBlob(timestampCSV, tsFilename, 'text/csv;charset=utf-8'); } catch (e) { console.error('[Step12] local timestamps download failed:', e); }
            // 2. Server upload
            try {
              const API_BASE = window.location.origin;
              const controller = new AbortController();
              const tsTimeout = setTimeout(() => controller.abort(), 15000);
              await fetch(`${API_BASE}/api/save`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ paradigm: 'eyetracking', subject_id: subjectId, filename: tsFilename, content: timestampCSV }),
                signal: controller.signal,
              });
              clearTimeout(tsTimeout);
            } catch (e) { console.warn('[Step12] server timestamps upload failed (local copy saved):', e); }
          } catch (e) {
            console.error('[Step12] timestampsToCSV() failed:', e);
          }
        }
      } catch (outerError) {
        console.error('[Step12] unexpected error in camera stop/save flow:', outerError);
      } finally {
        // ALWAYS call done() to prevent blank screen hang
        done();
      }
    },
  });

  /* --- 13. Save trial data --- */
  let _dataSaved = false;
  timeline.push({
    type: jsPsychCallFunction,
    async: true,
    func: async function(done) {
      if (_dataSaved) { done(); return; }
      _dataSaved = true;
      // CRITICAL: done() MUST be called no matter what.
      try {
        const API_BASE = window.location.origin;

        // Trial CSV
        let trialCSV = '';
        let trialFilename = `${prefix}_trials.csv`;
        try {
          trialCSV = trialData.toCSV();
        } catch (e) {
          console.error('[Step13] toCSV() failed:', e);
        }

        // F4 (2026-04-19): 续写场景合并上次 CSV
        if (trialCSV && window.ProgressAPI && window.ProgressAPI.getPrior) {
          const priorCSV = window.ProgressAPI.getPrior('eyetracking', subjectId);
          if (priorCSV) {
            trialCSV = window.ProgressAPI.merge(priorCSV, trialCSV);
            console.log('[eyetracking] merged prior CSV,final rows:', trialCSV.split('\n').length - 2);
          }
        }

        // Summary JSON
        let summaryJSON = '';
        let summaryFilename = `${prefix}_summary.json`;
        try {
          summaryJSON = trialData.toSummaryJSON();
        } catch (e) {
          console.error('[Step13] toSummaryJSON() failed:', e);
        }

        // Trial CSV: local + server
        if (trialCSV) {
          if (typeof LocalPack !== 'undefined') {
            LocalPack.add(trialFilename, trialCSV);
          }
          try { downloadBlob(trialCSV, trialFilename, 'text/csv;charset=utf-8'); } catch (e) { console.error('[Step13] local trial CSV failed:', e); }
          try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 15000);
            await fetch(`${API_BASE}/api/save`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paradigm: 'eyetracking', subject_id: subjectId, filename: trialFilename, content: trialCSV }), signal: controller.signal });
            clearTimeout(timeout);
          } catch (e) { console.warn('[Step13] server trial CSV upload failed (local copy saved):', e); }
        }

        // Summary JSON: local + server
        if (summaryJSON) {
          if (typeof LocalPack !== 'undefined') {
            LocalPack.add(summaryFilename, summaryJSON);
          }
          try { downloadBlob(summaryJSON, summaryFilename, 'application/json'); } catch (e) { console.error('[Step13] local summary JSON failed:', e); }
          try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 15000);
            await fetch(`${API_BASE}/api/save`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paradigm: 'eyetracking', subject_id: subjectId, filename: summaryFilename, content: summaryJSON }), signal: controller.signal });
            clearTimeout(timeout);
          } catch (e) { console.warn('[Step13] server summary upload failed (local copy saved):', e); }
        }
      } catch (outerError) {
        console.error('[Step13] unexpected error in trial data save flow:', outerError);
      } finally {
        // Clear checkpoint — experiment ended normally, final data already saved above
        _ckpt.clear();
        // ALWAYS call done() to prevent blank screen hang
        done();
      }
    },
  });

  /* ===== Run ===== */
  jsPsych.run(timeline);
})();
