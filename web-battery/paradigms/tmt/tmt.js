/**
 * TMT (Trail Making Test) — Web implementation
 * 6 sub-tasks: A0, A1, B1, B2, B3, B4
 * Canvas-based touch drawing with dual-radius collision detection
 */

import { CONFIG, getUrlParams, timestamp } from '../../lib/shared-config.js';
import { saveCSV } from '../../lib/data-sync.js';

const AUDIO_BASE = '../../audio/tmt';

// ============================================================
// Constants (matching PsychoPy source)
// ============================================================
const HARD_LIMIT_S = Infinity; // 无时间上限：让被试想画多久就画多久
const STALL_HINT_S = 10;
const HINT_FLASH_MS = 800;
const ERROR_FLASH_MS = 300;

// Hit detection radii (multipliers of node radius)
/* 命中判定参数 — 老年人适配
   文献依据:
   - 活动区域超出可见圆圈20% (JMIR 2023, PMC10337362, Q1 IF=6.0, N=297 HC+MCI+AD)
   - 5px容差+0.1s停顿阈值 (Frontiers Psychology 2017, PMC5384876, Q1, 50-93岁迭代测试)
   调整: 手指触控比触控笔粗，进一步放宽正确判定、收紧错误判定 */
const HIT_RADIUS_MULT = 1.10;   // 检测区: 超出可见圆圈10% (文献20%略收)
const CORE_HIT_MULT = 0.65;     // 正确命中: 进入圆圈65%立即确认 (原0.45太严, 0.85太松)
const START_TOL_MULT = 1.15;    // 起点容差
const RIGHT_DWELL_S = 0.10;     // 正确停留: 100ms (文献标准0.1s, PMC5384876)
const WRONG_DWELL_S = 0.30;     // 错误停留: 300ms (原270ms, 稍微宽松避免误判)
const WRONG_CORE_MULT = 0.45;   // 错误核心: 收紧到45% (原62%, 碰边缘不轻易算错)

// Visual
const NODE_BORDER_W = 4;
const NODE_FILL = '#FFFFFF';
const NODE_BORDER = '#000000';
const TEXT_COLOR = '#000000';
const LINE_COLOR = '#3C3C3C';
const LINE_WIDTH = 8;
const ERROR_RING_COLOR = '#FF2B2B';
const HINT_RING_COLOR = '#339933';
const FOCUS_RING_COLOR = '#1565C0';
const RETURN_RING_COLOR = '#F5A623';
const DRAW_MIN_MOVE_PX = 1.5;
const RAW_SAMPLE_INTERVAL = 1000 / 60; // ~16ms

// Node rendering -- per-task caps matching PsychoPy source ratios
// PsychoPy: A0=135/1152=11.7%, B1/B2=150/1152=13.0%, A1/B3/B4=170/1000=17.0%
const NODE_CAP_RATIO = {
  A0: 0.117, B1: 0.130, B2: 0.130,
  A1: 0.170, B3: 0.170, B4: 0.170,
};
const NODE_DIAMETER_PX_DEFAULT = 135;
const FONT_SIZE_BASE = 46;

// B2 shapes
const B2_SQUARE_SIZE_MULT = 1.6; // square side = radius * mult

// ============================================================
// State
// ============================================================
let canvas, ctx;
let canvasW, canvasH;
let dpr = 1; // device pixel ratio
const { subjectId } = getUrlParams();

// Sub-task ordering: A0, B2, B1, A1, B3, B4 (group 1 default)
const TASK_ORDER = ['A0', 'B2', 'B1', 'A1', 'B3', 'B4'];

// Layout ID (derived from subject hash, like PsychoPy)
function stableLayoutId(sid) {
  let h = 0;
  for (const ch of sid) h = (h * 131 + ch.charCodeAt(0)) % 1000003;
  return (h % 3) + 1;
}

const layoutId = stableLayoutId(subjectId || 'S001');

// ============================================================
// Utility
// ============================================================
function dist(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

function normToPx(xNorm, yNorm) {
  const x = (xNorm - 0.5) * canvasW;
  const y = (0.5 - yNorm) * canvasH; // y_origin_top: 0=top, 1=bottom
  return [x, y];
}

// Convert from centered coords to canvas coords
function toCanvas(pos) {
  return [pos[0] + canvasW / 2, canvasH / 2 - pos[1]];
}

function fromCanvas(cx, cy) {
  return [cx - canvasW / 2, canvasH / 2 - cy];
}

function nowMs() {
  return performance.now();
}

function pad2(n) { return String(n).padStart(2, '0'); }

function formatTimestamp() {
  const d = new Date();
  return `${d.getFullYear()}${pad2(d.getMonth()+1)}${pad2(d.getDate())}_${pad2(d.getHours())}${pad2(d.getMinutes())}${pad2(d.getSeconds())}`;
}

// ============================================================
// Layout Loading
// ============================================================
async function loadLayout(taskType, layoutIdx) {
  // B3 layouts are in B3 dir but file name uses B4 format sometimes
  let dir = taskType;
  let prefix = `N6_v1_layout${layoutIdx}.json`;

  // A1 has bw/color subdirs -- use 'bw' as default
  if (taskType === 'A1') {
    const urls = [
      `layouts/A1/bw/${prefix}`,
      `layouts/A1/color/${prefix}`,
      `layouts/A1/${prefix}`,
    ];
    for (const url of urls) {
      try {
        const resp = await fetch(url);
        if (resp.ok) return await resp.json();
      } catch (e) { /* try next */ }
    }
    throw new Error(`Cannot load A1 layout ${layoutIdx}`);
  }

  // A0 may have bw subdir
  if (taskType === 'A0') {
    const urls = [
      `layouts/A0/${prefix}`,
      `layouts/A0/bw/${prefix}`,
    ];
    for (const url of urls) {
      try {
        const resp = await fetch(url);
        if (resp.ok) return await resp.json();
      } catch (e) { /* try next */ }
    }
    throw new Error(`Cannot load A0 layout ${layoutIdx}`);
  }

  const resp = await fetch(`layouts/${dir}/${prefix}`);
  if (!resp.ok) throw new Error(`Failed to load layout: ${dir}/${prefix}`);
  return await resp.json();
}

// 2026-04-19: 显示"加载失败"对话框,主试选择重试或跳过
// Promise resolve 'retry' 或 'skip'
function showLoadErrorDialog(taskType, errMsg, autoRetryCount) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.72);z-index:99999;display:flex;align-items:center;justify-content:center;font-family:"PingFang SC","Microsoft YaHei",sans-serif;';
    overlay.innerHTML =
      '<div style="background:white;border-radius:16px;padding:40px;text-align:center;max-width:560px;width:90%;">' +
        '<div style="font-size:32px;font-weight:bold;color:#C62828;margin-bottom:16px;">网络加载失败</div>' +
        '<div style="font-size:22px;color:#555;margin-bottom:24px;line-height:1.6;">' +
          `子任务 <b>${taskType}</b> 的布局文件加载失败<br>` +
          `已自动重试 ${autoRetryCount} 次,仍未成功。<br><br>` +
          '<span style="font-size:16px;color:#999;">' + (errMsg || '网络错误') + '</span>' +
        '</div>' +
        '<div style="background:#FFF8E1;border-radius:8px;padding:12px 18px;margin-bottom:24px;font-size:18px;color:#E65100;line-height:1.5;">' +
          '建议: 如果网络连接正常, 请点"重试"再试一次。<br>' +
          '如果反复失败, 可以选择"跳过", 但本 block 数据作废。' +
        '</div>' +
        '<div style="display:flex;gap:20px;justify-content:center;">' +
          '<button id="_tmtLoadRetry" style="padding:18px 48px;font-size:24px;font-weight:600;border:none;border-radius:12px;background:#43A047;color:white;cursor:pointer;min-width:160px;">重试</button>' +
          '<button id="_tmtLoadSkip" style="padding:18px 48px;font-size:20px;font-weight:600;border:2px solid #E0E0E0;border-radius:12px;background:#F5F5F5;color:#666;cursor:pointer;min-width:160px;">跳过此 block</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    document.getElementById('_tmtLoadRetry').addEventListener('click', () => { overlay.remove(); resolve('retry'); });
    document.getElementById('_tmtLoadSkip').addEventListener('click', () => {
      if (!confirm('确认跳过此 block? 该 block 的数据将作废且无法恢复。')) return;
      overlay.remove();
      resolve('skip');
    });
  });
}

// 带自动重试 + UI 对话框的 loadLayout 包装
// 自动重试 2 次(每次间隔 500ms), 仍失败 → 弹"重试/跳过"让主试决定
async function loadLayoutWithRetry(taskType, layoutIdx) {
  while (true) {
    let autoRetries = 0;
    let lastErr = null;
    for (let i = 0; i < 3; i++) {  // 最多 3 次 fetch (1 次首尝试 + 2 次自动重试)
      try {
        return await loadLayout(taskType, layoutIdx);
      } catch (e) {
        lastErr = e;
        autoRetries = i + 1;
        if (i < 2) {
          console.warn(`[TMT] loadLayout ${taskType} attempt ${i+1} failed, retrying:`, e.message);
          await new Promise(r => setTimeout(r, 500 * (i + 1)));  // 500ms, 1000ms
        }
      }
    }
    // 3 次全败 → 弹 UI
    console.error(`[TMT] loadLayout ${taskType} all auto-retries failed:`, lastErr);
    const action = await showLoadErrorDialog(taskType, lastErr ? lastErr.message : '', autoRetries);
    if (action === 'skip') {
      const e = new Error('SKIPPED_BY_TESTER');
      e.skipped = true;
      throw e;
    }
    // action === 'retry' → 外层 while 循环继续
  }
}

// ============================================================
// Parse nodes from layout JSON (unified across A0/B1/B2/B3/B4/A1)
// ============================================================
// Fruit image paths (numbered color PNGs with digits baked in)
const FRUIT_IMG_BASE = '../../stimuli/tmt-fruits/numbered/color/';
const FRUIT_IMG_MAP = {
  apple: (num) => `${FRUIT_IMG_BASE}apple_color_${num}.webp`,
  lemon: (num) => `${FRUIT_IMG_BASE}lemon_color_${num}.webp`,
};

// Preloaded Image cache: key = "apple_1" etc, value = HTMLImageElement
const fruitImageCache = {};
let fruitImagesReady = false;

/** Preload all fruit images needed for A1/B3/B4 (1-7 for each fruit type) */
function preloadFruitImages() {
  return new Promise((resolve) => {
    const entries = [];
    for (const fruit of ['apple', 'lemon']) {
      for (let n = 1; n <= 7; n++) {
        entries.push({ key: `${fruit}_${n}`, src: FRUIT_IMG_MAP[fruit](n) });
      }
    }
    let loaded = 0;
    const total = entries.length;
    for (const { key, src } of entries) {
      const img = new Image();
      img.onload = () => {
        fruitImageCache[key] = img;
        loaded++;
        if (loaded >= total) { fruitImagesReady = true; resolve(); }
      };
      img.onerror = () => {
        console.warn(`Failed to load fruit image: ${src}`);
        loaded++;
        if (loaded >= total) { fruitImagesReady = true; resolve(); }
      };
      img.src = src;
    }
  });
}

