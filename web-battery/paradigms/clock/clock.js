/**
 * clock.js -- 画钟测试 (Clock Drawing Test) Web版
 *
 * 基于 PsychoPy 版本移植，使用自定义 Canvas 绘制（不依赖 jsPsych sketchpad 插件），
 * 以实现完整的笔画追踪、撤销、清空、截图等功能。
 *
 * 流程: 指导语 -> 自由绘制(画钟) -> 完成 -> 数据导出
 *
 * 数据输出:
 *   - trajectory CSV: t, x, y, stroke_id, is_drawing
 *   - stroke_summary CSV: stroke_id, start_t, end_t, duration, n_points, length_px
 *   - 截图: canvas PNG (base64)
 */

/* ===== 断点保存 (inlined from lib/checkpoint.js — plain script, not ES module) ===== */

const _CK_API_BASE = window.location.origin;
const _CK_MIN_INTERVAL_MS = 5000;

function createCheckpoint(paradigm, subjectId, getDataFn) {
  let saving = false;
  let lastSaveTime = 0;
  let pendingSave = false;
  const filename = `${paradigm}_${subjectId}_checkpoint.csv`;
  const lsKey = `checkpoint_${paradigm}_${subjectId}`;

  async function doSave() {
    if (saving) { pendingSave = true; return; }
    const csv = getDataFn();
    if (!csv) return;
    saving = true;
    lastSaveTime = Date.now();
    try { localStorage.setItem(lsKey, csv); } catch (e) { /* quota exceeded */ }
    try {
      await fetch(`${_CK_API_BASE}/api/save`, {
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
      if (elapsed < _CK_MIN_INTERVAL_MS) {
        if (!pendingSave) {
          pendingSave = true;
          setTimeout(() => { if (pendingSave) { pendingSave = false; doSave(); } }, _CK_MIN_INTERVAL_MS - elapsed);
        }
        return;
      }
      doSave();
    },
    forceSave() { doSave(); },
    clear() { try { localStorage.removeItem(lsKey); } catch (e) { /* ignore */ } },
  };
}

/* ===== 工具函数 ===== */

function getUrlParam(key) {
  return new URLSearchParams(window.location.search).get(key) || '';
}

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function downloadBlob(content, filename, mimeType) {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType || 'text/plain' });
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

/* ===== 居中弹窗提示 ===== */
let _toastTimer = null;
function showToast(msg, durationMs = 3000) {
  // Remove existing toast
  const old = document.querySelector('.clock-toast');
  if (old) old.remove();
  clearTimeout(_toastTimer);

  const el = document.createElement('div');
  el.className = 'clock-toast';
  el.textContent = msg;
  document.body.appendChild(el);

  _toastTimer = setTimeout(() => {
    el.classList.add('fade-out');
    setTimeout(() => el.remove(), 300);
  }, durationMs);
}

/* ===== 配置 ===== */

const CLOCK_CONFIG = {
  inkColor: '#000000',
  lineWidth: 7,
  canvasBgColor: '#FFFFFF',
  targetTime: '11:10',
  // undoCooldownMs: 0 = 不冷却,连续点能一直撤到全空
  // 原 150ms 怕防抖,但 Edge synth click 延迟可能让第二次点击在 150ms 内被吞 → 老人反馈"点第二下没反应"
  undoCooldownMs: 0,
  predrawnCircle: false,          // 预画圆（关闭）
  circleColor: '#C8C8C8',        // RGB(200,200,200) 浅灰
  circleLineWidth: 2,
  circleDiameterRatio: 0.80,     // 圆直径 = 画布短边 × 0.80 ≈ Surface上10cm
};

/* ===== 绘制数据管理 ===== */

class DrawingManager {
  constructor() {
    this.strokes = [];         // [{id, points: [{t,x,y},...], active: true}]
    this.currentStroke = null;
    this.nextStrokeId = 0;
    this.undoStack = [];       // undone strokes for potential redo
    this.trajectoryLog = [];   // ALL points including metadata (raw log)
    this.undoEvents = [];      // [{t, undone_stroke_id, active_before, undo_event_id}]
    this.startTime = performance.now();
    this.lastUndoTime = 0;
  }

  beginStroke(x, y) {
    const t = this._relTime();
    const id = this.nextStrokeId++;
    this.currentStroke = { id, points: [{ t, x, y }], active: true };
    this.strokes.push(this.currentStroke);
    this.undoStack = [];  // clear redo after new stroke
    this.trajectoryLog.push({ t, x, y, stroke_id: id, is_drawing: 1, event: 'DOWN' });
  }

  addPoint(x, y) {
    if (!this.currentStroke) return;
    const t = this._relTime();
    this.currentStroke.points.push({ t, x, y });
    this.trajectoryLog.push({ t, x, y, stroke_id: this.currentStroke.id, is_drawing: 1, event: 'MOVE' });
  }

  endStroke(x, y) {
    if (!this.currentStroke) return;
    const t = this._relTime();
    this.trajectoryLog.push({ t, x, y, stroke_id: this.currentStroke.id, is_drawing: 0, event: 'UP' });
    this.currentStroke = null;
  }

  undo() {
    const now = performance.now();
    if (now - this.lastUndoTime < CLOCK_CONFIG.undoCooldownMs) return false;
    this.lastUndoTime = now;

    // Find last active stroke
    for (let i = this.strokes.length - 1; i >= 0; i--) {
      if (this.strokes[i].active) {
        const t = this._relTime();
        const activeBefore = this.activeStrokeCount();
        this.strokes[i].active = false;
        this.undoStack.push(this.strokes[i]);
        // Log undo event
        this.undoEvents.push({
          t, undone_stroke_id: this.strokes[i].id,
          active_before: activeBefore, undo_event_id: this.undoEvents.length
        });
        this.trajectoryLog.push({
          t, x: 0, y: 0, stroke_id: this.strokes[i].id, is_drawing: 0, event: 'UNDO'
        });
        return true;
      }
    }
    return false;
  }

  clear() {
    this.strokes = [];
    this.undoStack = [];
    this.currentStroke = null;
    this.nextStrokeId = 0;  // reset stroke counter for clean data
    // Keep trajectory log for raw record, but mark clear event
    const t = this._relTime();
    this.trajectoryLog.push({ t, x: 0, y: 0, stroke_id: -1, is_drawing: 0, event: 'CLEAR' });
  }

  getActiveStrokes() {
    return this.strokes.filter(s => s.active);
  }

  activeStrokeCount() {
    return this.strokes.filter(s => s.active).length;
  }

  /* Generate trajectory CSV (active strokes only, matching PsychoPy _traj.csv) */
  trajectoryCSV() {
    const active = this.getActiveStrokes();
    const activeIds = new Set(active.map(s => s.id));
    const rows = this.trajectoryLog
      .filter(p => activeIds.has(p.stroke_id))
      .map(p => `${p.t.toFixed(1)},${p.x},${p.y},${p.stroke_id},${p.is_drawing}`);
    return BOM + 't,x,y,stroke_id,is_drawing\n' + rows.join('\n');
  }

  /* Generate raw trajectory CSV (full log incl. undo/clear events, matching PsychoPy _traj_raw.csv) */
  trajectoryRawCSV() {
    const active = this.getActiveStrokes();
    const activeIds = new Set(active.map(s => s.id));
    const rows = this.trajectoryLog.map(p => {
      const isActive = activeIds.has(p.stroke_id) ? 1 : 0;
      const event = p.event || (p.is_drawing ? 'MOVE' : 'UP');
      return `${p.t.toFixed(1)},${p.x},${p.y},${p.stroke_id},${p.is_drawing},${isActive},${event}`;
    });
    return BOM + 't,x,y,stroke_id,is_drawing,is_active,event\n' + rows.join('\n');
  }

  /* Generate undo events CSV (matching PsychoPy _undo_events.csv) */
  undoEventsCSV() {
    const header = 'undo_time,undone_stroke_id,active_strokes_before_undo,undo_event_id';
    const rows = this.undoEvents.map(e =>
      `${e.t.toFixed(1)},${e.undone_stroke_id},${e.active_before},${e.undo_event_id}`
    );
    return BOM + header + '\n' + rows.join('\n');
  }

  /* Generate stroke summary CSV */
  strokeSummaryCSV() {
    const active = this.getActiveStrokes();
    const header = 'stroke_id,start_t,end_t,duration,n_points,length_px';
    const rows = active.map(s => {
      const pts = s.points;
      if (pts.length === 0) return null;
      const t0 = pts[0].t;
      const t1 = pts[pts.length - 1].t;
      const dur = t1 - t0;
      const nPts = pts.length;

      // Path length in pixels
      let len = 0;
      for (let i = 1; i < pts.length; i++) {
        const dx = pts[i].x - pts[i-1].x;
        const dy = pts[i].y - pts[i-1].y;
        len += Math.sqrt(dx * dx + dy * dy);
      }

      return `${s.id},${t0.toFixed(1)},${t1.toFixed(1)},${dur.toFixed(1)},${nPts},${len.toFixed(1)}`;
    }).filter(Boolean);

    return BOM + header + '\n' + rows.join('\n');
  }

  _relTime() {
    return performance.now() - this.startTime;
  }
}

/* ===== Canvas 绘制引擎 ===== */

class ClockCanvas {
  constructor(canvasEl) {
    this.canvas = canvasEl;
    this.ctx = canvasEl.getContext('2d');
    this.drawing = new DrawingManager();
    this.isPointerDown = false;
    this.onStrokeChange = null;   // callback: invoked after stroke end, undo, or clear
    this._setupHiDPI();
    this._setupEvents();
  }

  /* Handle high-DPI (Retina) displays: scale canvas backing store */
  _setupHiDPI() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    // CSS size stays the same; backing store is scaled up
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.scale(dpr, dpr);
    // Store CSS dimensions for coordinate calculations
    this._cssWidth = rect.width;
    this._cssHeight = rect.height;
  }

  _setupEvents() {
    const c = this.canvas;
    c.addEventListener('pointerdown', (e) => this._onDown(e));
    c.addEventListener('pointermove', (e) => this._onMove(e));
    c.addEventListener('pointerup', (e) => this._onUp(e));
    c.addEventListener('pointerleave', (e) => this._onUp(e));
    c.addEventListener('pointercancel', (e) => this._onUp(e));
    // Prevent default touch behaviors (scroll, zoom)
    c.style.touchAction = 'none';
  }

  _getPos(e) {
    const rect = this.canvas.getBoundingClientRect();
    return {
      x: Math.round(e.clientX - rect.left),
      y: Math.round(e.clientY - rect.top),
    };
  }

  _onDown(e) {
    e.preventDefault();
    this.isPointerDown = true;
    const { x, y } = this._getPos(e);
    this.drawing.beginStroke(x, y);
    // Start path
    this.ctx.beginPath();
    this.ctx.moveTo(x, y);
    this.ctx.strokeStyle = CLOCK_CONFIG.inkColor;
    this.ctx.lineWidth = CLOCK_CONFIG.lineWidth;
    this.ctx.lineCap = 'round';
    this.ctx.lineJoin = 'round';
    // Release pointer capture to allow smooth tracking
    this.canvas.releasePointerCapture(e.pointerId);
  }

  _onMove(e) {
    if (!this.isPointerDown) return;
    e.preventDefault();
    const { x, y } = this._getPos(e);
    this.drawing.addPoint(x, y);
    this.ctx.lineTo(x, y);
    this.ctx.stroke();
    // Continue path from current position
    this.ctx.beginPath();
    this.ctx.moveTo(x, y);
  }

  _onUp(e) {
    if (!this.isPointerDown) return;
    this.isPointerDown = false;
    const { x, y } = this._getPos(e);
    this.drawing.endStroke(x, y);
    if (this.onStrokeChange) this.onStrokeChange('stroke_end');
  }

  undo() {
    if (this.drawing.undo()) {
      this._redraw();
      if (this.onStrokeChange) this.onStrokeChange('undo');
      return true;
    }
    return false;
  }

  clear() {
    this.drawing.clear();
    this._redraw();
    if (this.onStrokeChange) this.onStrokeChange('clear');
  }

  _redraw() {
    const ctx = this.ctx;
    // Use CSS dimensions (not backing store dimensions) because ctx is already scaled
    const w = this._cssWidth || this.canvas.width;
    const h = this._cssHeight || this.canvas.height;

    // Clear to white
    ctx.fillStyle = CLOCK_CONFIG.canvasBgColor;
    ctx.fillRect(0, 0, w, h);

    // Pre-drawn circle (light gray, non-erasable base layer)
    if (CLOCK_CONFIG.predrawnCircle) {
      const r = Math.min(w, h) * CLOCK_CONFIG.circleDiameterRatio / 2;
      ctx.beginPath();
      ctx.arc(w / 2, h / 2, r, 0, Math.PI * 2);
      ctx.strokeStyle = CLOCK_CONFIG.circleColor;
      ctx.lineWidth = CLOCK_CONFIG.circleLineWidth;
      ctx.stroke();
    }

    // Redraw all active strokes
    const activeStrokes = this.drawing.getActiveStrokes();
    for (const stroke of activeStrokes) {
      if (stroke.points.length < 2) continue;
      ctx.beginPath();
      ctx.moveTo(stroke.points[0].x, stroke.points[0].y);
      for (let i = 1; i < stroke.points.length; i++) {
        ctx.lineTo(stroke.points[i].x, stroke.points[i].y);
      }
      ctx.strokeStyle = CLOCK_CONFIG.inkColor;
      ctx.lineWidth = CLOCK_CONFIG.lineWidth;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.stroke();
    }
  }

  getScreenshot() {
    return this.canvas.toDataURL('image/png');
  }
}

