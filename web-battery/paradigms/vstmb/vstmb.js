/**
 * VSTMB (Visual Short-Term Memory Binding) — jsPsych 8 Web Implementation
 *
 * 3 conditions: Object (shape only), Color (color only), Binding (shape+color)
 * Each condition: 4 practice + 18 formal = 22 trials
 * Trial flow: fixation 500ms -> study 2000ms -> retention 900ms -> probe (same/different, 5s timeout)
 * SDT metrics: A', beta (Hit/Miss/FA/CR)
 *
 * Stimulus structure:
 *   stimuli/vstmb/shape/{A-F}.webp          — Object condition (black-white shapes)
 *   stimuli/vstmb/color/{1-6}/{a-f}.webp    — Color condition (lowercase filenames)
 *   stimuli/vstmb/binding/{A-F}/{1-6}.webp — Binding condition
 */

(async function () {
  'use strict';

  // ==================== Checkpoint: incremental data saving ====================
  // Inline implementation (no ES module dependency).
  // Non-blocking — save failures never affect experiment flow.
  var _checkpoint = {
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
      try { localStorage.setItem(lsKey, csv); } catch (e) { /* quota exceeded, ignore */ }
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

    /** Immediate save — use at condition/block boundaries */
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

  // ==================== Configuration ====================
  const STIMULI_BASE = '../../stimuli/vstmb';

  const CONFIG = {
    practiceTrials: 4,
    formalTrials: 18,
    timing: {
      fixation: 500,
      study: 2000,
      retention: 900,
      timeout: 5000,
      transition: 1000,
      feedbackWait: 0,   // click-to-continue
    },
    grid: {
      spacing: 190,      // px between grid cells (matches original config.json)
      objectSize: 96,    // px (matches original config.json: object_size=96)
      availablePositions: [1, 2, 3, 4, 6, 7, 8, 9], // exclude center (5)
    },
    conditions: ['Object', 'Color', 'Binding'],
    balanceOrders: {
      A: ['Object', 'Color', 'Binding'],
      B: ['Color', 'Binding', 'Object'],
      C: ['Binding', 'Object', 'Color'],
    },
    shapeIds: ['A', 'B', 'C', 'D', 'E', 'F'],
    colorIds: ['1', '2', '3', '4', '5', '6'],
  };

  // Grid positions relative to center (px offsets)
  // Layout:  1  2  3
  //          4  5  6
  //          7  8  9
  const SP = CONFIG.grid.spacing;
  const GRID_OFFSETS = {
    1: [-SP,  SP], 2: [  0,  SP], 3: [ SP,  SP],
    4: [-SP,   0], 5: [  0,   0], 6: [ SP,   0],
    7: [-SP, -SP], 8: [  0, -SP], 9: [ SP, -SP],
  };

  // ==================== URL Params ====================
  const urlParams = new URLSearchParams(window.location.search);
  const SUBJECT_ID = urlParams.get('sid') || 'TEST';
  const BALANCE = urlParams.get('balance') || 'A';

  // F4 (2026-04-19): Block-level resume 参数
  let START_BLOCK = 0;
  let SKIP_INSTRUCTIONS = false;
  if (window.ProgressAPI && window.ProgressAPI.getResumeParams) {
    const _rp = window.ProgressAPI.getResumeParams();
    START_BLOCK = _rp.startBlock;
    SKIP_INSTRUCTIONS = _rp.skipInstructions;
  }
  // Clamp: 避免 startBlock >= totalBlocks 导致空 timeline
  const _condOrderPreview = (typeof CONFIG !== 'undefined' && CONFIG.balanceOrders) ? (CONFIG.balanceOrders[BALANCE] || CONFIG.balanceOrders.A) : ['Object','Color','Binding'];
  if (START_BLOCK >= _condOrderPreview.length) {
    console.warn('[VSTMB] startBlock', START_BLOCK, '>= totalBlocks, falling back to 0');
    START_BLOCK = 0;
    SKIP_INSTRUCTIONS = false;
    if (window.ProgressAPI) window.ProgressAPI.clear('vstmb', SUBJECT_ID);
  }

  // F4: 暴露全局状态给 touch-hardening 三指退出使用
  window.__paradigmName = 'vstmb';
  window.__subjectId = SUBJECT_ID;
  window.__totalBlocks = _condOrderPreview.length;
  window.__currentBlockIdx = START_BLOCK;
  window.__blockOrder = _condOrderPreview;
  window.__balance = BALANCE;

  // ==================== Image Path Helpers ====================
  function objectImagePath(shapeId) {
    return `${STIMULI_BASE}/shape/${shapeId}.webp`;
  }

  function colorImagePath(colorId, shapeId) {
    // Color directory uses lowercase filenames
    return `${STIMULI_BASE}/color/${colorId}/${shapeId.toLowerCase()}.webp`;
  }

  function bindingImagePath(shapeId, colorId) {
    return `${STIMULI_BASE}/binding/${shapeId}/${colorId}.webp`;
  }

  function getImagePath(condition, shapeIdx, colorIdx) {
    const shapeId = CONFIG.shapeIds[shapeIdx];
    const colorId = colorIdx >= 0 ? CONFIG.colorIds[colorIdx] : null;
    if (condition === 'Object') return objectImagePath(shapeId);
    if (condition === 'Color')  return colorImagePath(colorId, shapeId);
    if (condition === 'Binding') return bindingImagePath(shapeId, colorId);
    return '';
  }

  // ==================== Preload List ====================
  function getAllImagePaths() {
    const paths = [];
    // Object
    CONFIG.shapeIds.forEach(s => paths.push(objectImagePath(s)));
    // Color
    CONFIG.colorIds.forEach(c => {
      CONFIG.shapeIds.forEach(s => paths.push(colorImagePath(c, s)));
    });
    // Binding
    CONFIG.shapeIds.forEach(s => {
      CONFIG.colorIds.forEach(c => paths.push(bindingImagePath(s, c)));
    });
    return paths;
  }

  // ==================== Random Helpers ====================
  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function sampleWithout(arr, n) {
    return shuffle(arr).slice(0, n);
  }

  function randInt(max) {
    return Math.floor(Math.random() * max);
  }

  // ==================== Trial Generation ====================
  function generateTrialStimuli(condition, trialType) {
    const positions = CONFIG.grid.availablePositions;
    const studyPositions = sampleWithout(positions, 2);
    const probePositions = sampleWithout(positions, 2);

    const studyShapes = sampleWithout([0,1,2,3,4,5], 2);
    let studyColors = condition === 'Object' ? [-1, -1] : sampleWithout([0,1,2,3,4,5], 2);

    let probeShapes, probeColors;

    if (trialType === 'Same') {
      probeShapes = studyShapes.slice();
      probeColors = studyColors.slice();
    } else {
      if (condition === 'Object') {
        probeShapes = getDifferentIndices(studyShapes, 6);
        probeColors = [-1, -1];
      } else if (condition === 'Color') {
        probeShapes = studyShapes.slice();
        probeColors = getDifferentIndices(studyColors, 6);
      } else {
        // Binding: swap colors between the two objects
        probeShapes = studyShapes.slice();
        probeColors = [studyColors[1], studyColors[0]];
      }
    }

    return {
      studyPositions, studyShapes, studyColors,
      probePositions, probeShapes, probeColors,
      trialType,
    };
  }

  function getDifferentIndices(current, total) {
    const result = [];
    for (const idx of current) {
      const candidates = [];
      for (let i = 0; i < total; i++) {
        if (i !== idx && !result.includes(i)) candidates.push(i);
      }
      result.push(candidates[randInt(candidates.length)]);
    }
    return result;
  }

  function generateTrialList(condition, numTrials, isPractice) {
    const trials = [];
    if (isPractice) {
      // Practice: trial 1 = Same, trial 2 = Different, rest random
      trials.push(generateTrialStimuli(condition, 'Same'));
      trials.push(generateTrialStimuli(condition, 'Different'));
      for (let i = 2; i < numTrials; i++) {
        trials.push(generateTrialStimuli(condition, Math.random() < 0.5 ? 'Same' : 'Different'));
      }
    } else {
      // Formal: 50% Same, 50% Different, shuffled
      const halfSame = Math.floor(numTrials / 2);
      const types = [];
      for (let i = 0; i < halfSame; i++) types.push('Same');
      for (let i = halfSame; i < numTrials; i++) types.push('Different');
      const shuffled = shuffle(types);
      shuffled.forEach(t => trials.push(generateTrialStimuli(condition, t)));
    }
    return trials;
  }

  // ==================== Data Storage ====================
  const allTrialData = [];

  function recordTrial(data) {
    allTrialData.push(data);
  }

  // ==================== SDT Calculations ====================
  function calcAPrime(hitRate, faRate) {
    const h = Math.max(0.01, Math.min(0.99, hitRate));
    const g = Math.max(0.01, Math.min(0.99, faRate));
    if (g <= h) {
      return 0.5 + (h - g) * (1 + h - g) / (4 * h * (1 - g));
    } else {
      return 0.5 - (g - h) * (1 + g - h) / (4 * g * (1 - h));
    }
  }

  function inverseNormalCDF(p) {
    // Abramowitz & Stegun approximation 26.2.23
    // For p in (0, 0.5]: use p directly, result is negative
    // For p in (0.5, 1): use 1-p, result is positive
    let sign, pp;
    if (p > 0.5) { sign = 1; pp = 1 - p; }
    else { sign = -1; pp = p; }
    const a0 = 2.515517, a1 = 0.802853, a2 = 0.010328;
    const b1 = 1.432788, b2 = 0.189269, b3 = 0.001308;
    const t = Math.sqrt(-2 * Math.log(pp));
    const z = t - (a0 + a1*t + a2*t*t) / (1 + b1*t + b2*t*t + b3*t*t*t);
    return sign * z;
  }

  function calcBeta(hitRate, faRate) {
    const h = Math.max(0.01, Math.min(0.99, hitRate));
    const g = Math.max(0.01, Math.min(0.99, faRate));
    try {
      const zH = inverseNormalCDF(h);
      const zG = inverseNormalCDF(g);
      return Math.exp((zG*zG - zH*zH) / 2);
    } catch(e) {
      return 1.0;
    }
  }

  function computeMetrics(condition) {
    const formal = allTrialData.filter(d => d.condition === condition && !d.is_practice);
    if (formal.length === 0) return {};

    let hits = 0, misses = 0, fa = 0, cr = 0;
    formal.forEach(t => {
      if      (t.sdt_classification === 'Hit')  hits++;
      else if (t.sdt_classification === 'Miss') misses++;
      else if (t.sdt_classification === 'FA')   fa++;
      else if (t.sdt_classification === 'CR')   cr++;
    });

    const hitRate = (hits + misses) > 0 ? hits / (hits + misses) : 0;
    const faRate  = (fa + cr) > 0 ? fa / (fa + cr) : 0;
    const accuracy = formal.filter(t => t.accuracy === 1).length / formal.length;
    const validRTs = formal.filter(t => !t.timeout && t.reaction_time > 0).map(t => t.reaction_time);
    const meanRT = validRTs.length > 0 ? validRTs.reduce((a,b)=>a+b,0)/validRTs.length : 0;

    return {
      condition, total: formal.length, accuracy: Math.round(accuracy*1000)/10,
      hits, misses, fa, cr,
      hitRate: Math.round(hitRate*1000)/1000,
      faRate: Math.round(faRate*1000)/1000,
      aPrime: Math.round(calcAPrime(hitRate, faRate)*1000)/1000,
      beta: Math.round(calcBeta(hitRate, faRate)*1000)/1000,
      meanRT: Math.round(meanRT),
    };
  }

  // ==================== CSV Export ====================
  function generateCSV() {
    const BOM = '\uFEFF';
    const fields = [
      'subject_id','trial_index','is_practice','condition','trial_type',
      'response_key','reaction_time','accuracy','sdt_classification',
      'timeout',
      'study_pos_1','study_obj_id_1','study_color_id_1',
      'study_pos_2','study_obj_id_2','study_color_id_2',
      'probe_pos_1','probe_obj_id_1','probe_color_id_1',
      'probe_pos_2','probe_obj_id_2','probe_color_id_2',
    ];
    let csv = BOM + fields.join(',') + '\n';
    allTrialData.forEach(d => {
      csv += fields.map(f => {
        const v = d[f];
        return v === undefined || v === null ? '' : v;
      }).join(',') + '\n';
    });
    return csv;
  }

  function generateSummaryJSON() {
    const metrics = {};
    CONFIG.conditions.forEach(c => { metrics[c] = computeMetrics(c); });
    return JSON.stringify({
      subject_id: SUBJECT_ID,
      balance_order: BALANCE,
      timestamp: new Date().toISOString(),
      conditions: metrics,
      total_trials: allTrialData.length,
      formal_trials: allTrialData.filter(d => !d.is_practice).length,
    }, null, 2);
  }

  function downloadFile(content, filename, mime) {
    const blob = new Blob([content], { type: mime || 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ==================== Rendering Helpers ====================
  function renderGrid(items, condition) {
    // items: [{pos, shapeIdx, colorIdx}]
    // Grid container = 2*spacing + objectSize = 2*190+96 = 476 ≈ 480px
    const sz = CONFIG.grid.objectSize;
    const containerSize = CONFIG.grid.spacing * 2 + sz; // 190*2+96 = 476
    const center = containerSize / 2;
    let html = `<div class="vstmb-trial-wrapper"><div class="vstmb-grid-container" style="width:${containerSize}px;height:${containerSize}px;">`;
    items.forEach(item => {
      const [ox, oy] = GRID_OFFSETS[item.pos];
      // CSS: center of container; y is inverted (top-down)
      const left = center + ox - sz/2;
      const top  = center - oy - sz/2;
      const src = getImagePath(condition, item.shapeIdx, item.colorIdx);
      html += `<div class="vstmb-grid-cell" style="left:${left}px;top:${top}px;width:${sz}px;height:${sz}px;">` +
              `<img src="${src}" width="${sz}" height="${sz}" draggable="false"></div>`;
    });
    html += '</div></div>';
    return html;
  }

  function responseBarHTML(active) {
    const cls = active ? 'vstmb-response-bar active' : 'vstmb-response-bar';
    return `<div class="${cls}" id="vstmb-response-bar">` +
      `<button class="vstmb-btn${active?'':' disabled'}" id="vstmb-btn-same">相同</button>` +
      `<button class="vstmb-btn${active?'':' disabled'}" id="vstmb-btn-diff">不同</button>` +
      `</div>`;
  }

  // ==================== Instruction HTML Helpers ====================

  /** Reusable small image tag for instruction examples */
  function instrImg(condition, shapeIdx, colorIdx, size) {
    size = size || 96;
    const src = getImagePath(condition, shapeIdx, colorIdx);
    return `<img src="${src}" width="${size}" height="${size}" style="vertical-align:middle;border-radius:8px;" draggable="false">`;
  }

  /** Build the 4-step trial flow diagram (CSS-drawn, no external images) */
  function trialFlowHTML() {
    // Uses actual stimuli to show: observe -> disappear -> reappear -> judge
    const imgA = instrImg('Object', 0, -1, 80); // hat
    const imgB = instrImg('Object', 1, -1, 80); // mug
    return `
      <div class="instr-flow">
        <div class="instr-flow-step">
          <div class="instr-flow-label">1. 观察</div>
          <div class="instr-flow-box">
            <div class="instr-flow-grid">
              <span class="instr-flow-cell" style="grid-area:1/1">${imgA}</span>
              <span class="instr-flow-cell" style="grid-area:2/3">${imgB}</span>
            </div>
          </div>
        </div>
        <div class="instr-flow-arrow"></div>
        <div class="instr-flow-step">
          <div class="instr-flow-label">2. 短暂消失</div>
          <div class="instr-flow-box instr-flow-blank">
            <span style="font-size:40px;color:#bbb;">...</span>
          </div>
        </div>
        <div class="instr-flow-arrow"></div>
        <div class="instr-flow-step">
          <div class="instr-flow-label">3. 再次出现</div>
          <div class="instr-flow-box">
            <div class="instr-flow-grid">
              <span class="instr-flow-cell" style="grid-area:1/1">${imgA}</span>
              <span class="instr-flow-cell" style="grid-area:2/3">${imgB}</span>
            </div>
          </div>
        </div>
        <div class="instr-flow-arrow"></div>
        <div class="instr-flow-step">
          <div class="instr-flow-label">4. 判断</div>
          <div class="instr-flow-judge">
            <span class="instr-mini-btn">相同</span>
            <span style="margin:0 4px;font-size:20px;color:#999;">或</span>
            <span class="instr-mini-btn">不同</span>
          </div>
        </div>
      </div>`;
  }

  /** Build the button mapping demo HTML */
  function buttonMappingHTML() {
    // Left: "Same" example; Right: "Different" example
    const imgA = instrImg('Object', 0, -1, 100);
    const imgB = instrImg('Object', 1, -1, 100);
    return `
      <div class="instr-mapping-row">
        <div class="instr-mapping-case">
          <div class="instr-mapping-title" style="color:var(--success);">一样</div>
          <div class="instr-mapping-pair">
            ${imgA}<span class="instr-eq">=</span>${imgA}
          </div>
          <div class="instr-mapping-arrow-down"></div>
          <span class="instr-mini-btn instr-btn-highlight">相同</span>
        </div>
        <div class="instr-mapping-divider"></div>
        <div class="instr-mapping-case">
          <div class="instr-mapping-title" style="color:var(--error);">不一样</div>
          <div class="instr-mapping-pair">
            ${imgA}<span class="instr-neq">&ne;</span>${imgB}
          </div>
          <div class="instr-mapping-arrow-down"></div>
          <span class="instr-mini-btn instr-btn-highlight">不同</span>
        </div>
      </div>`;
  }

  /**
   * Build condition-specific instruction HTML with "Same" and "Different" examples.
   * Uses actual stimuli so elderly participants see exactly what to expect.
   */
  function conditionInstructionHTML(condition) {
    const condCfg = {
      Object: {
        title: '请留意：物体的形状',
        desc: '只看形状是否一样，不用管颜色',
        focusTag: '形状',
        // Same: hat + mug -> hat + mug (same shapes)
        sameStudy: [ instrImg('Object', 0, -1, 100), instrImg('Object', 1, -1, 100) ],
        sameProbe: [ instrImg('Object', 0, -1, 100), instrImg('Object', 1, -1, 100) ],
        sameExplain: '形状没变',
        // Different: hat + mug -> stool + book (different shapes)
        diffStudy: [ instrImg('Object', 0, -1, 100), instrImg('Object', 1, -1, 100) ],
        diffProbe: [ instrImg('Object', 2, -1, 100), instrImg('Object', 3, -1, 100) ],
        diffExplain: '形状变了',
      },
      Color: {
        title: '请留意：物体的颜色',
        desc: '只看颜色是否一样，不用管形状',
        focusTag: '颜色',
        // Same: green-hat + purple-hat -> green-hat + purple-hat
        sameStudy: [ instrImg('Color', 0, 2, 100), instrImg('Color', 0, 3, 100) ],
        sameProbe: [ instrImg('Color', 0, 2, 100), instrImg('Color', 0, 3, 100) ],
        sameExplain: '颜色没变',
        // Different: green-hat + purple-hat -> blue-hat + yellow-hat
        diffStudy: [ instrImg('Color', 0, 2, 100), instrImg('Color', 0, 3, 100) ],
        diffProbe: [ instrImg('Color', 0, 0, 100), instrImg('Color', 0, 1, 100) ],
        diffExplain: '颜色变了',
      },
      Binding: {
        title: '请留意：形状和颜色的搭配',
        desc: '看哪个形状配哪个颜色，搭配是否一样',
        focusTag: '搭配',
        // Same: green-hat + purple-mug -> green-hat + purple-mug
        sameStudy: [ instrImg('Binding', 0, 2, 100), instrImg('Binding', 1, 3, 100) ],
        sameProbe: [ instrImg('Binding', 0, 2, 100), instrImg('Binding', 1, 3, 100) ],
        sameExplain: '搭配没变',
        // Different: green-hat + purple-mug -> purple-hat + green-mug (colors swapped)
        diffStudy: [ instrImg('Binding', 0, 2, 100), instrImg('Binding', 1, 3, 100) ],
        diffProbe: [ instrImg('Binding', 0, 3, 100), instrImg('Binding', 1, 2, 100) ],
        diffExplain: '颜色搭配交换了',
      },
    };

    const c = condCfg[condition];
    return `
      <div class="instr-condition-page">
        <div class="instr-condition-header">
          <div class="instr-condition-badge">${c.focusTag}</div>
          <div class="instr-condition-title">${c.title}</div>
          <div class="instr-condition-desc">${c.desc}</div>
        </div>

        <div class="instr-example-row">
          <div class="instr-example-card instr-same-card">
            <div class="instr-example-label" style="color:var(--success);">相同 的例子</div>
            <div class="instr-example-compare">
              <div class="instr-example-phase">
                <div class="instr-phase-label">先看到</div>
                <div class="instr-phase-items">${c.sameStudy[0]}${c.sameStudy[1]}</div>
              </div>
              <div class="instr-example-arrow"></div>
              <div class="instr-example-phase">
                <div class="instr-phase-label">再出现</div>
                <div class="instr-phase-items">${c.sameProbe[0]}${c.sameProbe[1]}</div>
              </div>
            </div>
            <div class="instr-example-verdict" style="color:var(--success);">${c.sameExplain} → 点【相同】</div>
          </div>

          <div class="instr-example-card instr-diff-card">
            <div class="instr-example-label" style="color:var(--error);">不同 的例子</div>
            <div class="instr-example-compare">
              <div class="instr-example-phase">
                <div class="instr-phase-label">先看到</div>
                <div class="instr-phase-items">${c.diffStudy[0]}${c.diffStudy[1]}</div>
              </div>
              <div class="instr-example-arrow"></div>
              <div class="instr-example-phase">
                <div class="instr-phase-label">再出现</div>
                <div class="instr-phase-items">${c.diffProbe[0]}${c.diffProbe[1]}</div>
              </div>
            </div>
            <div class="instr-example-verdict" style="color:var(--error);">${c.diffExplain} → 点【不同】</div>
          </div>
        </div>
      </div>`;
  }

  // ==================== Build jsPsych Timeline ====================
  function buildTimeline() {
    const timeline = [];

    // Voice-guided instruction config
    const AUDIO_BASE = '../../audio/vstmb';

    // 1. Preload images + audio + instruction images
    // 磁盘实际:b1=15, b2=10, b3=11(对齐 VoiceGuide steps 用量,原先写死 15 会 404 9 个)
    var _vstmbAudioFiles = [];
    var _vstmbCounts = { b1: 15, b2: 10, b3: 11 };
    Object.keys(_vstmbCounts).forEach(function(b) {
      var n = _vstmbCounts[b];
      for (var i = 1; i <= n; i++) _vstmbAudioFiles.push(AUDIO_BASE + '/' + b + '_s' + String(i).padStart(2,'0') + '.mp3');
    });
    timeline.push({
      type: jsPsychPreload,
      images: getAllImagePaths().concat(['img/block1.webp','img/block2.webp','img/block3.webp']),
      audio: _vstmbAudioFiles,
      show_progress_bar: true,
      message: '<p style="font-size:32px;">正在加载，请稍候...</p>',
      continue_after_error: true,
    });
    // 2026-04-19: 预加载后检查失败资源
    timeline.push({
      type: jsPsychCallFunction, async: true,
      func: function(done) {
        if (typeof TouchHardening !== 'undefined' && TouchHardening.checkLoadFailures) {
          TouchHardening.checkLoadFailures({ paradigmName: 'VSTMB 视觉记忆' }).then(function() { done(); });
        } else { done(); }
      },
    });
    const vstmbVoiceConfig = {
      Object: {
        image: 'img/block1.webp',
        btnRegion: { x: '80.1%', y: '4.9%', w: '15%', h: '8.2%' },
        steps: [
          { region: { x: '19.6%', y: '25.6%', w: '59.7%', h: '17%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s01.mp3`, subtitle: '屏幕上会出现一组物体，请仔细看' },
            { audio: `${AUDIO_BASE}/b1_s02.mp3`, subtitle: '然后这组物体会短暂消失' },
            { audio: `${AUDIO_BASE}/b1_s03.mp3`, subtitle: '接着会再出现一组物体' },
          ] },
          { region: { x: '42.5%', y: '26%', w: '36.2%', h: '12.7%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s04.mp3`, subtitle: '请比较消失前和消失后的这组物体' },
            { audio: `${AUDIO_BASE}/b1_s05.mp3`, subtitle: '不是比较同时出现的两个物体，是比较前后两次出现的变化' },
          ] },
          { region: { x: '9.5%', y: '61.3%', w: '14.5%', h: '12.5%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s06.mp3`, subtitle: '比如消失前是帽子和杯子' },
          ] },
          { region: { x: '30.6%', y: '61.1%', w: '14.6%', h: '12.5%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s07.mp3`, subtitle: '消失后变成了书本和椅子，形状变了' },
          ] },
          { region: { x: '16.9%', y: '74.4%', w: '20.9%', h: '16.8%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s08.mp3`, subtitle: '所以点击不同按钮' },
          ] },
          { region: { x: '54.9%', y: '61.5%', w: '14.3%', h: '11.7%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s09.mp3`, subtitle: '再看这边，消失前是帽子和杯子' },
          ] },
          { region: { x: '75.6%', y: '61.4%', w: '15%', h: '12.2%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s10.mp3`, subtitle: '消失后再次出现形状没变' },
            { audio: `${AUDIO_BASE}/b1_s11.mp3`, subtitle: '正式游戏时位置可能会改变，但只需要注意形状是否发生改变' },
          ] },
          { region: { x: '61.8%', y: '74.4%', w: '20.9%', h: '16.5%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s12.mp3`, subtitle: '形状没变，点击相同按钮' },
          ] },
          { region: { x: '32.7%', y: '51.6%', w: '40.2%', h: '7.1%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s13.mp3`, subtitle: '只看形状有没有变，不用管颜色和位置' },
          ] },
          { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s14.mp3`, subtitle: '明白了就点击开始练习' },
            { audio: `${AUDIO_BASE}/b1_s15.mp3`, subtitle: '有不清楚的可以问工作人员' },
          ] },
        ],
      },
      Color: {
        image: 'img/block2.webp',
        btnRegion: { x: '80.1%', y: '4.9%', w: '15%', h: '8.2%' },
        steps: [
          { region: { x: '20.2%', y: '25.8%', w: '60.1%', h: '16.1%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s01.mp3`, subtitle: '这次规则变了，请关注颜色' },
          ] },
          { region: { x: '21.5%', y: '26.3%', w: '57%', h: '11.9%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s02.mp3`, subtitle: '请比较消失前和消失后物体的颜色是否一样' },
          ] },
          { region: { x: '9.6%', y: '61.6%', w: '14.7%', h: '12.3%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s03.mp3`, subtitle: '比如消失前是绿色帽子和蓝色杯子' },
          ] },
          { region: { x: '30.4%', y: '61.6%', w: '15.1%', h: '12.4%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s04.mp3`, subtitle: '消失后依旧是绿色帽子和蓝色杯子，没有改变' },
          ] },
          { region: { x: '18.1%', y: '75.3%', w: '18%', h: '15%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s05.mp3`, subtitle: '所以点击相同' },
          ] },
          { region: { x: '54.8%', y: '61.8%', w: '14.8%', h: '11.8%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s06.mp3`, subtitle: '再看这边，消失前是绿色帽子和蓝色杯子' },
          ] },
          { region: { x: '75.8%', y: '61.7%', w: '14.8%', h: '11.9%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s07.mp3`, subtitle: '消失后，变成了暗绿色帽子和紫色杯子' },
          ] },
          { region: { x: '62.4%', y: '74.8%', w: '18.6%', h: '15.6%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s08.mp3`, subtitle: '颜色发生改变，所以点不同按钮' },
          ] },
          { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s09.mp3`, subtitle: '明白了就点击开始练习' },
          ] },
        ],
      },
      Binding: {
        image: 'img/block3.webp',
        btnRegion: { x: '80.1%', y: '4.9%', w: '15%', h: '8.2%' },
        steps: [
          { region: { x: '20.5%', y: '25%', w: '59.2%', h: '16.3%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s01.mp3`, subtitle: '最后一个环节，这次要同时看颜色和形状的搭配' },
          ] },
          { region: { x: '21.5%', y: '25.8%', w: '57.1%', h: '12.6%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s02.mp3`, subtitle: '请比较每个物体的颜色和形状搭配是否和之前一样' },
          ] },
          { region: { x: '9%', y: '61.3%', w: '15.5%', h: '12.5%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s03.mp3`, subtitle: '比如消失前绿色帽子配蓝色杯子' },
          ] },
          { region: { x: '30.3%', y: '61.5%', w: '15.2%', h: '12.3%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s04.mp3`, subtitle: '消失后颜色互换了，帽子变蓝色杯子变绿色' },
          ] },
          { region: { x: '13.8%', y: '74.2%', w: '27.5%', h: '16.6%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s05.mp3`, subtitle: '搭配变了，点击不同按钮' },
          ] },
          { region: { x: '54.1%', y: '61.2%', w: '36.8%', h: '12.8%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s06.mp3`, subtitle: '再看这边，每个物体的颜色和形状都没变' },
            { audio: `${AUDIO_BASE}/b3_s07.mp3`, subtitle: '依旧是绿色帽子和蓝色杯子' },
          ] },
          { region: { x: '58.2%', y: '74.6%', w: '28.4%', h: '16.5%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s08.mp3`, subtitle: '搭配没变，点击相同按钮' },
          ] },
          { region: { x: '32.7%', y: '51.7%', w: '43.9%', h: '7.1%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s09.mp3`, subtitle: '颜色、形状、搭配都要注意，只有位置不用管' },
          ] },
          { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s10.mp3`, subtitle: '明白了就点击开始练习' },
          ] },
        ],
      },
    };

    // 2-3. Welcome pages removed — voice guide per condition replaces them

    // 4. Condition blocks
    const conditionOrder = CONFIG.balanceOrders[BALANCE] || CONFIG.balanceOrders.A;
    const condLabels = {Object:'形状', Color:'颜色', Binding:'搭配'};

    let condFormalCounter = 0; // 条件内计数，每条件重置

    conditionOrder.forEach((condition, blockIdx) => {
      // F4 (2026-04-19): 跳过已完成的 block(resume 模式)
      if (blockIdx < START_BLOCK) return;

      const condNames = {Object:'物体形状', Color:'物体颜色', Binding:'形状和颜色的搭配'};
      const focusText = condNames[condition];
      const blockNum = blockIdx + 1;
      const totalBlocks = conditionOrder.length;

      // F4: resume 且主试选了"跳过指导语" — 用简短提醒代替完整 VoiceGuide
      const isResumeSkipInstr = SKIP_INSTRUCTIONS && blockIdx === START_BLOCK && START_BLOCK > 0;
      const vcfg = vstmbVoiceConfig[condition];
      if (isResumeSkipInstr) {
        // 简短提醒 — 一页按钮,不放 VoiceGuide
        timeline.push({
          type: jsPsychHtmlButtonResponse,
          stimulus: `
            <div class="instruction-page">
              <div class="instruction-title">接着测试 (第 ${blockNum} 部分 / 共 ${totalBlocks})</div>
              <div class="instruction-body">
                继续留意 <b style="color:var(--primary);">【${focusText}】</b> 是否变化<br><br>
                一样 → <b>相同</b> &nbsp;&nbsp; 不一样 → <b>不同</b><br><br>
                <span style="font-size:22px;color:#666;">准备好后点击继续</span>
              </div>
            </div>`,
          choices: ['继续'],
          button_html: (c) => `<button class="jspsych-btn" style="margin-top:24px;">${c}</button>`,
        });
      } else if (vcfg) {
        // 完整 VoiceGuide(原有逻辑)
        timeline.push({
          type: jsPsychCallFunction,
          async: true,
          func: async function(done) {
            await VoiceGuide.show({
              image: vcfg.image,
              btnRegion: vcfg.btnRegion,
              buttonText: '开始练习',
              pauseBetween: 500,
              steps: vcfg.steps,
            });
            done();
          },
        });
      }

      timeline.push({
        type: jsPsychCallFunction,
        func: function() {
          if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
            ParadigmCamera.addEvent('condition_start', { condition: condition, block_index: blockIdx + 1 });
          }
        },
      });

      // Practice loop with accuracy gating
      const practiceNode = {
        timeline: [buildPracticeLoop(condition)],
      };
      timeline.push(practiceNode);

      // Formal instruction — brief reminder
      timeline.push({
        type: jsPsychHtmlButtonResponse,
        stimulus: `
          <div class="instruction-page">
            <div class="instruction-title">正式测试</div>
            <div class="instruction-body">
              接下来是正式测试<br><br>
              继续留意 <b style="color:var(--primary);">【${focusText}】</b> 是否变化<br>
              一样 → <b>相同</b> &nbsp;&nbsp; 不一样 → <b>不同</b>
            </div>
          </div>`,
        choices: ['继续'],
        button_html: (c) => `<button class="jspsych-btn" style="margin-top:24px;">${c}</button>`,
      });

      // 3-2-1 倒计时 (VSTMB 灰底 #808080 + 纯黑 #000000 字,对齐原版 PsychoPy text_color [-1,-1,-1])
      // VSTMB 只加载了 html-button-response,用空 choices + trial_duration 自动跳转
      for (let c = 3; c >= 1; c--) {
        timeline.push({
          type: jsPsychHtmlButtonResponse,
          stimulus: `<div style="font-size:14vh;color:#000000;font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;">${c}</div>`,
          choices: [],
          trial_duration: 1000,
          response_ends_trial: false,
        });
      }

      // Formal trials
      const formalTrials = generateTrialList(condition, CONFIG.formalTrials, false);
      condFormalCounter = 0; // 每条件重置
      const condTotal = CONFIG.formalTrials; // 18
      formalTrials.forEach((trial, idx) => {
        condFormalCounter++;
        const trialNum = condFormalCounter;
        // 进度计数（注视点前插入）
        timeline.push({
          type: jsPsychCallFunction,
          func: function() {
            var existing = document.getElementById('_vstmb_progress');
            if (existing) existing.remove();
            var div = document.createElement('div');
            div.id = '_vstmb_progress';
            div.style.cssText = 'position:fixed;top:12px;right:24px;color:rgba(0,0,0,0.3);font-size:36px;font-family:"PingFang SC","Microsoft YaHei",sans-serif;pointer-events:none;z-index:9999;';
            div.textContent = trialNum + ' / ' + condTotal;
            document.body.appendChild(div);
          },
        });
        timeline.push(...buildTrialTimeline(condition, trial, 'formal', blockIdx * 100 + idx));
      });

      // 清除进度计数
      timeline.push({ type: jsPsychCallFunction, func: function() {
        var el = document.getElementById('_vstmb_progress');
        if (el) el.remove();
      }});

      // Checkpoint: force save at condition boundary (after all formal trials)
      timeline.push({
        type: jsPsychCallFunction,
        func: function() {
          if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
            ParadigmCamera.addEvent('condition_end', { condition: condition, block_index: blockIdx + 1 });
          }
          _checkpoint.forceSave();
        },
      });

      // 注意力探针（每个条件后）
      timeline.push(buildAttentionProbe(jsPsych, 'vstmb', 'after_' + condition.toLowerCase()));

      // F4 (2026-04-19): 写 progress 标记本 block 已完成
      if (window.ProgressAPI && window.ProgressAPI.writeTrial) {
        timeline.push(window.ProgressAPI.writeTrial('vstmb', SUBJECT_ID, blockIdx, conditionOrder.length, {
          blockOrder: conditionOrder,
          balance: BALANCE,
        }));
      }

      // Rest between blocks (not after last) — 提示下一条件
      if (blockIdx < conditionOrder.length - 1) {
        const nextCond = conditionOrder[blockIdx + 1];
        const nextLabel = condLabels[nextCond];
        timeline.push({
          type: jsPsychHtmlButtonResponse,
          stimulus: `
            <div class="instruction-page">
              <div class="instruction-body" style="font-size:30px;margin-top:24px;">
                接下来是第 ${blockNum + 1} 部分：留意<b>【${nextLabel}】</b><br><br>
                准备好后点击继续
              </div>
            </div>`,
          choices: ['继续'],
          button_html: (c) => `<button class="jspsych-btn" style="margin-top:24px;">${c}</button>`,
        });
      }
    });

    // 5. Save data and show completion
    let _dataSaved = false;
    timeline.push({
      type: jsPsychCallFunction,
      async: true,
      func: async function(done) {
        if (_dataSaved) { done(); return; }
        _dataSaved = true;
        const ts = formatTimestamp();
        const csvFilename = `VSTMB_${SUBJECT_ID}_${ts}.csv`;
        let csvData = generateCSV();
        // F4 (2026-04-19): 续写场景 — 合并上次会话的 checkpoint CSV
        if (window.ProgressAPI && window.ProgressAPI.getPrior) {
          const priorCSV = window.ProgressAPI.getPrior('vstmb', SUBJECT_ID);
          if (priorCSV) {
            csvData = window.ProgressAPI.merge(priorCSV, csvData);
            console.log('[VSTMB] merged prior CSV with new session,final rows:', csvData.split('\n').length - 2);
          }
        }
        const jsonFilename = `VSTMB_${SUBJECT_ID}_${ts}_summary.json`;
        const jsonData = generateSummaryJSON();
        // Try server save, fallback to download
        await trySaveData(csvFilename, csvData, jsonFilename, jsonData);
        if (typeof LocalPack !== 'undefined') {
          LocalPack.add(csvFilename, csvData);
          LocalPack.add(jsonFilename, jsonData);
        }
        // Clear checkpoint — experiment completed normally, full data saved
        _checkpoint.clear();
        // Stop camera recording and save video
        try { await ParadigmCamera.stopAndSave(); } catch (e) { console.warn('[vstmb] camera stop skipped:', e.message); }
        done();
      },
    });

    // (End screen is handled by showEndScreen in on_finish callback)

    return timeline;
  }

  // ==================== Practice Loop ====================
  function buildPracticeLoop(condition) {
    // 2026-04-18 bug 修复:
    //   原实现把 attempt 计数存在 window._vstmb_practice_attempt,
    //   每次循环进入 timeline 都会被内部 callFunction 重置回 0,
    //   导致 attempt 永远累加不到 MAX=2 → 准确率达不到 70% 时死循环。
    // 改成闭包局部变量 attemptCount,scoped 到这次 buildPracticeLoop 调用,
    //   loop_function 捕获后跨迭代共享;新 condition 会新调一次 buildPracticeLoop,
    //   自然重新初始化。
    let attemptCount = 0;
    return {
      timeline: [{
        type: jsPsychCallFunction,
        func: function() {
          // 每次迭代重置 correct/total/counter,但 attempt 由闭包 attemptCount 控制
          window._vstmb_practice_correct = 0;
          window._vstmb_practice_total = 0;
          window._vstmb_practice_counter = 0;
        }
      },
      ...buildPracticeTrials(condition),
      {
        type: jsPsychHtmlButtonResponse,
        stimulus: function() {
          const acc = window._vstmb_practice_total > 0
            ? window._vstmb_practice_correct / window._vstmb_practice_total : 0;
          if (acc < 0.70 && attemptCount < 1) {
            // 准确率不够 + 还有机会重来 → "再练一遍"
            return `<div class="instruction-page">
              <div class="instruction-body" style="color:var(--error);">
                我们再练一遍，没关系
              </div>
            </div>`;
          }
          if (acc < 0.70) {
            // 准确率仍不够但已达最大尝试 → 直接进入正式,不解释
            return `<div class="instruction-page">
              <div class="instruction-body">
                进入正式测试
              </div>
            </div>`;
          }
          return `<div class="instruction-page">
            <div class="instruction-body" style="color:var(--success);">
              练习结束，做得不错！
            </div>
          </div>`;
        },
        choices: ['继续'],
        button_html: (c) => `<button class="jspsych-btn" style="margin-top:24px;">${c}</button>`,
      }],
      loop_function: function() {
        const acc = window._vstmb_practice_total > 0
          ? window._vstmb_practice_correct / window._vstmb_practice_total : 0;
        attemptCount += 1;
        return acc < 0.70 && attemptCount < 2; // 70% threshold, max 2 attempts (原值,现在真的生效)
      }
    };
  }

  function buildPracticeTrials(condition) {
    const trials = generateTrialList(condition, CONFIG.practiceTrials, true);
    const practiceTotal = trials.length;
    const nodes = [];
    trials.forEach((trial, idx) => {
      // 练习进度
      const pNum = idx + 1;
      nodes.push({
        type: jsPsychCallFunction,
        func: function() {
          var existing = document.getElementById('_vstmb_progress');
          if (existing) existing.remove();
          var div = document.createElement('div');
          div.id = '_vstmb_progress';
          div.style.cssText = 'position:fixed;top:12px;right:24px;color:rgba(0,0,0,0.3);font-size:36px;font-family:"PingFang SC","Microsoft YaHei",sans-serif;pointer-events:none;z-index:9999;';
          div.textContent = '练习 ' + pNum + ' / ' + practiceTotal;
          document.body.appendChild(div);
        },
      });
      nodes.push(...buildTrialTimeline(condition, trial, 'practice', idx));
    });
    return nodes;
  }

  // ==================== Single Trial Timeline ====================
  function buildTrialTimeline(condition, trial, phase, globalIdx) {
    const nodes = [];
    const isPractice = phase === 'practice';

    // Fixation
    nodes.push({
      type: jsPsychHtmlButtonResponse,
      stimulus: `<div class="vstmb-trial-wrapper"><div style="font-size:80px;color:var(--text);">+</div></div>`,
      choices: [],
      trial_duration: CONFIG.timing.fixation,
      response_ends_trial: false,
      css_classes: ['vstmb-trial'],
    });

    // Study phase: show 2 items on grid
    const studyItems = [
      { pos: trial.studyPositions[0], shapeIdx: trial.studyShapes[0], colorIdx: trial.studyColors[0] },
      { pos: trial.studyPositions[1], shapeIdx: trial.studyShapes[1], colorIdx: trial.studyColors[1] },
    ];
    nodes.push({
      type: jsPsychHtmlButtonResponse,
      stimulus: renderGrid(studyItems, condition),
      choices: [],
      trial_duration: CONFIG.timing.study,
      response_ends_trial: false,
      on_start: function() {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('study_onset', { trial_index: globalIdx, condition: condition });
        }
      },
    });

    // Retention (blank with buttons)
    nodes.push({
      type: jsPsychHtmlButtonResponse,
      stimulus: `<div style="height:400px;"></div>`,
      choices: [],
      trial_duration: CONFIG.timing.retention,
      response_ends_trial: false,
    });

    // Probe phase: show 2 items + active response buttons
    const probeItems = [
      { pos: trial.probePositions[0], shapeIdx: trial.probeShapes[0], colorIdx: trial.probeColors[0] },
      { pos: trial.probePositions[1], shapeIdx: trial.probeShapes[1], colorIdx: trial.probeColors[1] },
    ];

    nodes.push({
      type: jsPsychHtmlButtonResponse,
      stimulus: renderGrid(probeItems, condition),
      choices: ['相同', '不同'],
      button_html: (choice) => `<button class="jspsych-btn">${choice}</button>`,
      button_layout: 'flex',
      css_classes: ['vstmb-probe'],
      trial_duration: CONFIG.timing.timeout,
      response_ends_trial: true,
      on_start: function() {
        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('probe_onset', { trial_index: globalIdx, condition: condition, is_same: trial.trialType === 'Same' });
        }
      },
      on_finish: function(data) {
        if (typeof TouchHardening !== 'undefined') TouchHardening.correctRT(data);
        // Determine response
        const responseIdx = data.response; // 0=same, 1=different, null=timeout
        let response = '', judgment = '', timeout = false;

        if (responseIdx === 0) {
          response = 'same'; judgment = 'Same';
        } else if (responseIdx === 1) {
          response = 'different'; judgment = 'Different';
        } else {
          timeout = true;
        }

        // Accuracy
        const correct = judgment === trial.trialType ? 1 : 0;

        // SDT classification
        let sdt = '';
        if (trial.trialType === 'Different' && judgment === 'Different') sdt = 'Hit';
        else if (trial.trialType === 'Different' && judgment === 'Same') sdt = 'Miss';
        else if (trial.trialType === 'Same' && judgment === 'Different') sdt = 'FA';
        else if (trial.trialType === 'Same' && judgment === 'Same') sdt = 'CR';
        else sdt = timeout ? 'Timeout' : 'Unknown';

        // Track practice accuracy
        if (isPractice) {
          window._vstmb_practice_total = (window._vstmb_practice_total || 0) + 1;
          if (correct) window._vstmb_practice_correct = (window._vstmb_practice_correct || 0) + 1;
        }

        // Record (field names match original PsychoPy TrialData)
        const trialRecord = {
          subject_id: SUBJECT_ID,
          trial_index: globalIdx,
          is_practice: isPractice,
          condition: condition,
          trial_type: trial.trialType,
          response_key: response,
          reaction_time: data.rt !== null ? data.rt : -1,
          accuracy: correct,
          sdt_classification: sdt,
          timeout: timeout ? 1 : 0,
          study_pos_1: trial.studyPositions[0],
          study_obj_id_1: CONFIG.shapeIds[trial.studyShapes[0]],
          study_color_id_1: trial.studyColors[0] >= 0 ? CONFIG.colorIds[trial.studyColors[0]] : '',
          study_pos_2: trial.studyPositions[1],
          study_obj_id_2: CONFIG.shapeIds[trial.studyShapes[1]],
          study_color_id_2: trial.studyColors[1] >= 0 ? CONFIG.colorIds[trial.studyColors[1]] : '',
          probe_pos_1: trial.probePositions[0],
          probe_obj_id_1: CONFIG.shapeIds[trial.probeShapes[0]],
          probe_color_id_1: trial.probeColors[0] >= 0 ? CONFIG.colorIds[trial.probeColors[0]] : '',
          probe_pos_2: trial.probePositions[1],
          probe_obj_id_2: CONFIG.shapeIds[trial.probeShapes[1]],
          probe_color_id_2: trial.probeColors[1] >= 0 ? CONFIG.colorIds[trial.probeColors[1]] : '',
        };
        recordTrial(trialRecord);

        if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera.isRecording()) {
          ParadigmCamera.addEvent('response', { trial_index: globalIdx, condition: condition, response: response, rt: data.rt, correct: correct });
        }

        // Checkpoint: save after each formal trial (throttled, non-blocking)
        if (!isPractice) { _checkpoint.save(); }

        // Store for feedback
        data._vstmb_correct = correct;
        data._vstmb_trial_type = trial.trialType;
        data._vstmb_condition = condition;
        data._vstmb_trial_idx = globalIdx;
      },
    });

    // Feedback (practice only)
    if (isPractice) {
      nodes.push({
        type: jsPsychHtmlButtonResponse,
        stimulus: function() {
          const lastData = jsPsych.data.get().last(1).values()[0];
          const correct = lastData._vstmb_correct;
          const idx = lastData._vstmb_trial_idx;

          const fbClass = correct ? 'correct' : 'incorrect';
          const fbText = correct ? '✓ 对了' : '没关系，再看仔细';

          const condNames = {Object:'物体形状', Color:'物体颜色', Binding:'物体与颜色的组合'};
          const cn = condNames[condition];
          let detailText = '';
          if (!correct && idx === 0) {
            detailText = `${cn}和之前一样时，点左边【相同】`;
          } else if (!correct && idx === 1) {
            detailText = `${cn}和之前不一样时，点右边【不同】`;
          } else if (!correct) {
            detailText = '相同点左边，不同点右边';
          }

          return `<div class="practice-feedback ${fbClass}">${fbText}` +
                 (detailText ? `<div class="detail">${detailText}</div>` : '') +
                 `</div>` +
                 responseBarHTML(false);
        },
        choices: [],
        trial_duration: 1500,
        response_ends_trial: false,
      });
    }

    // Transition blank
    nodes.push({
      type: jsPsychHtmlButtonResponse,
      stimulus: `<div style="height:10px;"></div>`,
      choices: [],
      trial_duration: CONFIG.timing.transition,
      response_ends_trial: false,
    });

    return nodes;
  }

  // ==================== Data Save ====================
  function formatTimestamp() {
    const d = new Date();
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
  }

  async function trySaveData(csvFilename, csvContent, jsonFilename, jsonContent) {
    // Try server first
    try {
      const resp = await safeFetch(window.location.origin + '/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paradigm: 'vstmb',
          subject_id: SUBJECT_ID,
          filename: csvFilename,
          content: csvContent,
        }),
      });
      if (resp.ok) {
        // Also save JSON summary
        const resp2 = await safeFetch(window.location.origin + '/api/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            paradigm: 'vstmb',
            subject_id: SUBJECT_ID,
            filename: jsonFilename,
            content: jsonContent,
          }),
        });
        if (!resp2.ok) throw new Error('server error');
        console.log('Data saved to server');
        return;
      }
    } catch(e) {
      console.warn('[VSTMB] server save failed, LocalPack has backup:', e);
    }
  }

  // ==================== Init Checkpoint ====================
  _checkpoint.init('vstmb', SUBJECT_ID, function () { return generateCSV(); });

  // ==================== Init jsPsych ====================
  // VSTMB 使用灰色背景（config: background_color [0.5,0.5,0.5] = #808080）
  // Override CSS variables for gray background readability
  // Original PsychoPy uses text_color [-1,-1,-1] = black on #808080
  document.body.style.background = '#808080';
  document.documentElement.style.setProperty('--bg', '#808080');
  document.documentElement.style.setProperty('--text', '#000000');
  document.documentElement.style.setProperty('--text-secondary', '#1A1A2E');

  const jsPsych = initJsPsych({
    display_element: 'jspsych-target',
    on_finish: function() {
      console.log('VSTMB experiment complete');
      showEndScreen('vstmb', SUBJECT_ID);
    },
  });

  // 修正平板浏览器 100vh 含地址栏问题（iOS Safari / Android Chrome）
  function setVhVar() {
    document.documentElement.style.setProperty('--vh', window.innerHeight * 0.01 + 'px');
  }
  setVhVar();
  window.addEventListener('resize', setVhVar);

  // Camera recording (optional — graceful skip if not enabled)
  try { await ParadigmCamera.init('vstmb', SUBJECT_ID); } catch (e) { console.warn('[vstmb] camera init skipped:', e.message); }

  jsPsych.run(buildTimeline());

})();