function parseNodes(layoutData, taskType) {
  const rawNodes = layoutData.nodes;
  const nodeSizePx = layoutData.node_size_px || layoutData.node_diam_px || NODE_DIAMETER_PX_DEFAULT;
  // PsychoPy uses min() to cap oversized layout values; apply viewport-proportional cap
  const capRatio = NODE_CAP_RATIO[taskType] || 0.130;
  const viewportCap = Math.round(canvasH * capRatio);
  const renderDiam = Math.min(nodeSizePx, viewportCap);
  const nodeRadius = renderDiam / 2;

  const previewCanvas = layoutData.preview_canvas_px;
  const canvasPx = layoutData.canvas_px; // {w, h} for B3/B4/A1

  const nodes = [];
  for (let i = 0; i < rawNodes.length; i++) {
    const nd = rawNodes[i];
    let pos;

    // Parse position -- prefer x_norm/y_norm
    if (nd.x_norm !== undefined && nd.y_norm !== undefined) {
      pos = normToPx(nd.x_norm, nd.y_norm);
    } else if (nd.x_px !== undefined && nd.y_px !== undefined && previewCanvas) {
      // Convert preview px to norm then to our canvas
      const xNorm = nd.x_px / previewCanvas[0];
      const yNorm = nd.y_px / previewCanvas[1];
      pos = normToPx(xNorm, yNorm);
    } else if (nd.x_px !== undefined && nd.y_px !== undefined && canvasPx) {
      // B3/B4/A1: canvas_px coordinate system
      const xNorm = nd.x_px / canvasPx.w;
      const yNorm = nd.y_px / canvasPx.h;
      pos = normToPx(xNorm, yNorm);
    } else if (nd.pos_px) {
      const refW = canvasPx?.w || 1400;
      const refH = canvasPx?.h || 1000;
      const xNorm = nd.pos_px[0] / refW;
      const yNorm = nd.pos_px[1] / refH;
      pos = normToPx(xNorm, yNorm);
    } else {
      console.warn('Cannot parse node position:', nd);
      continue;
    }

    // Parse node identity
    let k;
    if (nd.k != null) {
      k = typeof nd.k === 'number' ? nd.k : parseInt(nd.k);
    } else if (typeof nd.node_id === 'number') {
      k = nd.node_id;
    } else if (nd.step != null) {
      k = nd.step;
    } else {
      k = i + 1;
    }
    // Lure nodes get negative k to avoid collision with main sequence
    if (nd.role === 'lure' && nd.k == null) {
      k = -(i + 100);
    }

    // Build label based on task type
    let label = nd.label || '';
    let kind = nd.kind || nd.category || 'digit';
    let shape = nd.shape || 'circle';
    let role = nd.role || 'main';
    let value = nd.value ?? nd.num ?? k;
    let fruit = nd.fruit || null;
    let stimRel = nd.stim_rel || null;

    // For B3/B4/A1: fruit-based nodes — image has number baked in, label is just the number (for HUD/messages)
    if (fruit && !label) {
      label = String(nd.num || value);
    }

    // For B1: label is already set from JSON (e.g., "1", "一", "2", "二")
    if (!label) {
      label = String(value);
    }

    // Preserve original node_id for sequence matching (e.g. "n01", "B2_main_01")
    const nodeId = nd.node_id != null ? String(nd.node_id) : null;

    nodes.push({ k, label, kind, shape, role, value, fruit, stimRel, pos, radius: nodeRadius, nodeId });
  }

  // Determine sequence from layout
  let sequence;
  if (layoutData.sequence) {
    sequence = layoutData.sequence;
  } else if (layoutData.main_sequence) {
    sequence = layoutData.main_sequence.map((_, i) => i + 1);
  } else if (layoutData.path_node_ids) {
    sequence = layoutData.path_node_ids;
  } else {
    // Default: sort by k for main nodes
    const mainNodes = nodes.filter(n => n.role !== 'lure');
    mainNodes.sort((a, b) => a.k - b.k);
    sequence = mainNodes.map(n => n.k);
  }

  // Build ordered sequence of node references
  const orderedNodes = [];
  for (const seqItem of sequence) {
    let found;
    if (typeof seqItem === 'number') {
      found = nodes.find(n => n.k === seqItem && n.role !== 'lure');
    } else if (typeof seqItem === 'string') {
      // Match by original node_id first (A0: "n01", "n02", ...)
      found = nodes.find(n => n.nodeId === seqItem && n.role !== 'lure');
      if (!found) {
        // B1: sequence items are labels like "1", "一", "2", "二"
        found = nodes.find(n => n.label === seqItem);
      }
      if (!found) {
        // Try matching by k as string
        found = nodes.find(n => String(n.k) === seqItem);
      }
    } else if (typeof seqItem === 'object' && seqItem.value !== undefined) {
      found = nodes.find(n => n.value === seqItem.value && n.shape === seqItem.shape && n.role !== 'lure');
    }
    if (found) orderedNodes.push(found);
  }

  // Also include lure nodes (for B2 display)
  const lureNodes = nodes.filter(n => n.role === 'lure');

  return { orderedNodes, lureNodes, allNodes: nodes, nodeRadius: nodeRadius, renderDiam };
}

// ============================================================
// Drawing helpers
// ============================================================
function clearCanvas() {
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, canvasW * dpr, canvasH * dpr);
}

function drawNode(node, highlight, highlightColor) {
  const [cx, cy] = toCanvas(node.pos);
  const r = node.radius;
  const scaledR = r * dpr;
  const scaledCx = cx * dpr;
  const scaledCy = cy * dpr;

  // Draw highlight ring if needed
  if (highlight) {
    ctx.beginPath();
    if (node.shape === 'square') {
      const side = r * B2_SQUARE_SIZE_MULT * 1.2 * dpr;
      ctx.rect(scaledCx - side / 2, scaledCy - side / 2, side, side);
    } else {
      ctx.arc(scaledCx, scaledCy, scaledR * 1.15, 0, Math.PI * 2);
    }
    ctx.strokeStyle = highlightColor || FOCUS_RING_COLOR;
    ctx.lineWidth = 4 * dpr;
    ctx.stroke();
  }

  // Draw label or fruit image
  const isFruitNode = node.fruit != null;

  if (isFruitNode) {
    // 水果节点：不画白底圆圈，直接画图片（避免"白圈圈"问题）
    const imgKey = `${node.fruit}_${node.value ?? 1}`;
    const img = fruitImageCache[imgKey];
    if (img) {
      const imgSize = scaledR * 2;
      ctx.drawImage(img, scaledCx - imgSize / 2, scaledCy - imgSize / 2, imgSize, imgSize);
    } else {
      // Fallback: 图片未加载时画白底+文字
      ctx.beginPath();
      ctx.arc(scaledCx, scaledCy, scaledR, 0, Math.PI * 2);
      ctx.fillStyle = NODE_FILL;
      ctx.fill();
      ctx.strokeStyle = NODE_BORDER;
      ctx.lineWidth = NODE_BORDER_W * dpr;
      ctx.stroke();
      const baseFont = FONT_SIZE_BASE * (node.radius / (NODE_DIAMETER_PX_DEFAULT / 2));
      const fontSize = Math.round(baseFont * dpr);
      ctx.font = `bold ${fontSize}px "Microsoft YaHei", "PingFang SC", sans-serif`;
      ctx.fillStyle = TEXT_COLOR;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.label, scaledCx, scaledCy);
    }
  } else {
    // 非水果节点：画白底圆圈/方块 + 文字
    ctx.beginPath();
    if (node.shape === 'square') {
      const side = r * B2_SQUARE_SIZE_MULT * dpr;
      ctx.rect(scaledCx - side / 2, scaledCy - side / 2, side, side);
    } else {
      ctx.arc(scaledCx, scaledCy, scaledR, 0, Math.PI * 2);
    }
    ctx.fillStyle = NODE_FILL;
    ctx.fill();
    ctx.strokeStyle = NODE_BORDER;
    ctx.lineWidth = NODE_BORDER_W * dpr;
    ctx.stroke();
    // Non-fruit node: draw text label as before
    const baseFont = FONT_SIZE_BASE * (node.radius / (NODE_DIAMETER_PX_DEFAULT / 2));
    const fontSize = Math.round(baseFont * dpr);
    ctx.font = `bold ${fontSize}px "Microsoft YaHei", "PingFang SC", sans-serif`;
    ctx.fillStyle = TEXT_COLOR;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(node.label, scaledCx, scaledCy);
  }
}

function drawPath(points, color, width) {
  if (points.length < 2) return;
  ctx.beginPath();
  const p0 = toCanvas(points[0]);
  ctx.moveTo(p0[0] * dpr, p0[1] * dpr);
  for (let i = 1; i < points.length; i++) {
    const p = toCanvas(points[i]);
    ctx.lineTo(p[0] * dpr, p[1] * dpr);
  }
  ctx.strokeStyle = color || LINE_COLOR;
  ctx.lineWidth = (width || LINE_WIDTH) * dpr;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.stroke();
}

// ============================================================
// Instruction overlay (supports rich HTML content with diagrams)
// ============================================================
function showInstruction(title, body, hint) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'tmt-instruction-overlay';
    overlay.innerHTML = `
      <h2>${title}</h2>
      <p>${body}</p>
      ${hint ? `<p class="hint">${hint}</p>` : ''}
      <button class="btn-primary" style="margin-top: 20px; min-width: 260px; min-height: 88px;">继续</button>
    `;
    document.body.appendChild(overlay);

    const btn = overlay.querySelector('button');
    btn.disabled = true;
    setTimeout(() => { btn.disabled = false; }, CONFIG.instruction.minWaitMs);

    btn.addEventListener('pointerup', () => {
      overlay.remove();
      resolve();
    });
  });
}

/**
 * Rich instruction with inline SVG diagram.
 * @param {string} title - Large title text
 * @param {string} diagramHTML - SVG or HTML for the illustration area
 * @param {string} caption - Text below the diagram
 * @param {object} [opts] - Options: { buttonText, minWait }
 */