/* ===== 主实验流程 ===== */

(async function() {
  const subjectId = getUrlParam('sid') || 'P001';
  const ts = timestamp();
  const prefix = `clock_${subjectId}_${ts}`;

  // Initialize jsPsych
  const jsPsych = initJsPsych({
    display_element: 'jspsych-target',
    on_finish: function() {
      showEndScreen('clock', subjectId);
    },
  });

  let clockCanvas = null;      // command condition
  let copyClockCanvas = null;  // copy condition
  let checkpoint = null;
  let copyCheckpoint = null;

  /* --- 语音指导语 (VoiceGuide + UX图片) --- */
  const AUDIO_BASE = '../../audio/clock';
  const voiceGuideTrial = {
    type: jsPsychCallFunction,
    async: true,
    func: async function(done) {
      await VoiceGuide.show({
        image: 'img/rules.webp?v=20260414n',
        btnRegion: { x: '80.1%', y: '4.9%', w: '15%', h: '8.2%' },
        buttonText: '我明白了，开始',
        pauseBetween: 500,
        steps: [
          { region: { x: '7.1%', y: '17%', w: '31.7%', h: '38.7%' }, lines: [
            { audio: `${AUDIO_BASE}/s01.mp3`, subtitle: '接下来请您画一个时钟' },
            { audio: `${AUDIO_BASE}/s02.mp3`, subtitle: '用手指在白色画布上画就行' },
          ] },
          { region: { x: '48.3%', y: '27.3%', w: '33.6%', h: '22.2%' }, lines: [
            { audio: `${AUDIO_BASE}/s03.mp3`, subtitle: '需要画三样东西' },
          ] },
          { region: { x: '50.1%', y: '29.7%', w: '30.7%', h: '6.4%' }, lines: [
            { audio: `${AUDIO_BASE}/s04.mp3`, subtitle: '第一，请在白色画布上画一个钟表' },
          ] },
          { region: { x: '50.2%', y: '35.8%', w: '30.6%', h: '5.8%' }, lines: [
            { audio: `${AUDIO_BASE}/s05.mp3`, subtitle: '第二，填上所有的数字' },
          ] },
          { region: { x: '50.3%', y: '41.6%', w: '30.8%', h: '5.3%' }, lines: [
            { audio: `${AUDIO_BASE}/s06.mp3`, subtitle: '第三，将指针指向十一点十分' },
          ] },
          { region: { x: '17.2%', y: '72.8%', w: '25.3%', h: '17%' }, lines: [
            { audio: `${AUDIO_BASE}/s07.mp3`, subtitle: '画好了点击完成按钮' },
          ] },
          { region: { x: '48.8%', y: '65.2%', w: '39.1%', h: '23.5%' }, lines: [
            { audio: `${AUDIO_BASE}/s08.mp3`, subtitle: '画错了也没关系，可以点击清空或撤销' },
          ] },
          { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
            { audio: `${AUDIO_BASE}/s09.mp3`, subtitle: '明白了就点击开始' },
          ] },
        ],
      });
      done();
    },
  };

  /* --- 画钟主界面 (custom HTML trial) --- */
  const drawingTrial = {
    type: jsPsychHtmlButtonResponse,
    stimulus: function() {
      // Compute canvas size: fill tablet screen as much as possible
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      // Reserve: instruction ~60px + buttons ~90px + status ~30px + padding/gaps ~30px
      const reservedH = 190;
      const canvasSize = Math.max(400, Math.min(vw - 40, vh - reservedH, 650));
      const canvasW = canvasSize;
      const canvasH = canvasSize;  // square canvas for clock drawing

      // Set width/height as CSS style (not HTML attributes) so _setupHiDPI can scale backing store
      return `
        <div class="clock-container" style="height:${vh}px; padding:10px 20px 0;">
          <div class="clock-instruction" style="font-size:36px;">
            请画一个时钟，时间指向 <b>11:10</b>
          </div>
          <div class="clock-canvas-wrapper" id="clock-wrapper">
            <canvas id="clock-canvas"
              style="width:${canvasW}px; height:${canvasH}px;"
              width="${canvasW}" height="${canvasH}"></canvas>
          </div>
          <div class="clock-btn-bar">
            <button class="clock-btn clear-btn" id="btn-clear">清空</button>
            <button class="clock-btn undo-btn" id="btn-undo">撤销</button>
            <button class="clock-btn done-btn" id="btn-done">完成</button>
          </div>
        </div>
      `;
    },
    choices: [],  // no jsPsych buttons, we use custom ones
    trial_duration: null,
    response_ends_trial: false,
    on_load: function() {
      // Initialize canvas engine (constructor handles HiDPI + initial white fill)
      const canvasEl = document.getElementById('clock-canvas');
      clockCanvas = new ClockCanvas(canvasEl);
      clockCanvas.drawing.startTime = performance.now();
      // Fill white after HiDPI setup
      clockCanvas._redraw();

      // --- 断点保存: 每次stroke结束/undo/clear后自动保存轨迹数据 ---
      checkpoint = createCheckpoint('clock', subjectId, () => clockCanvas.drawing.trajectoryRawCSV());
      clockCanvas.onStrokeChange = (eventType) => {
        if (eventType === 'clear') {
          // Clear is a significant action — force save immediately
          checkpoint.forceSave();
        } else {
          // stroke_end / undo — throttled save (5s min interval)
          checkpoint.save();
        }
      };

      // Clear button
      document.getElementById('btn-clear').addEventListener('click', () => {
        clockCanvas.clear();
        showToast('已清空', 1500);
      });

      // Undo button — 成功撤销/无可撤销 都给明确反馈(避免老人/主试误以为"没反应")
      document.getElementById('btn-undo').addEventListener('click', () => {
        if (clockCanvas.undo()) {
          showToast('已撤销', 1500);
        } else {
          showToast('没有可撤销的笔画', 1500);
        }
      });

      // Done button
      document.getElementById('btn-done').addEventListener('click', () => {
        const strokeCount = clockCanvas.drawing.activeStrokeCount();
        if (strokeCount === 0) { showToast('请先画一个时钟'); return; }
        jsPsych.finishTrial({
          response: 'done',
          stroke_count: strokeCount,
          rt: performance.now() - clockCanvas.drawing.startTime,
        });
      });
    },
  };

  /* --- 通用数据保存函数 --- */
  function saveClockData(canvas, ckpt, filePrefix) {
    if (!canvas) return Promise.resolve();
    if (ckpt) ckpt.clear();

    const API_BASE = window.location.origin;

    function saveText(filename, content, mimeType) {
      return safeFetch(`${API_BASE}/api/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paradigm: 'clock',
          subject_id: subjectId,
          filename: filename,
          content: content,
        }),
      }).catch((e) => {
        console.warn('[Clock] server save failed, LocalPack has backup:', e);
      });
    }

    const trajCSV = canvas.drawing.trajectoryCSV();
    const trajRawCSV = canvas.drawing.trajectoryRawCSV();
    const strokeSummCSV = canvas.drawing.strokeSummaryCSV();
    const undoCSV = canvas.drawing.undoEventsCSV();
    const screenshot = canvas.getScreenshot();
    const screenshotJSON = JSON.stringify({
      subject_id: subjectId,
      timestamp: ts,
      target_time: CLOCK_CONFIG.targetTime,
      canvas_css_width: canvas._cssWidth || canvas.canvas.width,
      canvas_css_height: canvas._cssHeight || canvas.canvas.height,
      canvas_backing_width: canvas.canvas.width,
      canvas_backing_height: canvas.canvas.height,
      device_pixel_ratio: window.devicePixelRatio || 1,
      stroke_count: canvas.drawing.activeStrokeCount(),
      undo_count: canvas.drawing.undoEvents.length,
      total_drawing_ms: performance.now() - canvas.drawing.startTime,
      image_base64: screenshot,
    }, null, 2);

    let pngBlob = null;
    const pngFilename = `${filePrefix}_clock.webp`;
    try {
      const byteString = atob(screenshot.split(',')[1]);
      const ab = new ArrayBuffer(byteString.length);
      const ia = new Uint8Array(ab);
      for (let i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i);
      }
      pngBlob = new Blob([ab], { type: 'image/png' });
    } catch (e) {
      console.warn('PNG blob creation failed:', e);
    }

    if (typeof LocalPack !== 'undefined') {
      LocalPack.add(`${filePrefix}_trajectory.csv`, trajCSV);
      LocalPack.add(`${filePrefix}_trajectory_raw.csv`, trajRawCSV);
      LocalPack.add(`${filePrefix}_stroke_summary.csv`, strokeSummCSV);
      LocalPack.add(`${filePrefix}_undo_events.csv`, undoCSV);
      LocalPack.add(`${filePrefix}_screenshot.json`, screenshotJSON);
      if (pngBlob) LocalPack.add(pngFilename, pngBlob);
    }

    saveText(`${filePrefix}_trajectory.csv`, trajCSV);
    saveText(`${filePrefix}_trajectory_raw.csv`, trajRawCSV);
    saveText(`${filePrefix}_stroke_summary.csv`, strokeSummCSV);
    saveText(`${filePrefix}_undo_events.csv`, undoCSV);
    saveText(`${filePrefix}_screenshot.json`, screenshotJSON, 'application/json');

    if (pngBlob) {
      const formData = new FormData();
      formData.append('file', pngBlob, pngFilename);
      formData.append('paradigm', 'clock');
      formData.append('subject_id', subjectId);
      fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData })
        .catch((e) => console.warn('[Clock] PNG upload failed, LocalPack has backup:', e));
    }

    return Promise.resolve();
  }

  /* --- 保存命令条件数据 --- */
  const saveCommandData = {
    type: jsPsychCallFunction,
    async: true,
    func: async function(done) {
      await saveClockData(clockCanvas, checkpoint, `${prefix}_command`);
      done();
    },
  };

  /* --- 临摹条件指导语 --- */
  const copyInstrPage = {
    type: jsPsychCallFunction,
    async: true,
    func: async function(done) {
      // Build overlay
      const overlay = document.createElement('div');
      overlay.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:1000;padding:24px 40px;text-align:center;';
      overlay.innerHTML = `
        <div style="font-size:44px;font-weight:bold;color:var(--primary,#1565C0);margin-bottom:24px;">临摹测试</div>
        <div style="font-size:34px;color:#333;line-height:1.6;">
          接下来请您<b>照着左边的示例</b><br>
          在右边的画布上画一个一样的图形<br><br>
          尽可能画得准确
        </div>
        <div id="copy-subtitle" style="font-size:31px;font-weight:bold;color:#1565C0;margin-top:30px;min-height:50px;"></div>
        <button id="copy-start-btn" class="jspsych-btn btn-primary" style="margin-top:30px;min-width:260px;min-height:88px;opacity:0.4;pointer-events:none;">播放中...</button>
        <button id="copy-repeat-btn" style="position:fixed;left:24px;bottom:24px;width:160px;height:60px;padding:0;font-size:22px;font-family:'PingFang SC',sans-serif;font-weight:bold;background:#B0B0B0;color:#1A1A1A;border:2px solid #707070;border-radius:20px;box-shadow:0 2px 8px rgba(0,0,0,0.15);cursor:pointer;touch-action:manipulation;display:none;">再听一遍</button>
        <button id="copy-skip-btn" style="display:none;position:fixed;top:12px;right:12px;z-index:10000;padding:6px 14px;min-height:28px;font-size:13px;font-family:'PingFang SC',sans-serif;background:rgba(60,60,60,0.55);color:#fff;border:none;border-radius:6px;cursor:pointer;touch-action:manipulation;">跳过 (Esc)</button>
      `;
      document.body.appendChild(overlay);

      const subtitleEl = overlay.querySelector('#copy-subtitle');
      const btn = overlay.querySelector('#copy-start-btn');
      const repeatBtn = overlay.querySelector('#copy-repeat-btn');

      // Play audio sequentially
      const audioFiles = [
        { src: `${AUDIO_BASE}/copy_s01.mp3`, text: '接下来请您照着左边的示例' },
        { src: `${AUDIO_BASE}/copy_s02.mp3`, text: '在右边的画布上画一个一样的图形' },
        { src: `${AUDIO_BASE}/copy_s03.mp3`, text: '尽可能画得准确' },
      ];

      async function playSequence() {
        repeatBtn.style.display = 'none';
        btn.textContent = '播放中...';
        btn.style.opacity = '0.4';
        btn.style.pointerEvents = 'none';
        for (const item of audioFiles) {
          subtitleEl.textContent = item.text;
          await new Promise(resolve => {
            const audio = new Audio(item.src);
            audio.onended = resolve;
            audio.onerror = resolve;
            audio.play().catch(resolve);
          });
          await new Promise(r => setTimeout(r, 500)); // pause between sentences
        }
        subtitleEl.textContent = '';
        btn.textContent = '我明白了，开始';
        btn.style.opacity = '1';
        btn.style.pointerEvents = 'auto';
        repeatBtn.style.display = 'block';
      }

      repeatBtn.addEventListener('pointerup', () => { playSequence(); });

      btn.addEventListener('pointerup', () => {
        if (_copyEscHandler) document.removeEventListener('keydown', _copyEscHandler);
        overlay.remove();
        done();
      });

      // 主试模式:跳过按钮 + Esc
      const _testerMode = (() => {
        try { if (localStorage.getItem('tester_mode') === '1') return true; } catch(e){}
        return false;
      })();
      let _copyEscHandler = null;
      const _copySkip = () => {
        if (_copyEscHandler) { document.removeEventListener('keydown', _copyEscHandler); _copyEscHandler = null; }
        if (overlay.parentNode) overlay.remove();
        done();
      };
      if (_testerMode) {
        const skipBtn = overlay.querySelector('#copy-skip-btn');
        if (skipBtn) {
          skipBtn.style.display = 'block';
          skipBtn.addEventListener('pointerup', _copySkip);
        }
        _copyEscHandler = (e) => { if (e.key === 'Escape') _copySkip(); };
        document.addEventListener('keydown', _copyEscHandler);
      }

      await playSequence();
    },
  };

  /* --- 临摹条件画钟界面（左右布局） --- */
  const copyDrawingTrial = {
    type: jsPsychHtmlButtonResponse,
    stimulus: function() {
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      // Left-right layout: image left, canvas right
      const canvasSize = Math.max(350, Math.min(vh - 160, (vw - 80) / 2, 650));

      return `
        <div style="display:flex; align-items:flex-start; justify-content:center; height:${vh}px; padding:10px 20px 0; gap:30px;">
          <div style="flex:0 0 auto; display:flex; flex-direction:column; align-items:center;">
            <div class="clock-instruction" style="margin-bottom:10px;">示例</div>
            <div style="width:${canvasSize}px; height:${canvasSize}px; border:2px solid #ddd; border-radius:8px; background:#fff; display:flex; align-items:center; justify-content:center;">
              <img src="copy_model_pentagons.webp?v=20260414n" style="max-height:${canvasSize - 20}px; max-width:${canvasSize - 20}px;">
            </div>
          </div>
          <div style="flex:0 0 auto; display:flex; flex-direction:column; align-items:center;">
            <div class="clock-instruction" style="margin-bottom:10px;">请临摹左边的图形</div>
            <div class="clock-canvas-wrapper" id="copy-clock-wrapper">
              <canvas id="copy-clock-canvas"
                style="width:${canvasSize}px; height:${canvasSize}px;"
                width="${canvasSize}" height="${canvasSize}"></canvas>
            </div>
            <div class="clock-btn-bar">
              <button class="clock-btn clear-btn" id="copy-btn-clear">清空</button>
              <button class="clock-btn undo-btn" id="copy-btn-undo">撤销</button>
              <button class="clock-btn done-btn" id="copy-btn-done">完成</button>
            </div>
          </div>
        </div>
      `;
    },
    choices: [],
    trial_duration: null,
    response_ends_trial: false,
    on_load: function() {
      const canvasEl = document.getElementById('copy-clock-canvas');
      copyClockCanvas = new ClockCanvas(canvasEl);
      copyClockCanvas.drawing.startTime = performance.now();
      copyClockCanvas._redraw();

      copyCheckpoint = createCheckpoint('clock_copy', subjectId, () => copyClockCanvas.drawing.trajectoryRawCSV());
      copyClockCanvas.onStrokeChange = (eventType) => {
        if (eventType === 'clear') copyCheckpoint.forceSave();
        else copyCheckpoint.save();
      };

      document.getElementById('copy-btn-clear').addEventListener('click', () => {
        copyClockCanvas.clear();
        showToast('已清空', 1500);
      });
      document.getElementById('copy-btn-undo').addEventListener('click', () => {
        if (copyClockCanvas.undo()) {
          showToast('已撤销', 1500);
        } else {
          showToast('没有可撤销的笔画', 1500);
        }
      });
      document.getElementById('copy-btn-done').addEventListener('click', () => {
        const strokeCount = copyClockCanvas.drawing.activeStrokeCount();
        if (strokeCount === 0) { showToast('请先画一个时钟'); return; }
        jsPsych.finishTrial({
          response: 'done',
          condition: 'copy',
          stroke_count: strokeCount,
          rt: performance.now() - copyClockCanvas.drawing.startTime,
        });
      });
    },
  };

  /* --- 保存临摹数据 + 停止摄像头 --- */
  const saveCopyData = {
    type: jsPsychCallFunction,
    async: true,
    func: async function(done) {
      await saveClockData(copyClockCanvas, copyCheckpoint, `${prefix}_copy`);
      await ParadigmCamera.stopAndSave();
      done();
    },
  };

  /* --- 注意力探针（临摹结束后） --- */
  const attentionProbe = buildAttentionProbe(jsPsych, 'clock', 'end');

  /* --- Timeline --- */
  // 预加载指导语图片 + 音频 — 必须等所有 audio 都下完才进 instruction
  var _clockAudioFiles = [];
  ['s01','s02','s03','s04','s05','s06','s07','s08','s09','copy_s01','copy_s02','copy_s03'].forEach(function(n) {
    _clockAudioFiles.push(AUDIO_BASE + '/' + n + '.mp3');
  });
  const preloadTrial = {
    type: jsPsychPreload,
    images: ['img/rules.webp?v=20260414n'],
    audio: _clockAudioFiles,
    show_progress_bar: true,
    message: '<p style="font-size:32px;">正在加载，请稍候...</p>',
    continue_after_error: true,
  };
  // 2026-04-19: 预加载后检查失败资源
  const loadCheckTrial = {
    type: jsPsychCallFunction, async: true,
    func: function(done) {
      if (typeof TouchHardening !== 'undefined' && TouchHardening.checkLoadFailures) {
        TouchHardening.checkLoadFailures({ paradigmName: '画钟测试' }).then(function() { done(); });
      } else { done(); }
    },
  };

  const timeline = [preloadTrial, loadCheckTrial, voiceGuideTrial, drawingTrial, saveCommandData, copyInstrPage, copyDrawingTrial, attentionProbe, saveCopyData];

  /* Camera recording (before jsPsych starts) */
  await ParadigmCamera.init('clock', subjectId);

  jsPsych.run(timeline);
})();