function showRichInstruction(title, diagramHTML, caption, opts = {}) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'tmt-instruction-overlay';
    const btnText = opts.buttonText || '继续';
    const minWait = opts.minWait || CONFIG.instruction.minWaitMs;
    overlay.innerHTML = `
      <h2 style="margin-bottom:10px;">${title}</h2>
      <div class="tmt-diagram-area">${diagramHTML}</div>
      ${caption ? `<p class="tmt-caption">${caption}</p>` : ''}
      <button class="btn-primary" style="margin-top:16px; min-width:260px; min-height:88px;">${btnText}</button>
    `;
    document.body.appendChild(overlay);

    const btn = overlay.querySelector('button');
    btn.disabled = true;
    setTimeout(() => { btn.disabled = false; }, minWait);

    btn.addEventListener('pointerup', () => {
      overlay.remove();
      resolve();
    });
  });
}

// ============================================================
// SVG diagram builders (matching original PsychoPy instruction images)
// ============================================================

/** Helper: draw a circle node in SVG */
function svgCircleNode(cx, cy, r, label, opts = {}) {
  const fill = opts.fill || '#fff';
  const stroke = opts.stroke || '#1565C0';
  const sw = opts.strokeWidth || 3;
  const textColor = opts.textColor || '#1A1A2E';
  const fontSize = opts.fontSize || Math.round(r * 0.9);
  const bold = opts.bold !== false ? 'font-weight:700;' : '';
  return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>
    <text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="central"
      style="font-size:${fontSize}px;fill:${textColor};${bold}font-family:'Microsoft YaHei','PingFang SC',sans-serif;">${label}</text>`;
}

/** Helper: draw a square node in SVG */
function svgSquareNode(cx, cy, size, label, opts = {}) {
  const fill = opts.fill || '#fff';
  const stroke = opts.stroke || '#2B5EA7';
  const sw = opts.strokeWidth || 3;
  const textColor = opts.textColor || '#fff';
  const fontSize = opts.fontSize || Math.round(size * 0.45);
  const r = opts.cornerRadius || 6;
  const bgFill = opts.bgFill || '#2B5EA7';
  return `<rect x="${cx - size/2}" y="${cy - size/2}" width="${size}" height="${size}" rx="${r}"
      fill="${bgFill}" stroke="${stroke}" stroke-width="${sw}"/>
    <text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="central"
      style="font-size:${fontSize}px;fill:${textColor};font-weight:700;font-family:'Microsoft YaHei','PingFang SC',sans-serif;">${label}</text>`;
}

/** Helper: arrow between two points */
function svgArrow(x1, y1, x2, y2, opts = {}) {
  const color = opts.color || '#1565C0';
  const sw = opts.strokeWidth || 3;
  const markerId = opts.markerId || `arw${Math.random().toString(36).slice(2,6)}`;
  const headSize = opts.headSize || 8;
  return `<defs><marker id="${markerId}" markerWidth="${headSize}" markerHeight="${headSize}" refX="${headSize-1}" refY="${headSize/2}" orient="auto">
      <polygon points="0 0, ${headSize} ${headSize/2}, 0 ${headSize}" fill="${color}"/></marker></defs>
    <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="${sw}" marker-end="url(#${markerId})"/>`;
}

/** Helper: curved arrow */
function svgCurvedArrow(x1, y1, cx, cy, x2, y2, opts = {}) {
  const color = opts.color || '#1565C0';
  const sw = opts.strokeWidth || 3;
  const markerId = `carw${Math.random().toString(36).slice(2,6)}`;
  const hs = opts.headSize || 8;
  return `<defs><marker id="${markerId}" markerWidth="${hs}" markerHeight="${hs}" refX="${hs-1}" refY="${hs/2}" orient="auto">
      <polygon points="0 0, ${hs} ${hs/2}, 0 ${hs}" fill="${color}"/></marker></defs>
    <path d="M${x1},${y1} Q${cx},${cy} ${x2},${y2}" fill="none" stroke="${color}" stroke-width="${sw}" marker-end="url(#${markerId})"/>`;
}

/** Helper: hand/finger indicator SVG at position (pure SVG, no emoji) */
function svgHandIcon(cx, cy, size) {
  const s = size || 28;
  // Simple arrow-curve indicating "start here"
  const r = s * 0.45;
  return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#F5A623" stroke-width="2.5" stroke-dasharray="4,3"/>
    <line x1="${cx + r + 4}" y1="${cy}" x2="${cx + r + s * 0.5}" y2="${cy}" stroke="#F5A623" stroke-width="2.5"/>
    <polygon points="${cx + r + s * 0.5 - 5},${cy - 4} ${cx + r + s * 0.5 + 2},${cy} ${cx + r + s * 0.5 - 5},${cy + 4}" fill="#F5A623"/>`;
}

/** Diagram: Operation method (matches 1.webp) — scaled for tablet */
function diagramOperationMethod() {
  const w = 680, h = 420;
  const r = 54;
  // Three nodes in a path: 1 (top-left), 2 (top-right), 3 (bottom-center)
  const n1 = [150, 120], n2 = [450, 120], n3 = [300, 310];
  let svg = `<svg viewBox="0 0 ${w} ${h}">`;
  // Curved arrows: 1->2, 2->3
  svg += svgCurvedArrow(n1[0]+r+6, n1[1]-14, 300, 28, n2[0]-r-6, n2[1]-14, {color:'#5BA0D9', strokeWidth: 4, headSize: 12});
  svg += svgCurvedArrow(n2[0]+6, n2[1]+r+6, 470, 240, n3[0]+r+6, n3[1]-14, {color:'#5BA0D9', strokeWidth: 4, headSize: 12});
  // Nodes
  svg += svgCircleNode(n1[0], n1[1], r, '1', {fill:'#E8E8E8', stroke:'#AAAAAA', textColor:'#333', strokeWidth: 4, fontSize: Math.round(r * 0.85)});
  svg += svgCircleNode(n2[0], n2[1], r, '2', {fill:'#E8E8E8', stroke:'#AAAAAA', textColor:'#333', strokeWidth: 4, fontSize: Math.round(r * 0.85)});
  svg += svgCircleNode(n3[0], n3[1], r, '3', {fill:'#E8E8E8', stroke:'#AAAAAA', textColor:'#333', strokeWidth: 4, fontSize: Math.round(r * 0.85)});
  // Start indicator near node 1
  svg += svgHandIcon(n1[0]+r+14, n1[1]+8, 36);
  svg += '</svg>';
  return svg;
}

/** Diagram: A0 number sequence (matches A0_1.webp) — scaled for tablet */
function diagramA0() {
  const w = 780, h = 360;
  const r = 46;
  // Two rows: 1,3,5 bottom; 2,4,6 top -- zigzag path
  const positions = [
    [90, 270],   // 1
    [210, 90],   // 2
    [330, 270],  // 3
    [450, 90],   // 4
    [570, 270],  // 5
    [690, 90],   // 6
  ];
  let svg = `<svg viewBox="0 0 ${w} ${h}">`;
  // Arrows between consecutive nodes
  for (let i = 0; i < positions.length - 1; i++) {
    const [x1, y1] = positions[i];
    const [x2, y2] = positions[i+1];
    const dx = x2 - x1, dy = y2 - y1;
    const len = Math.hypot(dx, dy);
    const offset = r + 8;
    svg += svgArrow(
      x1 + dx/len*offset, y1 + dy/len*offset,
      x2 - dx/len*offset, y2 - dy/len*offset,
      {color: '#1565C0', strokeWidth: 4, headSize: 11}
    );
  }
  // Nodes on top
  for (let i = 0; i < positions.length; i++) {
    svg += svgCircleNode(positions[i][0], positions[i][1], r, String(i+1), {stroke:'#1565C0', strokeWidth: 4, fontSize: Math.round(r * 0.85)});
  }
  svg += '</svg>';
  return svg;
}

/** Diagram: B1 digit-Chinese alternation (matches B1_1.webp) -- scaled for tablet */
function diagramB1() {
  const w = 780, h = 400;
  const r = 46;
  // Top row: 1, 2, 3 (arabic digits in circles)
  // Bottom row: one, two, three (Chinese in circles)
  const topY = 90, botY = 290;
  const xs = [135, 390, 645];
  let svg = `<svg viewBox="0 0 ${w} ${h}">`;
  // Arrows: 1->yi, yi->2, 2->er, er->3, 3->san
  const pairs = [
    [xs[0], topY, xs[0], botY],
    [xs[0], botY, xs[1], topY],
    [xs[1], topY, xs[1], botY],
    [xs[1], botY, xs[2], topY],
    [xs[2], topY, xs[2], botY],
  ];
  for (const [x1, y1, x2, y2] of pairs) {
    const dx = x2 - x1, dy = y2 - y1;
    const len = Math.hypot(dx, dy);
    const off = r + 8;
    svg += svgArrow(
      x1 + dx/len*off, y1 + dy/len*off,
      x2 - dx/len*off, y2 - dy/len*off,
      {color: '#1565C0', strokeWidth: 4, headSize: 11}
    );
  }
  const nOpts = {stroke:'#888', fill:'#fff', textColor:'#333', strokeWidth: 4, fontSize: Math.round(r * 0.85)};
  const cnOpts = {stroke:'#888', fill:'#fff', textColor:'#333', strokeWidth: 4, fontSize: Math.round(r * 0.75)};
  // Top row nodes (arabic)
  svg += svgCircleNode(xs[0], topY, r, '1', nOpts);
  svg += svgCircleNode(xs[1], topY, r, '2', nOpts);
  svg += svgCircleNode(xs[2], topY, r, '3', nOpts);
  // Bottom row nodes (chinese)
  svg += svgCircleNode(xs[0], botY, r, '\u4E00', cnOpts);
  svg += svgCircleNode(xs[1], botY, r, '\u4E8C', cnOpts);
  svg += svgCircleNode(xs[2], botY, r, '\u4E09', cnOpts);
  svg += '</svg>';
  return svg;
}

/** Diagram: B2 shape alternation (matches B2_1.webp) -- scaled for tablet */
function diagramB2() {
  const w = 780, h = 240;
  const r = 52;
  const sqSize = r * 1.5;
  const y = 120;
  const xs = [105, 300, 500, 695];
  let svg = `<svg viewBox="0 0 ${w} ${h}">`;
  // Arrows
  for (let i = 0; i < xs.length - 1; i++) {
    const gap = 64;
    svg += svgArrow(xs[i]+gap, y, xs[i+1]-gap, y, {color:'#2B5EA7', strokeWidth: 4, headSize: 11});
  }
  const sqOpts = {bgFill:'#2B5EA7', stroke:'#2B5EA7', strokeWidth: 4, fontSize: Math.round(sqSize * 0.45)};
  const crOpts = {fill:'#2B5EA7', stroke:'#2B5EA7', textColor:'#fff', strokeWidth: 4, fontSize: Math.round(r * 0.85)};
  // Alternating square, circle, square, circle
  svg += svgSquareNode(xs[0], y, sqSize, '1', sqOpts);
  svg += svgCircleNode(xs[1], y, r, '2', crOpts);
  svg += svgSquareNode(xs[2], y, sqSize, '3', sqOpts);
  svg += svgCircleNode(xs[3], y, r, '4', crOpts);
  svg += '</svg>';
  return svg;
}

/** Helper: SVG fruit icon (circle with leaf, no emoji) */
function svgFruitIcon(cx, cy, size, type) {
  // type: 'apple' (red) or 'lemon' (yellow)
  const r = size * 0.42;
  const color = type === 'apple' ? '#D32F2F' : '#F9A825';
  const leafColor = '#4CAF50';
  let s = `<circle cx="${cx}" cy="${cy + 2}" r="${r}" fill="${color}" stroke="${color}" stroke-width="1.5"/>`;
  // Leaf
  s += `<ellipse cx="${cx + r * 0.3}" cy="${cy - r + 1}" rx="${r * 0.35}" ry="${r * 0.2}" fill="${leafColor}" transform="rotate(-20,${cx + r * 0.3},${cy - r + 1})"/>`;
  // Stem
  s += `<line x1="${cx}" y1="${cy - r + 2}" x2="${cx}" y2="${cy - r - 3}" stroke="#5D4037" stroke-width="2" stroke-linecap="round"/>`;
  return s;
}

/** Diagram: A1 fruit numbers (matches A1_1.webp) -- scaled for tablet */
function diagramA1() {
  const w = 780, h = 220;
  const r = 48;
  const y = 110;
  const xs = [105, 300, 500, 695];
  const fruitTypes = ['apple', 'lemon', 'apple', 'lemon'];
  let svg = `<svg viewBox="0 0 ${w} ${h}">`;
  // Arrows
  for (let i = 0; i < xs.length - 1; i++) {
    svg += svgArrow(xs[i]+r+10, y, xs[i+1]-r-10, y, {color:'#1565C0', strokeWidth: 4, headSize: 11});
  }
  // Fruit icons with numbers
  for (let i = 0; i < xs.length; i++) {
    svg += svgFruitIcon(xs[i], y - 20, r, fruitTypes[i]);
    svg += `<text x="${xs[i]}" y="${y + 34}" text-anchor="middle"
      style="font-size:34px;font-weight:700;fill:#C0392B;font-family:'Microsoft YaHei','PingFang SC',sans-serif;">${i+1}</text>`;
  }
  svg += '</svg>';
  return svg;
}

/** Diagram: B3 fruit alternation (matches B3_1.webp) -- scaled for tablet */
function diagramB3() {
  const w = 700, h = 440;
  const xs = [120, 350, 580];
  const topY = 100, botY = 320;
  const fruitSz = 52;
  let svg = `<svg viewBox="0 0 ${w} ${h}">`;
  // Arrows: apple1 -> lemon1 -> apple2 -> lemon2 -> apple3 -> lemon3
  const points = [
    [xs[0], topY], [xs[0], botY],
    [xs[1], topY], [xs[1], botY],
    [xs[2], topY], [xs[2], botY],
  ];
  for (let i = 0; i < points.length - 1; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[i+1];
    const dx = x2 - x1, dy = y2 - y1;
    const len = Math.hypot(dx, dy);
    const off = 52;
    svg += svgArrow(
      x1 + dx/len*off, y1 + dy/len*off,
      x2 - dx/len*off, y2 - dy/len*off,
      {color:'#1565C0', strokeWidth: 4, headSize: 11}
    );
  }
  // Top row: apples
  for (let i = 0; i < 3; i++) {
    svg += svgFruitIcon(xs[i], topY - 10, fruitSz, 'apple');
    svg += `<text x="${xs[i]}" y="${topY + 36}" text-anchor="middle"
      style="font-size:28px;font-weight:700;fill:#C0392B;font-family:'Microsoft YaHei','PingFang SC',sans-serif;">${i+1}</text>`;
  }
  // Bottom row: lemons
  for (let i = 0; i < 3; i++) {
    svg += svgFruitIcon(xs[i], botY - 10, fruitSz, 'lemon');
    svg += `<text x="${xs[i]}" y="${botY + 36}" text-anchor="middle"
      style="font-size:28px;font-weight:700;fill:#D4A017;font-family:'Microsoft YaHei','PingFang SC',sans-serif;">${i+1}</text>`;
  }
  svg += '</svg>';
  return svg;
}

/** Diagram: B4 fruit number alternation (matches B4_1.webp) -- scaled for tablet */
function diagramB4() {
  const w = 640, h = 400;
  const fruitSz = 52;
  const positions = [
    [120, 80],   // apple 1
    [280, 280],  // lemon 1
    [440, 80],   // apple 2
    [580, 280],  // lemon 2
  ];
  const fruitTypes = ['apple', 'lemon', 'apple', 'lemon'];
  const nums = [1, 1, 2, 2];
  const numColors = ['#C0392B', '#D4A017', '#C0392B', '#D4A017'];
  let svg = `<svg viewBox="0 0 ${w} ${h}">`;
  // Arrows
  for (let i = 0; i < positions.length - 1; i++) {
    const [x1, y1] = positions[i];
    const [x2, y2] = positions[i+1];
    const dx = x2 - x1, dy = y2 - y1;
    const len = Math.hypot(dx, dy);
    const off = 50;
    svg += svgArrow(
      x1 + dx/len*off, y1 + dy/len*off,
      x2 - dx/len*off, y2 - dy/len*off,
      {color:'#1565C0', strokeWidth: 4, headSize: 11}
    );
  }
  // Fruit + number
  for (let i = 0; i < positions.length; i++) {
    const [x, y] = positions[i];
    svg += svgFruitIcon(x, y - 10, fruitSz, fruitTypes[i]);
    svg += `<text x="${x}" y="${y + 38}" text-anchor="middle"
      style="font-size:30px;font-weight:700;fill:${numColors[i]};font-family:'Microsoft YaHei','PingFang SC',sans-serif;">${nums[i]}</text>`;
  }
  svg += '</svg>';
  return svg;
}

// ============================================================
// Rest screen between tasks
// ============================================================
function showRest(taskName, index, total) {
  // 清除canvas残留
  if (ctx) {
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, canvasW * dpr, canvasH * dpr);
  }
  return showRichInstruction(
    '休息一下',
    '',
    `放松眼睛和手<br><span style="font-size:24px;color:#999;">已完成 ${index}/${total} 个任务</span>`,
    {}
  );
}

// ============================================================
// Practice task (1-2-3-4)
// ============================================================
async function runPractice() {
  // Welcome page (matches all_1.webp)
  await showRichInstruction(
    '欢迎参加连线测试',
    '',
    '这不是考试，没有对错<br>请放轻松，随时可以休息<br>如果不舒服请告诉工作人员',
    {}
  );

  // Voice-guided rules instruction (2026-04-23 晓烨重构 — 7 steps, 新增一笔连完 + 不要交叉)
  await VoiceGuide.show({
    image: 'img/rules.webp',
    btnRegion: { x: '79.8%', y: '5.3%', w: '15.5%', h: '8.1%' },
    buttonText: '开始练习',
    pauseBetween: 500,
    steps: [
      { region: { x: '5.1%', y: '14.2%', w: '47.8%', h: '38.6%' }, lines: [
        { audio: `${AUDIO_BASE}/rules_s01.mp3`, subtitle: '屏幕上有着一些带数字的圆点，请先找到数字1' },
      ] },
      { region: { x: '5.4%', y: '54.9%', w: '47.5%', h: '39.1%' }, lines: [
        { audio: `${AUDIO_BASE}/rules_s02.mp3`, subtitle: '手指按住数字1，从1开始，依次连到2、3、4……' },
      ] },
      { region: { x: '54.1%', y: '14.3%', w: '40.7%', h: '79.2%' }, lines: [
        { audio: `${AUDIO_BASE}/rules_s03.mp3`, subtitle: '按顺序连就可以' },
      ] },
      { region: { x: '56%', y: '28.4%', w: '20.1%', h: '29%' }, lines: [
        { audio: `${AUDIO_BASE}/rules_one_stroke.mp3?v=20260423`, subtitle: '请尽可能一笔连完，尽量不要松开' },
      ] },
      { region: { x: '73.4%', y: '28.1%', w: '19%', h: '29.4%' }, lines: [
        { audio: `${AUDIO_BASE}/rules_s04.mp3?v=20260423`, subtitle: '如果中途松开也没关系，从上一个点接着连' },
      ] },
      { region: { x: '54.2%', y: '58.5%', w: '41%', h: '34.9%' }, lines: [
        { audio: `${AUDIO_BASE}/rules_no_cross.mp3?v=20260423`, subtitle: '尽量不要让线条交叉' },
        { audio: `${AUDIO_BASE}/rules_s05.mp3?v=20260423`,       subtitle: '如果线条交叉也没关系，按照规则继续连' },
      ] },
      { region: { x: '79.3%', y: '4.2%', w: '16.8%', h: '9.4%' }, lines: [
        { audio: `${AUDIO_BASE}/rules_s06.mp3`, subtitle: '明白了就点击开始练习' },
        { audio: `${AUDIO_BASE}/rules_s07.mp3`, subtitle: '有不清楚的可以问工作人员' },
      ] },
    ],
  });

  // Practice node positions (fixed layout) -- radius scaled for tablet touch
  const practiceR = 72;
  const positions = [
    [0, canvasH * 0.2],
    [-canvasW * 0.25, -canvasH * 0.05],
    [canvasW * 0.25, -canvasH * 0.05],
    [0, -canvasH * 0.25],
  ];

  const nodes = positions.map((pos, i) => ({
    k: i + 1,
    label: String(i + 1),
    kind: 'digit',
    shape: 'circle',
    role: 'main',
    value: i + 1,
    pos: pos,
    radius: practiceR,
  }));

  const result = await runTMTTask({
    taskType: 'PRACTICE',
    orderedNodes: nodes,
    lureNodes: [],
    allNodes: nodes,
    nodeRadius: practiceR,
    hardLimit: 60, // generous time for practice
    layoutId: 0,
  });

  return result;
}

// ============================================================
// Core TMT task runner (used for practice + all sub-tasks)
// ============================================================
function runTMTTask(params) {
  const { taskType, orderedNodes, lureNodes, allNodes, nodeRadius, hardLimit, layoutId: lid } = params;
  const totalNodes = orderedNodes.length;

  return new Promise(resolve => {
    // State
    let currentTarget = 0; // index into orderedNodes (start at first node)
    let penDown = false;
    let taskStartMs = null;
    let segmentStartMs = null;
    let needReturn = false;
    let finished = false;

    // Paths
    const committedPaths = []; // Array of {points: [[x,y],...], color}
    let currentPathDraw = [];
    let currentPathLen = 0;

    // 3-finger double-tap skip (无障碍跳过手势)
    const activePointers = new Set();
    // 2026-04-19: 单指锁定,防止老人左手扶屏产生第二个 pointer stream 污染画线
    // 第一根触屏的手指 = primary,后续 pointer 忽略(仍计入 activePointers 供 3-finger 跳过检测)
    let primaryPointerId = null;
    let lastThreeFingerTapMs = -1;
    const THREE_FINGER_SKIP_MS = 700; // 两次3指触碰间隔 ≤700ms 触发跳过

    // Error tracking
    let totalErrors = 0;
    let orderErrors = 0;
    let timeoutErrors = 0;
    let invalidStartCount = 0;

    // Dwell tracking (anti-swipe-through)
    let candNode = null;
    let candSince = null;

    // Timing
    let lastProgressMs = 0;
    let lastSampleMs = 0;
    let hintActiveUntilMs = 0;
    let errorFlashUntilMs = 0;
    let errorFlashNode = null;
    let successFlashUntilMs = 0;
    let successFlashNode = null;

    // Data collection
    const segmentRows = [];
    const rawRows = [];
    const eventMarkers = [];
    let segIndex = 0;

    const hud = document.getElementById('tmt-hud');
    const msg = document.getElementById('tmt-message');
    const skipBtn = document.getElementById('tmt-skip-btn');
    // 每个 block 开始时保证按钮隐藏 (上一个 block 显过的残留不带到下一个)
    if (skipBtn) skipBtn.style.display = 'none';
    // 跳过按钮点击处理 (仅 skipBtn 显现后才可能被点到)
    let skipBtnClickHandler = null;
    if (skipBtn) {
      skipBtnClickHandler = function (e) {
        e.preventDefault();
        e.stopPropagation();
        addMarker('SKIP', 'operator-button', -1, -1);
        finished = true;
        skipBtn.style.display = 'none';
        cleanup();
        resolve(buildResult());
      };
      skipBtn.addEventListener('click', skipBtnClickHandler);
    }

    function getElapsedS() {
      if (taskStartMs === null) return 0;
      return (nowMs() - taskStartMs) / 1000;
    }

    function addMarker(eventName, note, kFrom, kTo) {
      eventMarkers.push({
        ts_ms: taskStartMs !== null ? Math.round(nowMs() - taskStartMs) : 0,
        event: eventName,
        from_k: kFrom ?? -1,
        to_k: kTo ?? -1,
        note: note || '',
      });
    }

    function resetCandidate() {
      candNode = null;
      candSince = null;
    }

    function addDrawPoint(pt) {
      if (currentPathDraw.length === 0) {
        currentPathDraw.push(pt);
        return;
      }
      if (dist(pt, currentPathDraw[currentPathDraw.length - 1]) >= DRAW_MIN_MOVE_PX) {
        currentPathDraw.push(pt);
      }
    }

    function commitSegment() {
      if (currentPathDraw.length >= 2) {
        committedPaths.push({ points: [...currentPathDraw], color: LINE_COLOR });
      }
    }

    function nearestNodeWithin(pos, radius) {
      let best = null;
      let bestD = Infinity;
      for (const n of allNodes) {
        const d = dist(pos, n.pos);
        if (d <= radius && d < bestD) {
          best = n;
          bestD = d;
        }
      }
      return { node: best, dist: bestD };
    }

    const hitRadius = nodeRadius * HIT_RADIUS_MULT;
    const coreRadius = nodeRadius * CORE_HIT_MULT;
    const wrongCoreRadius = nodeRadius * WRONG_CORE_MULT;
    const startTol = nodeRadius * START_TOL_MULT;

    // ---- Drawing ----
    function render() {
      clearCanvas();
      const tMs = taskStartMs !== null ? Math.round(nowMs() - taskStartMs) : 0;

      // Draw committed paths (under nodes)
      for (const p of committedPaths) {
        drawPath(p.points, p.color, LINE_WIDTH);
      }

      // Draw current live path
      if (penDown && currentPathDraw.length >= 2) {
        drawPath(currentPathDraw, LINE_COLOR, LINE_WIDTH);
      }

      // Draw all nodes (on top of lines, white fill hides line passing through)
      for (const n of allNodes) {
        drawNode(n, false, null);
      }

      // Overlay rings drawn AFTER nodes

      // Error flash ring
      if (errorFlashNode && tMs < errorFlashUntilMs) {
        const [cx, cy] = toCanvas(errorFlashNode.pos);
        ctx.beginPath();
        ctx.arc(cx * dpr, cy * dpr, nodeRadius * 1.12 * dpr, 0, Math.PI * 2);
        ctx.strokeStyle = ERROR_RING_COLOR;
        ctx.lineWidth = 5 * dpr;
        ctx.stroke();
      }

      // Success flash ring (green, 200ms)
      if (successFlashNode && tMs < successFlashUntilMs) {
        const [cx, cy] = toCanvas(successFlashNode.pos);
        ctx.beginPath();
        ctx.arc(cx * dpr, cy * dpr, nodeRadius * 1.12 * dpr, 0, Math.PI * 2);
        ctx.strokeStyle = '#4CAF50';
        ctx.lineWidth = 5 * dpr;
        ctx.stroke();
      }

      // Hint ring (stall timeout highlight)
      if (tMs < hintActiveUntilMs && currentTarget < totalNodes) {
        const targetNode = orderedNodes[currentTarget];
        const [cx, cy] = toCanvas(targetNode.pos);
        ctx.beginPath();
        ctx.arc(cx * dpr, cy * dpr, nodeRadius * 1.1 * dpr, 0, Math.PI * 2);
        ctx.strokeStyle = HINT_RING_COLOR;
        ctx.lineWidth = 5 * dpr;
        ctx.stroke();
      }

      // Need return: highlight the "from" node to return to
      if (needReturn && currentTarget > 0) {
        const returnNode = orderedNodes[currentTarget - 1];
        const [cx, cy] = toCanvas(returnNode.pos);
        ctx.beginPath();
        ctx.arc(cx * dpr, cy * dpr, nodeRadius * 1.2 * dpr, 0, Math.PI * 2);
        ctx.strokeStyle = RETURN_RING_COLOR;
        ctx.lineWidth = 5 * dpr;
        ctx.stroke();
      }

      // Focus ring on first node before start
      if (taskStartMs === null) {
        const firstNode = orderedNodes[0];
        const [cx, cy] = toCanvas(firstNode.pos);
        ctx.beginPath();
        ctx.arc(cx * dpr, cy * dpr, nodeRadius * 1.2 * dpr, 0, Math.PI * 2);
        ctx.strokeStyle = FOCUS_RING_COLOR;
        ctx.lineWidth = 5 * dpr;
        ctx.stroke();
      }

      // HUD
      if (taskStartMs !== null) {
        const completed = Math.min(currentTarget, totalNodes);
        hud.textContent = `进度: ${completed}/${totalNodes}`;
      } else {
        hud.textContent = taskType;
      }

      // Message
      if (taskStartMs === null) {
        msg.textContent = `请触碰 ${orderedNodes[0].label} 开始`;
      } else if (needReturn && currentTarget > 0) {
        msg.textContent = `连错了，请回到 ${orderedNodes[currentTarget - 1].label} 后继续`;
      } else if (finished) {
        msg.textContent = '完成！请点击屏幕继续';
      } else {
        msg.textContent = '';
      }
    }

    // ---- Pointer event handlers ----
    function getPointerPos(e) {
      const rect = canvas.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      return fromCanvas(cx, cy);
    }

    function onPointerDown(e) {
      e.preventDefault();
      const pos = getPointerPos(e);
      const now = nowMs();

      // 3-finger double-tap: 主试跳过当前任务 (必须在 primary 锁定之前检查,
      // 否则第 2/3 根手指被忽略会导致 activePointers.size < 3)
      activePointers.add(e.pointerId);
      if (activePointers.size >= 3) {
        if (lastThreeFingerTapMs > 0 && now - lastThreeFingerTapMs <= THREE_FINGER_SKIP_MS) {
          addMarker('SKIP', '3-finger-double-tap', -1, -1);
          finished = true;
          cleanup();
          resolve(buildResult());
          return;
        }
        lastThreeFingerTapMs = now;
      }

      // 单指锁定: 只接受第一根手指的 pointer stream,其他手指(如左手扶屏)忽略
      // 已有 primary 且 pointerId 不同 → 忽略此 pointerdown
      if (primaryPointerId !== null && e.pointerId !== primaryPointerId) {
        return;
      }
      // 首次 pointerdown → 记为 primary,后续 move/up 只认它
      if (primaryPointerId === null) {
        primaryPointerId = e.pointerId;
        try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* best-effort */ }
      }

      if (finished) {
        // Click to continue after finishing
        cleanup();
        resolve(buildResult());
        return;
      }

      // Before task starts: must touch first node
      if (taskStartMs === null) {
        if (dist(pos, orderedNodes[0].pos) <= startTol) {
          taskStartMs = now;
          lastProgressMs = 0;
          lastSampleMs = 0;
          addMarker('BLOCK_START', 'start timing', orderedNodes[0].k, orderedNodes[0].k);
          if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
            window.ParadigmCamera.addEvent('task_start', { task_type: taskType });
          }
          penDown = true;
          segmentStartMs = 0;
          currentPathDraw = [];
          addDrawPoint(pos);
          currentPathLen = 0;
          resetCandidate();
          // Advance: currentTarget is 0 (first node), next target is 1
          currentTarget = 1;
        }
        return;
      }

      const tMs = Math.round(now - taskStartMs);

      // Need return: must touch previous correct node first
      if (needReturn && currentTarget > 0) {
        const returnNode = orderedNodes[currentTarget - 1];
        if (dist(pos, returnNode.pos) <= startTol) {
          needReturn = false;
          penDown = true;
          segmentStartMs = tMs;
          currentPathDraw = [];
          addDrawPoint(pos);
          currentPathLen = 0;
          resetCandidate();
        }
        return;
      }

      // Normal pen down: must be near current "from" node
      if (!penDown) {
        const fromNode = orderedNodes[currentTarget - 1];
        if (dist(pos, fromNode.pos) > startTol) {
          invalidStartCount++;
          segIndex++;
          segmentRows.push({
            segment_index: segIndex,
            task_type: taskType,
            layout_id: lid,
            kind: 'ERROR',
            from_k: fromNode.k,
            to_k: fromNode.k,
            start_ts_ms: tMs,
            end_ts_ms: tMs,
            duration_ms: 0,
            path_length_px: 0,
            is_error: 1,
            error_type: 'invalid_start',
            note: 'pen down not near current node',
          });
          return;
        }
        penDown = true;
        segmentStartMs = tMs;
        currentPathDraw = [];
        addDrawPoint(pos);
        currentPathLen = 0;
        resetCandidate();
      }
    }

    function onPointerMove(e) {
      e.preventDefault();
      // 非 primary 手指的 move 忽略 (左手扶屏的 pointer stream 不画线)
      if (primaryPointerId !== null && e.pointerId !== primaryPointerId) return;
      if (!penDown || taskStartMs === null || finished) return;

      const pos = getPointerPos(e);
      const now = nowMs();
      const tMs = Math.round(now - taskStartMs);

      // Raw sampling
      if (tMs - lastSampleMs >= RAW_SAMPLE_INTERVAL) {
        rawRows.push({
          ts_ms: tMs,
          x_px: Math.round(pos[0] * 10) / 10,
          y_px: Math.round(pos[1] * 10) / 10,
          is_pen_down: 1,
        });
        lastSampleMs = tMs;
      }

      // Update path
      if (currentPathDraw.length > 0) {
        const lastPt = currentPathDraw[currentPathDraw.length - 1];
        if (dist(pos, lastPt) >= 0.1) {
          currentPathLen += dist(pos, lastPt);
          addDrawPoint(pos);
        }
      }

      // Check collision with target
      if (currentTarget < totalNodes) {
        const targetNode = orderedNodes[currentTarget];
        const { node: picked, dist: pickedD } = nearestNodeWithin(pos, hitRadius);
        const fromNode = orderedNodes[currentTarget - 1];

        if (!picked || picked === fromNode) {
          resetCandidate();
        } else {
          // Candidate changed?
          if (!candNode || picked !== candNode) {
            candNode = picked;
            candSince = now;
          }

          const dwell = (now - (candSince || now)) / 1000;

          // Correct next node
          if (picked === targetNode) {
            if (pickedD <= coreRadius || dwell >= RIGHT_DWELL_S) {
              // HIT correct!
              const segEndMs = tMs;
              const segDur = segEndMs - (segmentStartMs || 0);

              segIndex++;
              segmentRows.push({
                segment_index: segIndex,
                task_type: taskType,
                layout_id: lid,
                kind: 'SEGMENT',
                from_k: fromNode.k,
                to_k: targetNode.k,
                start_ts_ms: segmentStartMs || 0,
                end_ts_ms: segEndMs,
                duration_ms: segDur,
                path_length_px: Math.round(currentPathLen * 10) / 10,
                is_error: 0,
                error_type: 'none',
                note: 'continuous confirm correct',
              });

              commitSegment();
              successFlashNode = targetNode;
              successFlashUntilMs = tMs + 200; // 200ms 绿色闪烁
              currentTarget++;
              lastProgressMs = tMs;
              resetCandidate();
              if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
                window.ParadigmCamera.addEvent('node_hit', { task_type: taskType, node_label: targetNode.label, node_index: currentTarget - 1 });
              }

              if (currentTarget >= totalNodes) {
                finished = true;
                addMarker('BLOCK_END', 'completed', targetNode.k, targetNode.k);
                if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
                  window.ParadigmCamera.addEvent('task_end', { task_type: taskType, time_s: Math.round(tMs / 10) / 100, errors: totalErrors });
                }
              }

              // Continue drawing: new segment
              segmentStartMs = tMs;
              currentPathDraw = [];
              addDrawPoint(pos);
              currentPathLen = 0;
            }
          } else if (picked.role !== 'lure' || taskType === 'B2') {
            // Wrong node: 进入核心区即判错，无需停留
            // 文献依据: JMIR 2023 PMC10337362 "error occurs when user enters incorrect target";
            // 纸笔版 TMT (Reitan 1958) 亦为进入即错。WRONG_DWELL_S 仅作数据记录，不参与错误判定。
            if (pickedD <= wrongCoreRadius) {
              totalErrors++;
              orderErrors++;

              const segEndMs = tMs;
              segIndex++;
              segmentRows.push({
                segment_index: segIndex,
                task_type: taskType,
                layout_id: lid,
                kind: 'ERROR',
                from_k: fromNode.k,
                to_k: picked.k,
                start_ts_ms: segmentStartMs || 0,
                end_ts_ms: segEndMs,
                duration_ms: segEndMs - (segmentStartMs || 0),
                path_length_px: Math.round(currentPathLen * 10) / 10,
                is_error: 1,
                error_type: 'order',
                note: 'long dwell on wrong node',
              });

              commitSegment();
              committedPaths.pop(); // 移除错误线条，不保留在画面上
              needReturn = true;
              lastProgressMs = tMs;
              if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
                window.ParadigmCamera.addEvent('error', { task_type: taskType, target: targetNode.label, hit: picked.label });
              }

              errorFlashNode = picked;
              errorFlashUntilMs = tMs + ERROR_FLASH_MS;

              // Force pen up
              penDown = false;
              segmentStartMs = null;
              currentPathDraw = [];
              currentPathLen = 0;
              resetCandidate();
            }
          }
        }
      }
    }

    function onPointerUp(e) {
      e.preventDefault();
      activePointers.delete(e.pointerId);
      // 非 primary 手指抬起: 只维护 activePointers,不影响画线状态
      if (primaryPointerId !== null && e.pointerId !== primaryPointerId) return;
      // primary 手指抬起: 清空 primary 供下一笔接管
      if (e.pointerId === primaryPointerId) {
        primaryPointerId = null;
        try { canvas.releasePointerCapture(e.pointerId); } catch (_) { /* best-effort */ }
      }
      if (!penDown || taskStartMs === null) return;

      const pos = getPointerPos(e);
      const now = nowMs();
      const tMs = Math.round(now - taskStartMs);

      // Check if released on correct target
      if (currentTarget < totalNodes && segmentStartMs !== null) {
        const targetNode = orderedNodes[currentTarget];
        const fromNode = orderedNodes[currentTarget - 1];
        const { node: picked, dist: pickedD } = nearestNodeWithin(pos, hitRadius);

        if (picked === targetNode) {
          // Released on correct next node
          const segEndMs = tMs;
          segIndex++;
          segmentRows.push({
            segment_index: segIndex,
            task_type: taskType,
            layout_id: lid,
            kind: 'SEGMENT',
            from_k: fromNode.k,
            to_k: targetNode.k,
            start_ts_ms: segmentStartMs,
            end_ts_ms: segEndMs,
            duration_ms: segEndMs - segmentStartMs,
            path_length_px: Math.round(currentPathLen * 10) / 10,
            is_error: 0,
            error_type: 'none',
            note: 'release inside correct next',
          });

          commitSegment();
          currentTarget++;
          lastProgressMs = tMs;
          if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
            window.ParadigmCamera.addEvent('node_hit', { task_type: taskType, node_label: targetNode.label, node_index: currentTarget - 1 });
          }

          if (currentTarget >= totalNodes) {
            finished = true;
            addMarker('BLOCK_END', 'completed', targetNode.k, targetNode.k);
            if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
              window.ParadigmCamera.addEvent('task_end', { task_type: taskType, time_s: Math.round(tMs / 10) / 100, errors: totalErrors });
            }
          }
        } else if (picked && picked !== fromNode && picked.role !== 'lure') {
          // Released on wrong node
          totalErrors++;
          orderErrors++;

          segIndex++;
          segmentRows.push({
            segment_index: segIndex,
            task_type: taskType,
            layout_id: lid,
            kind: 'ERROR',
            from_k: fromNode.k,
            to_k: picked.k,
            start_ts_ms: segmentStartMs,
            end_ts_ms: tMs,
            duration_ms: tMs - segmentStartMs,
            path_length_px: Math.round(currentPathLen * 10) / 10,
            is_error: 1,
            error_type: 'order',
            note: 'release inside wrong node',
          });

          commitSegment();
          committedPaths.pop(); // 移除错误线条，不保留在画面上（数据已在segmentRows中）
          needReturn = true;
          lastProgressMs = tMs;
          errorFlashNode = picked;
          errorFlashUntilMs = tMs + ERROR_FLASH_MS;
          if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
            window.ParadigmCamera.addEvent('error', { task_type: taskType, target: targetNode.label, hit: picked.label });
          }
        }
      }

      penDown = false;
      resetCandidate();
      segmentStartMs = null;
      currentPathDraw = [];
      currentPathLen = 0;
    }

    // ---- Main loop ----
    let animFrameId;
    let loopStopped = false;

    function loop() {
      if (loopStopped) return;

      if (taskStartMs !== null && !finished) {
        const tMs = Math.round(nowMs() - taskStartMs);
        const elapsedS = tMs / 1000;

        // Hard time limit
        if (elapsedS >= hardLimit) {
          finished = true;
          addMarker('TIMEOUT', 'hard limit reached', -1, -1);
          if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
            window.ParadigmCamera.addEvent('task_end', { task_type: taskType, time_s: Math.round(elapsedS * 100) / 100, errors: totalErrors });
          }
        }

        // Stall hint: highlight next target after 10s of no progress
        if (currentTarget < totalNodes && (tMs - lastProgressMs) >= STALL_HINT_S * 1000) {
          timeoutErrors++;
          hintActiveUntilMs = tMs + HINT_FLASH_MS;
          addMarker('TIMEOUT_PROMPT', 'stall>=10s',
            currentTarget > 0 ? orderedNodes[currentTarget - 1]?.k : -1,
            currentTarget < totalNodes ? orderedNodes[currentTarget]?.k : -1
          );
          lastProgressMs = tMs;

          // 首次 10s stall 就显现施测员跳过按钮 (右上角,避开节点布局 y<0.09 区)
          if (timeoutErrors >= 1 && skipBtn && skipBtn.style.display !== 'block') {
            skipBtn.style.display = 'block';
            addMarker('SKIP_BTN_SHOWN', 'stall>=10s', -1, -1);
          }

          segIndex++;
          segmentRows.push({
            segment_index: segIndex,
            task_type: taskType,
            layout_id: lid,
            kind: 'MARKER',
            from_k: currentTarget > 0 ? (orderedNodes[currentTarget - 1]?.k ?? -1) : -1,
            to_k: currentTarget < totalNodes ? (orderedNodes[currentTarget]?.k ?? -1) : -1,
            start_ts_ms: tMs,
            end_ts_ms: tMs,
            duration_ms: 0,
            path_length_px: 0,
            is_error: 0,
            error_type: 'timeout_hint',
            note: 'stall>=10s',
          });
        }
      }

      render();
      animFrameId = requestAnimationFrame(loop);
    }

    function buildResult() {
      const completionTime = taskStartMs !== null
        ? Math.min((nowMs() - taskStartMs) / 1000, hardLimit)
        : 0;

      return {
        taskType,
        layoutId: lid,
        finished: currentTarget >= totalNodes,
        completionTimeS: Math.round(completionTime * 1000) / 1000,
        totalErrors,
        orderErrors,
        timeoutErrors,
        invalidStartCount,
        nodesTotal: totalNodes,
        nodesCompleted: Math.min(currentTarget, totalNodes),
        segments: segmentRows,
        rawPath: rawRows,
        eventMarkers,
      };
    }

    function cleanup() {
      loopStopped = true;
      cancelAnimationFrame(animFrameId);
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup', onPointerUp);
      canvas.removeEventListener('pointercancel', onPointerUp);
      canvas.removeEventListener('pointerleave', onPointerUp);
      hud.textContent = '';
      msg.textContent = '';
      if (skipBtn && skipBtnClickHandler) {
        skipBtn.removeEventListener('click', skipBtnClickHandler);
        skipBtn.style.display = 'none';
      }
    }

    // ---- Start ----
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerUp);
    canvas.addEventListener('pointerleave', onPointerUp);
    loop();
  });
}

// ============================================================
// Data export
// ============================================================
function generateCSV(headers, rows) {
  const bom = '\uFEFF';
  const headerLine = headers.join(',');
  const dataLines = rows.map(row => headers.map(h => {
    const val = row[h] ?? '';
    const s = String(val);
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"` : s;
  }).join(','));
  return bom + [headerLine, ...dataLines].join('\n');
}

async function saveTaskData(result, sid) {
  const ts = formatTimestamp();
  const base = `TMT_${result.taskType}_${sid}_${ts}`;

  // Segments CSV
  if (result.segments.length > 0) {
    const segHeaders = [
      'subject_id', 'task_type', 'layout_id', 'segment_index', 'kind',
      'from_k', 'to_k', 'start_ts_ms', 'end_ts_ms', 'duration_ms',
      'path_length_px', 'is_error', 'error_type', 'note',
    ];
    const segRows = result.segments.map(s => ({ subject_id: sid, ...s }));
    const segCSV = generateCSV(segHeaders, segRows);
    const segName = `${base}_segments.csv`;
    await saveCSV('tmt', sid, segName, segCSV);
    if (typeof window.LocalPack !== 'undefined') window.LocalPack.add(segName, segCSV);
  }

  // Raw trajectory CSV (only save for formal tasks, not practice)
  if (result.rawPath.length > 0 && result.taskType !== 'PRACTICE') {
    const rawHeaders = ['subject_id', 'task_type', 'layout_id', 'ts_ms', 'x_px', 'y_px', 'is_pen_down'];
    const rawCSVRows = result.rawPath.map(r => ({
      subject_id: sid,
      task_type: result.taskType,
      layout_id: result.layoutId,
      ...r,
    }));
    const rawCSV = generateCSV(rawHeaders, rawCSVRows);
    const rawName = `${base}_raw_path.csv`;
    await saveCSV('tmt', sid, rawName, rawCSV);
    if (typeof window.LocalPack !== 'undefined') window.LocalPack.add(rawName, rawCSV);
  }

  // Summary CSV
  const summaryHeaders = [
    'subject_id', 'task_type', 'layout_id', 'finished',
    'completion_time_s', 'total_errors', 'order_errors',
    'timeout_errors', 'invalid_start_count', 'nodes_total',
    'nodes_completed', 'hard_limit_s', 'timestamp',
  ];
  const summaryRow = {
    subject_id: sid,
    task_type: result.taskType,
    layout_id: result.layoutId,
    finished: result.finished ? 1 : 0,
    completion_time_s: result.completionTimeS,
    total_errors: result.totalErrors,
    order_errors: result.orderErrors,
    timeout_errors: result.timeoutErrors,
    invalid_start_count: result.invalidStartCount,
    nodes_total: result.nodesTotal,
    nodes_completed: result.nodesCompleted,
    hard_limit_s: HARD_LIMIT_S,
    timestamp: ts,
  };
  const summaryCSV = generateCSV(summaryHeaders, [summaryRow]);
  const summaryName = `${base}_summary.csv`;
  await saveCSV('tmt', sid, summaryName, summaryCSV);
  if (typeof window.LocalPack !== 'undefined') window.LocalPack.add(summaryName, summaryCSV);

  // Event markers CSV
  if (result.eventMarkers.length > 0) {
    const markerHeaders = ['subject_id', 'task_type', 'layout_id', 'ts_ms', 'event', 'from_k', 'to_k', 'note'];
    const markerRows = result.eventMarkers.map(m => ({
      subject_id: sid,
      task_type: result.taskType,
      layout_id: result.layoutId,
      ...m,
    }));
    const markerCSV = generateCSV(markerHeaders, markerRows);
    const markerName = `${base}_event_marker.csv`;
    await saveCSV('tmt', sid, markerName, markerCSV);
    if (typeof window.LocalPack !== 'undefined') window.LocalPack.add(markerName, markerCSV);
  }
}

// ============================================================
// Sub-task instruction (rich visual, matching PsychoPy originals)
// ============================================================
async function showTaskInstruction(taskType) {
  // 清除canvas残留（上一个任务的最后一帧），避免"闪前一张图"
  if (ctx) {
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, canvasW * dpr, canvasH * dpr);
  }
  switch (taskType) {
    case 'A0':
      // 2026-04-14 ini 精简版:3 条主步骤,删掉反馈机制讲解(交由现场演示)
      await VoiceGuide.show({
        image: 'img/block1.webp',
        btnRegion: { x: '80.1%', y: '5.1%', w: '14.6%', h: '7.8%' },
        buttonText: '开始',
        pauseBetween: 500,
        steps: [
          { region: { x: '5.6%', y: '14%', w: '47.4%', h: '38.1%' }, lines: [
            { audio: `${AUDIO_BASE}/a0_s01.mp3`, subtitle: '先找到数字 1' },
          ] },
          { region: { x: '5.6%', y: '55%', w: '47.3%', h: '39.5%' }, lines: [
            { audio: `${AUDIO_BASE}/a0_s02.mp3`, subtitle: '从 1 开始，按顺序一直连到最后一个数字' },
          ] },
          { region: { x: '54.7%', y: '13.8%', w: '40.2%', h: '79.6%' }, lines: [
            { audio: `${AUDIO_BASE}/a0_s03.mp3`, subtitle: '中途松开了也没关系，接着连就可以' },
          ] },
          { region: { x: '79.3%', y: '4%', w: '16.5%', h: '9.9%' }, lines: [
            { audio: `${AUDIO_BASE}/a0_s04.mp3`, subtitle: '准备好了就点击开始' },
          ] },
        ],
      });
      break;
    case 'B2':
      // 2026-04-14 ini 精简版:合并"方形/圆形"定义到一句
      await VoiceGuide.show({
        image: 'img/block2.webp',
        btnRegion: { x: '80.3%', y: '5%', w: '14.6%', h: '7.8%' },
        buttonText: '开始',
        pauseBetween: 500,
        steps: [
          { region: { x: '5.1%', y: '14.6%', w: '32.2%', h: '54.4%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s01.mp3`, subtitle: '这次除了看数字，还要看图形。方的是方形，圆的是圆形' },
          ] },
          { region: { x: '11.2%', y: '45.2%', w: '5.4%', h: '7.8%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s02.mp3`, subtitle: '先找到方形里的数字 1' },
          ] },
          { region: { x: '40%', y: '17.1%', w: '55%', h: '44%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s03.mp3`, subtitle: '然后按数字顺序，方形和圆形轮流连' },
          ] },
          { region: { x: '41.7%', y: '32.7%', w: '48.8%', h: '44.1%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s04.mp3`, subtitle: '也就是：方形 1，圆形 2，方形 3，圆形 4，一直这样轮流连下去' },
          ] },
          { region: { x: '79.4%', y: '4.1%', w: '16.3%', h: '9.8%' }, lines: [
            { audio: `${AUDIO_BASE}/b2_s05.mp3`, subtitle: '明白了就点击开始' },
          ] },
        ],
      });
      break;
    case 'B1':
      // 2026-04-14 ini 精简版:用示例("1、2、3"/"一、二、三")替代术语"阿拉伯数字"
      await VoiceGuide.show({
        image: 'img/block3.webp',
        btnRegion: { x: '80.3%', y: '5%', w: '14.6%', h: '7.8%' },
        buttonText: '开始',
        pauseBetween: 500,
        steps: [
          { region: { x: '5.4%', y: '14.1%', w: '32.2%', h: '79.3%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s01.mp3`, subtitle: '这次除了看数字，还要分清两种写法。屏幕上有数字，也有汉字' },
          ] },
          { region: { x: '9%', y: '36.4%', w: '25.2%', h: '19.4%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s02.mp3`, subtitle: '像 1、2、3 这样的是数字，像一、二、三这样的是汉字' },
          ] },
          { region: { x: '10.6%', y: '44.1%', w: '6.5%', h: '9.2%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s03.mp3`, subtitle: '先找到数字 1' },
          ] },
          { region: { x: '39.2%', y: '14.2%', w: '55.8%', h: '64.4%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s04.mp3`, subtitle: '然后按顺序，数字和汉字轮流连' },
          ] },
          { region: { x: '43.3%', y: '58.7%', w: '48%', h: '19.1%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s05.mp3`, subtitle: '也就是：数字 1，汉字一，数字 2，汉字二，一直这样轮流连下去' },
          ] },
          { region: { x: '79.6%', y: '3.9%', w: '16.4%', h: '10.1%' }, lines: [
            { audio: `${AUDIO_BASE}/b1_s06.mp3`, subtitle: '明白了就点击开始' },
          ] },
        ],
      });
      break;
    case 'A1':
      // 2026-04-14 ini 精简版:4 步更有节奏
      await VoiceGuide.show({
        image: 'img/block4.webp',
        btnRegion: { x: '80.3%', y: '5%', w: '14.6%', h: '7.8%' },
        buttonText: '开始',
        pauseBetween: 500,
        steps: [
          { region: { x: '8.2%', y: '36.1%', w: '25.9%', h: '19.7%' }, lines: [
            { audio: `${AUDIO_BASE}/a1_s01.mp3`, subtitle: '屏幕上会出现不同的水果，每个水果上都有一个数字' },
          ] },
          { region: { x: '15.5%', y: '36.5%', w: '6.8%', h: '10%' }, lines: [
            { audio: `${AUDIO_BASE}/a1_s02.mp3`, subtitle: '不管是什么水果，都只看上面的数字' },
          ] },
          { region: { x: '10.6%', y: '44.5%', w: '5.7%', h: '8.7%' }, lines: [
            { audio: `${AUDIO_BASE}/a1_s03.mp3`, subtitle: '先找到数字 1' },
          ] },
          { region: { x: '39.7%', y: '58.6%', w: '55.1%', h: '23.7%' }, lines: [
            { audio: `${AUDIO_BASE}/a1_s04.mp3`, subtitle: '从 1 开始，按顺序一直连到最后一个数字' },
          ] },
          { region: { x: '79.5%', y: '4.2%', w: '16.4%', h: '9.7%' }, lines: [
            { audio: `${AUDIO_BASE}/a1_s05.mp3`, subtitle: '明白了就点击开始' },
          ] },
        ],
      });
      break;
    case 'B3':
      // 2026-04-14 ini 精简版:合并"苹果/柠檬"定义到一句
      await VoiceGuide.show({
        image: 'img/block5.webp',
        btnRegion: { x: '80.3%', y: '5%', w: '14.6%', h: '7.8%' },
        buttonText: '开始',
        pauseBetween: 500,
        steps: [
          { region: { x: '15.8%', y: '36.5%', w: '19.2%', h: '9.4%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s01.mp3`, subtitle: '这次要在苹果和柠檬之间轮流连。屏幕上有苹果，也有柠檬' },
          ] },
          { region: { x: '10.2%', y: '43.8%', w: '7.7%', h: '10.8%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s02.mp3`, subtitle: '先找到苹果里的数字 1' },
          ] },
          { region: { x: '54%', y: '36.8%', w: '25.6%', h: '19%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s03.mp3`, subtitle: '先连苹果，再连柠檬，两个水果轮流连' },
          ] },
          { region: { x: '47.3%', y: '34.5%', w: '38.5%', h: '45.7%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s04.mp3`, subtitle: '也就是：苹果 1，柠檬 1，苹果 2，柠檬 2，一直这样轮流连下去' },
          ] },
          { region: { x: '79.5%', y: '4.1%', w: '16.5%', h: '10%' }, lines: [
            { audio: `${AUDIO_BASE}/b3_s05.mp3`, subtitle: '明白了就点击开始' },
          ] },
        ],
      });
      break;
    case 'B4':
      // 2026-04-14 ini 精简版:第 1 步补"最后一个任务"开场
      await VoiceGuide.show({
        image: 'img/block6.webp',
        btnRegion: { x: '80.3%', y: '5%', w: '14.6%', h: '7.8%' },
        buttonText: '开始',
        pauseBetween: 500,
        steps: [
          { region: { x: '8.1%', y: '35.1%', w: '26.9%', h: '22.6%' }, lines: [
            { audio: `${AUDIO_BASE}/b4_s01.mp3`, subtitle: '最后一个任务。这次要从柠檬开始，在柠檬和苹果之间轮流连' },
          ] },
          { region: { x: '10.7%', y: '43.9%', w: '6.2%', h: '9.8%' }, lines: [
            { audio: `${AUDIO_BASE}/b4_s02.mp3`, subtitle: '先找到柠檬里的数字 1' },
          ] },
          { region: { x: '53.7%', y: '36.5%', w: '26.1%', h: '19.3%' }, lines: [
            { audio: `${AUDIO_BASE}/b4_s03.mp3`, subtitle: '先连柠檬，再连苹果，两个水果轮流连' },
          ] },
          { region: { x: '45.5%', y: '56.2%', w: '44%', h: '35%' }, lines: [
            { audio: `${AUDIO_BASE}/b4_s04.mp3`, subtitle: '也就是：柠檬 1，苹果 1，柠檬 2，苹果 2，一直这样轮流连下去' },
          ] },
          { region: { x: '79.2%', y: '4%', w: '16.7%', h: '10.1%' }, lines: [
            { audio: `${AUDIO_BASE}/b4_s05.mp3`, subtitle: '明白了就点击开始' },
          ] },
        ],
      });
      break;
    default:
      await showInstruction(taskType, '', '');
  }
}

// ============================================================
// Main entry point
// ============================================================
async function main() {
  // Setup canvas
  canvas = document.getElementById('tmt-canvas');
  dpr = window.devicePixelRatio || 1;
  canvasW = window.innerWidth;
  canvasH = window.innerHeight;
  canvas.width = canvasW * dpr;
  canvas.height = canvasH * dpr;
  canvas.style.width = canvasW + 'px';
  canvas.style.height = canvasH + 'px';
  ctx = canvas.getContext('2d');

  const sid = subjectId || 'P001';

  // F4 (2026-04-19): Block-level resume
  // block N = TASK_ORDER[N] (A0=0, B2=1, B1=2, A1=3, B3=4, B4=5)
  let START_BLOCK = 0;
  let SKIP_INSTRUCTIONS = false;
  if (window.ProgressAPI && window.ProgressAPI.getResumeParams) {
    const _rp = window.ProgressAPI.getResumeParams();
    START_BLOCK = _rp.startBlock;
    SKIP_INSTRUCTIONS = _rp.skipInstructions;
  }
  const TMT_TOTAL_BLOCKS = TASK_ORDER.length;
  if (START_BLOCK >= TMT_TOTAL_BLOCKS) {
    console.warn('[TMT] startBlock', START_BLOCK, '>= totalBlocks, falling back to 0');
    START_BLOCK = 0;
    SKIP_INSTRUCTIONS = false;
    if (window.ProgressAPI) window.ProgressAPI.clear('tmt', sid);
  }
  window.__paradigmName = 'tmt';
  window.__subjectId = sid;
  window.__totalBlocks = TMT_TOTAL_BLOCKS;
  window.__currentBlockIdx = START_BLOCK;
  window.__blockOrder = TASK_ORDER.slice();
  window.__balance = null;

  // Start paradigm camera (optional — skipped if not enabled in localStorage)
  try { await window.ParadigmCamera.init('tmt', sid); } catch (e) { console.warn('[TMT] camera init error:', e); }

  // Preload fruit images (for A1/B3/B4 tasks)
  await preloadFruitImages();

  // Preload audio + instruction images
  await new Promise(function(resolve) {
    var audioBase = '../../audio/tmt/';
    var files = [];
    // 2026-04-14 ini + 朝琮二次调整:B2/B1/A1/B3/B4 最后一句"有不清楚的可以问工作人员"已删
    var _tmtCounts = { rules: 7, a0: 4, a1: 5, b1: 6, b2: 5, b3: 5, b4: 5 };
    Object.keys(_tmtCounts).forEach(function(t) {
      var n = _tmtCounts[t];
      for (var i = 1; i <= n; i++) files.push(audioBase + t + '_s' + String(i).padStart(2,'0') + '.mp3');
    });
    // 2026-04-23 新增 rules 2 句
    files.push(audioBase + 'rules_one_stroke.mp3');
    files.push(audioBase + 'rules_no_cross.mp3');
    var imgFiles = ['img/rules.webp','img/block1.webp','img/block2.webp'];
    var loaded = 0, total = files.length + imgFiles.length;
    function tick() { loaded++; if (loaded >= total) resolve(); }
    files.forEach(function(f) { var a = new Audio(); a.oncanplaythrough = tick; a.onerror = tick; a.src = f; });
    imgFiles.forEach(function(f) { var img = new Image(); img.onload = tick; img.onerror = tick; img.src = f; });
    setTimeout(resolve, 10000); // 10秒兜底
  });

  // Collect subject ID if not in URL
  if (!subjectId) {
    await showInstruction(
      '连线测试 (TMT)',
      `被试编号: ${sid}<br>请确认后继续`,
      '如需更改，请在URL中添加 ?sid=编号'
    );
  }

  // F4: resume 时跳过练习和总指导(老人第一次就过了)
  if (START_BLOCK === 0) {
    // 1. Practice
    const practiceResult = await runPractice();
    if (practiceResult) {
      await saveTaskData(practiceResult, sid);
    }

    // 2. Formal task instruction (matches 2.webp)
    await showRichInstruction(
      '练习结束！',
      '',
      '接下来进入正式测试<br>连错了系统会提示，回到正确的点继续',
      {}
    );
  } else if (!SKIP_INSTRUCTIONS) {
    // 续做但不跳指导语 — 简短过渡页
    await showInstruction(
      '接着测试',
      `从第 ${START_BLOCK + 1} 部分继续<br>(共 ${TMT_TOTAL_BLOCKS} 部分)`,
      ''
    );
  }

  // 3. Run each sub-task
  const allResults = [];
  for (let i = 0; i < TASK_ORDER.length; i++) {
    // F4: 跳过已完成的 task
    if (i < START_BLOCK) continue;

    const taskType = TASK_ORDER[i];

    // Show task-specific rich instruction
    // F4: resume + skipInstructions 时 — 首个 task 也只放简短提示(不放完整 block.webp)
    if (SKIP_INSTRUCTIONS && i === START_BLOCK) {
      await showInstruction(
        `${taskType} - 接着测试`,
        '继续按规则连线<br>(按上次的方法)',
        ''
      );
    } else {
      await showTaskInstruction(taskType);
    }

    // Load layout
    // B4 (柠檬苹果交替) 固定用 layout 1,因为只有 layout 1 是 lemon-first,
    // 和指导语"先找柠檬里的数字 1"对得上。
    // PsychoPy 那边 B4 layout 1/2/3 起点混合(lemon/apple/apple),web 这边为了
    // 和指导语自洽,只用 lemon-first 那一个。layout2/3 文件保留但不加载。
    const taskLayoutId = (taskType === 'B4') ? 1 : layoutId;
    let layoutData;
    try {
      // 2026-04-19: 用带重试+UI的版本替代单次 fetch,防止偶发网络抖动静默跳过 block
      layoutData = await loadLayoutWithRetry(taskType, taskLayoutId);
    } catch (e) {
      if (e.skipped) {
        console.warn(`[TMT] block ${taskType} skipped by tester`);
      } else {
        console.error(`Failed to load layout for ${taskType}:`, e);
        await showInstruction('错误', `无法加载 ${taskType} 布局文件<br>${e.message}`, '');
      }
      continue;
    }

    // Parse nodes
    const { orderedNodes, lureNodes, allNodes, nodeRadius, renderDiam } = parseNodes(layoutData, taskType);

    if (orderedNodes.length === 0) {
      console.error(`No ordered nodes for ${taskType}`);
      continue;
    }

    // Run task
    const result = await runTMTTask({
      taskType,
      orderedNodes,
      lureNodes,
      allNodes,
      nodeRadius,
      hardLimit: HARD_LIMIT_S,
      layoutId: taskLayoutId,
    });

    allResults.push(result);
    await saveTaskData(result, sid);

    // F4: 写 progress 标记本 task 完成
    if (window.ProgressAPI && window.ProgressAPI.write) {
      window.ProgressAPI.write('tmt', sid, {
        lastCompletedBlockIdx: i,
        totalBlocks: TMT_TOTAL_BLOCKS,
        blockOrder: TASK_ORDER.slice(),
      });
      window.__currentBlockIdx = i + 1;
    }

    // Rest between tasks (except after last)
    if (i < TASK_ORDER.length - 1) {
      await showRest(taskType, i + 1, TASK_ORDER.length);
    }
  }

  // 注意力探针（全部子任务结束后）
  await showAttentionProbeAsync('tmt', 'end');

  // Stop paradigm camera before end screen (no-op if not enabled)
  try { await window.ParadigmCamera.stopAndSave(); } catch (e) { console.warn('[TMT] camera stop error:', e); }

  // 4. Unified end screen
  window.showEndScreen('tmt', sid);
}

// Start
main().catch(e => {
  console.error('TMT fatal error:', e);
  document.body.innerHTML = `<div class="tmt-instruction-overlay"><h2>出错了</h2><p>${e.message}</p></div>`;
});
