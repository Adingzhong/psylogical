/**
 * Visuospatial Navigation (Path Integration) Task — Web implementation
 * Based on PsychoPy visuospatial_navigation_task(demonstration only)_1.12_1.py
 *
 * Phases: Demo (4 trials) → Practice (≤3 rounds × 3 trials) → Formal (16 trials)
 * Local view movement → Global view click response → distance/angle error
 *
 * ═══════════════════════════════════════════════════════════════
 * DESIGN RATIONALE — all parameter choices are cited below.
 * ═══════════════════════════════════════════════════════════════
 *
 * GRID_SPACING_PX = 80 base (Surface: 60px ≈ 1.21° visual angle at 55cm)
 *   Visual angle calculation: Surface Pro 11 CSS 1440×960, physical ~28cm wide
 *   → 1 CSS px ≈ 0.194mm; 60px = 11.6mm; 2×arctan(11.6/(2×550)) ≈ 1.21°/cell.
 *   Increased from 40px (0.59°/cell) per elderly-usability feedback (20 testers,
 *   2026-04-06: "格子太小太密""头晕眼花").
 *   Reference (order-of-magnitude): Tcheang L, Bülthoff HH, Burgess N (2011)
 *     PNAS 108(8):3314–3319. DOI: 10.1073/pnas.1004298108
 *     VR floor tiles subtend ~3–8° at typical gaze angles. Note: 3D first-person
 *     geometry differs from our 2D top-down display; no published 2D PI paradigm
 *     reports grid-cell visual angle (confirmed by literature search 2026-04-08).
 *     This parameter is an original design choice justified by first-principles
 *     geometry and elderly visual acuity (Dou et al. 2022, PMC9376262).
 *
 * SPEED_PX_S = 90 base (unchanged) — visual speed ≈ 1.37°/s on Surface
 *   Calculation: 67.5 CSS px/s × 0.194mm/px ÷ 550mm × (180/π) ≈ 1.37°/s.
 *   References:
 *     Nau M et al. (2018) Nat Neurosci 21:188–190. DOI: 10.1038/s41593-017-0050-8
 *       Moving-dot paradigm used 7.5°/s; our 1.37°/s is substantially slower.
 *     Tan DS et al. (2004) CHI '04. DOI: 10.1145/985692.985748
 *       Fixed-speed PI tasks prevent speed-accuracy confounds.
 *     Stangl M et al. (2020) Nat Commun 11:2626. DOI: 10.1038/s41467-020-15805-9
 *       Real-walking PI at ~1.0–1.4 m/s (physical); passive display at 1 m/s
 *       virtual speed is consistent with literature range.
 *     Wuehr M et al. (2017) Front Neurol 8:173. DOI: 10.3389/fneur.2017.00173
 *       Elderly wheelchair-pushed speed 0.56–0.65 m/s.
 *   "Fast" perception was caused by dense grid (2.25 cells/s at old 30px spacing);
 *   increasing to 60px reduces passage rate to ~1.1 cells/s, resolving perception
 *   without changing speed parameter.
 *
 * Black masking (local view background = #000000):
 *   Stangl M et al. (2020) Nat Commun 11:2626. DOI: 10.1038/s41467-020-15805-9
 *     "precludes use of external landmarks, ensuring participants must rely on
 *     self-motion signals." Standard in Stangl/Wolbers group desktop PI paradigms.
 *   Burgess N et al. (2004) Hippocampus 14:216–231. DOI: 10.1002/hipo.10162
 *     Visible boundaries enable boundary-vector strategy, bypassing entorhinal
 *     grid-cell computation — the exact mechanism this paradigm measures.
 *   Murata A et al. (2004) Ergonomics 47:194–208. DOI: 10.1080/00140130310001629757
 *     High-contrast dark background produces less visual fatigue than low-contrast
 *     white background in sustained tasks — supports keeping black.
 *   Color unchanged; smooth 400ms fade transition added for elderly visual comfort.
 *
 * Fade transition (local ↔ global view):
 *   Murata A et al. (2004) Ergonomics 47:194–208. DOI: 10.1080/00140130310001629757
 *     Abrupt high-contrast switches increase after-image effects and visual fatigue.
 *   Original design: 400ms linear luminance fade via canvas overlay. No published
 *   PI paradigm reports transition animations (standard is hard cut), but this is
 *   an elderly-accessibility adaptation that does not alter stimulus content.
 *
 * Click marker (response confirmation — blue dot at tap location):
 *   Jenkins A et al. (2016) J Alzheimers Dis 54:1169–1182. DOI: 10.3233/JAD-160545
 *     Tablet cognitive tests must address "physical response requirements" and
 *     "performance feedback" for elderly users; without these, test validity is
 *     compromised.
 *   Zhang L et al. (2015) Hum Mov Sci 39:97–108. DOI: 10.1016/j.humov.2014.11.009
 *     Visual feedback of tap location significantly improves pointing accuracy in
 *     elderly under restricted-feedback conditions.
 *   Chrastil ER & Warren WH (2021) JEP:HPP 47:32–49. DOI: 10.1037/xhp0000875
 *     Execution error (motor response phase) is a major source of path integration
 *     error; click marker helps separate motor error from cognitive error.
 *   Howett D et al. (2019) Brain 142:1751–1766. DOI: 10.1093/brain/awz116
 *     Practice trials simultaneously display participant's response location and
 *     correct location — precedent for click marker + feedback marker design.
 *   WCAG 2.5.2 Pointer Cancellation: action on up-event allows cancel by sliding.
 *   WCAG 4.1.3 Status Messages: status changes must have perceivable feedback.
 *   Nielsen J (2010) NNGroup: feedback within 100ms feels instantaneous.
 *
 * Practice pass criterion:
 *   Per trial: distance error ≤ 3 grid cells (≈12% of screen width).
 *   Per round: ≥2/3 trials pass (≈70%). Max 3 rounds (2 retries).
 *   Rationale:
 *     Howett D et al. (2019) Brain 142:1751–1766. DOI: 10.1093/brain/awz116
 *       Healthy older adults: PI distance error ≈10–15% of arena diameter.
 *       Our 12% threshold aligns with healthy elderly performance.
 *     Stangl M et al. (2020) Nat Commun 11:2626. DOI: 10.1038/s41467-020-15805-9
 *       Older adults show 1.5–2× error vs. young; threshold accommodates this.
 *     Chance-level: random click on grid yields mean error ≈6 cells (√(W²+H²)/3);
 *       3-cell threshold is ~50% of chance, clearly above random performance.
 *     70% pass rate matches Flanker paradigm convention in this battery.
 *
 * ═══════════════════════════════════════════════════════════════
 * FULL REFERENCE LIST (alphabetical)
 * ═══════════════════════════════════════════════════════════════
 * [1]  Burgess N et al. (2004) Hippocampus 14:216–231.     DOI: 10.1002/hipo.10162
 * [2]  Chrastil ER & Warren WH (2021) JEP:HPP 47:32–49.   DOI: 10.1037/xhp0000875
 * [3]  Dou J et al. (2022) Front Psychol.                  PMC: PMC9376262
 * [4]  Howett D et al. (2019) Brain 142:1751–1766.         DOI: 10.1093/brain/awz116
 * [5]  Jenkins A et al. (2016) J Alzheimers Dis 54:1169.   DOI: 10.3233/JAD-160545
 * [6]  Murata A et al. (2004) Ergonomics 47:194–208.       DOI: 10.1080/00140130310001629757
 * [7]  Nau M et al. (2018) Nat Neurosci 21:188–190.        DOI: 10.1038/s41593-017-0050-8
 * [8]  Nielsen J (2010) NNGroup: Response Times.            URL: nngroup.com/articles/response-times-3-important-limits/
 * [9]  Stangl M et al. (2018) Curr Biol 28:1108–1115.      DOI: 10.1016/j.cub.2018.02.038
 * [10] Stangl M et al. (2020) Nat Commun 11:2626.          DOI: 10.1038/s41467-020-15805-9
 * [11] Tan DS et al. (2004) CHI '04.                       DOI: 10.1145/985692.985748
 * [12] Tcheang L et al. (2011) PNAS 108(8):3314–3319.      DOI: 10.1073/pnas.1004298108
 * [13] Wuehr M et al. (2017) Front Neurol 8:173.           DOI: 10.3389/fneur.2017.00173
 * [14] Zhang L et al. (2015) Hum Mov Sci 39:97–108.        DOI: 10.1016/j.humov.2014.11.009
 * [15] WCAG 2.5.2 Pointer Cancellation.                    URL: w3.org/WAI/WCAG21/Understanding/pointer-cancellation.html
 * [16] WCAG 4.1.3 Status Messages.                         URL: w3.org/WAI/WCAG21/Understanding/status-messages.html
 */

import { CONFIG, getUrlParams, timestamp } from '../../lib/shared-config.js';
import { saveCSV } from '../../lib/data-sync.js';
import { createCheckpoint } from '../../lib/checkpoint.js';

// ============================================================
// Constants
// ============================================================
// Scale visual parameters based on screen size (reference: 1920x1280 tablet)
const _screenScale = Math.min(window.innerWidth, window.innerHeight) / 1280;
const PX_PER_M = Math.round(90 * _screenScale);
const SPEED_PX_S = Math.round(90 * _screenScale);
// Grid spacing: 80px base → Surface 60px ≈ 1.21° visual angle at 55cm viewing distance
// Increased from 40px (0.59°) to reduce grid density per elderly-usability feedback.
// See design rationale in file header.
const GRID_SPACING_PX = Math.round(80 * _screenScale);
const LOCAL_WINDOW_PX = Math.round(220 * _screenScale);   // original: 220px
const GRID_COLOR = '#BFBFBF';                              // PsychoPy [0.5,0.5,0.5] = 75% grey
const GRID_LINE_WIDTH = 2;                                 // original: 2
const ARROW_COLOR = '#00FF00';                             // PsychoPy [-1,1,-1] = pure green
const END_MARKER_COLOR = '#000000';
const FEEDBACK_MARKER_COLOR = '#FF0000';
const CLICK_MARKER_COLOR = '#3B82F6';                      // Blue — participant's click location
const MARKER_RADIUS = 15;                                  // original: r=15 for both markers
const TRACE_LINE_WIDTH = 3;                                // original: lineWidth=3
const GUIDED_REVIEW_COLOR = '#1565C0';                     // feedback 回放完整路径色 — 深蓝,区别于动画阶段的黑色彗星尾
const GUIDED_REVIEW_WIDTH = 5;                             // 回放路径粗一点,视觉强化
const ITI_S = 2.0;

// Practice settings (mirrors Flanker pass-rate convention)
const PRACTICE_PASS_DISTANCE = 3 * GRID_SPACING_PX;       // ≤3 grid cells = pass for one trial
const PRACTICE_PASS_RATE = 0.70;                           // ≥70% trials pass = round passed
const MAX_PRACTICE_ROUNDS = 2;                             // max 2 rounds (1 retry)

// ============================================================
// Fixed trial data (exact match with PsychoPy source)
// ============================================================
const FIXED_TRIALS = [
  // Demo Phase
  { id: 1, phase: 'demo', turnCount: 0, turns: [], lengths: [3], heading: 335, startXY: [-244.70, 114.11], label: '不转向' },
  { id: 2, phase: 'demo', turnCount: 1, turns: ['L'], lengths: [4, 2], heading: 45, startXY: [-127.28, -381.84], label: '转向1次' },
  { id: 3, phase: 'demo', turnCount: 2, turns: ['R', 'L'], lengths: [5, 2, 3], heading: 195, startXY: [742.05, 12.48], label: '转向2次' },
  { id: 4, phase: 'demo', turnCount: 3, turns: ['L', 'R', 'L'], lengths: [2, 3, 4, 5], heading: 105, startXY: [835.23, -335.25], label: '转向3次' },

  // Formal Phase - Level 1 (0 turns)
  { id: 7, phase: 'formal', turnCount: 0, turns: [], lengths: [2], heading: 140, startXY: [137.89, -115.70] },
  { id: 8, phase: 'formal', turnCount: 0, turns: [], lengths: [3], heading: 75, startXY: [-69.88, -260.80] },
  { id: 9, phase: 'formal', turnCount: 0, turns: [], lengths: [4], heading: 280, startXY: [-62.51, 354.53] },
  { id: 10, phase: 'formal', turnCount: 0, turns: [], lengths: [5], heading: 315, startXY: [-318.20, 318.20] },

  // Formal Phase - Level 2 (1 turn)
  { id: 11, phase: 'formal', turnCount: 1, turns: ['L'], lengths: [3, 3], heading: 10, startXY: [-219.01, -312.78] },
  { id: 12, phase: 'formal', turnCount: 1, turns: ['L'], lengths: [4, 3], heading: 170, startXY: [401.42, 203.38] },
  { id: 13, phase: 'formal', turnCount: 1, turns: ['R'], lengths: [2, 5], heading: 295, startXY: [331.77, 353.31] },
  { id: 14, phase: 'formal', turnCount: 1, turns: ['R'], lengths: [4, 2], heading: 25, startXY: [-402.34, 10.99] },

  // Formal Phase - Level 3 (2 turns)
  { id: 15, phase: 'formal', turnCount: 2, turns: ['L', 'R'], lengths: [4, 2, 4], heading: 155, startXY: [728.61, -141.15] },
  { id: 16, phase: 'formal', turnCount: 2, turns: ['L', 'R'], lengths: [3, 5, 2], heading: 325, startXY: [-626.73, -110.51] },
  { id: 17, phase: 'formal', turnCount: 2, turns: ['R', 'L'], lengths: [2, 4, 3], heading: 350, startXY: [-380.65, 432.67] },
  { id: 18, phase: 'formal', turnCount: 2, turns: ['R', 'L'], lengths: [3, 4, 3], heading: 200, startXY: [630.56, -153.60] },

  // Formal Phase - Level 4 (3 turns)
  { id: 19, phase: 'formal', turnCount: 3, turns: ['L', 'R', 'L'], lengths: [3, 3, 5, 2], heading: 125, startXY: [781.59, -331.68] },
  { id: 20, phase: 'formal', turnCount: 3, turns: ['L', 'R', 'L'], lengths: [3, 2, 4, 3], heading: 355, startXY: [-666.82, -393.38] },
  { id: 21, phase: 'formal', turnCount: 3, turns: ['R', 'L', 'R'], lengths: [2, 4, 2, 4], heading: 65, startXY: [-804.68, -21.99] },
  { id: 22, phase: 'formal', turnCount: 3, turns: ['R', 'L', 'R'], lengths: [4, 2, 4, 3], heading: 5, startXY: [-756.48, 385.54] },
];

// Practice trials (separate from FIXED_TRIALS to support retry rounds).
// 3 trials: 0-turn (easiest, new) → 1-turn-L → 1-turn-R.
// ids 5, 6, 23 reserved; FIXED_TRIALS uses ids 1–4 (demo) and 7–22 (formal).
const PRACTICE_TRIALS = [
  // 0-turn: straight line east. actualStartXY ≈ [-202px, 0] after shiftToCenter.
  // Simplest possible: "I moved right, so I came from the left." Intuitive intro.
  { id: 23, phase: 'practice', turnCount: 0, turns: [], lengths: [3], heading: 0, startXY: [0, 0] },
  // 1-turn-L (original practice trial 5)
  { id: 5,  phase: 'practice', turnCount: 1, turns: ['L'], lengths: [2, 4], heading: 225, startXY: [-127.28, 381.84] },
  // 1-turn-R (original practice trial 6)
  { id: 6,  phase: 'practice', turnCount: 1, turns: ['R'], lengths: [4, 3], heading: 245, startXY: [396.85, 212.16] },
];

// Guided practice (2026-04-23 — demo 和 practice 之间的引导阶段).
// 视觉和 demo 一致 (全景 + 完整路径 + 黑线),但走完后让老人自己点起点并获得反馈.
// 把"只看 demo"和"小窗口无辅助 practice"之间做一个难度台阶.
// ids 24, 25 不与 demo (1-4) / practice (5,6,23) / formal (7-22) 冲突.
const GUIDED_TRIALS = [
  // 1-turn-L — 简单转 1 次
  { id: 24, phase: 'guided', turnCount: 1, turns: ['L'], lengths: [3, 3], heading: 45, startXY: [-200, -100] },
  // 2-turn R-L — 中等,引入 2 转向
  { id: 25, phase: 'guided', turnCount: 2, turns: ['R', 'L'], lengths: [3, 2, 3], heading: 180, startXY: [300, 100] },
];

// ============================================================
// State
// ============================================================
let canvas, ctx;
let canvasW, canvasH;
let dpr = 1;
const { subjectId } = getUrlParams();

// ============================================================
// Path generation (matching PsychoPy)
// ============================================================
function generatePathPoints(startXY, heading, turns, lengthsM) {
  const points = [[...startXY]];
  let curX = startXY[0], curY = startXY[1];
  let curHeading = heading;
  const lengthsPx = lengthsM.map(l => l * PX_PER_M);

  for (let idx = 0; idx < lengthsPx.length; idx++) {
    const segLen = lengthsPx[idx];
    const rad = curHeading * Math.PI / 180;
    const nextX = curX + Math.cos(rad) * segLen;
    const nextY = curY + Math.sin(rad) * segLen;
    points.push([nextX, nextY]);
    curX = nextX;
    curY = nextY;

    if (idx < turns.length) {
      if (turns[idx] === 'L') curHeading += 90;
      else if (turns[idx] === 'R') curHeading -= 90;
    }
  }
  return points;
}

function shiftPointsToCenter(points, targetXY = [0, 0]) {
  const end = points[points.length - 1];
  const dx = targetXY[0] - end[0];
  const dy = targetXY[1] - end[1];
  return points.map(([x, y]) => [x + dx, y + dy]);
}

function degWrap(angleDeg) {
  while (angleDeg > 180) angleDeg -= 360;
  while (angleDeg < -180) angleDeg += 360;
  return angleDeg;
}

// ============================================================
// Canvas coordinate helpers
// Center of canvas is (0,0), Y-up
// ============================================================
function toScreen(worldX, worldY) {
  return [canvasW / 2 + worldX, canvasH / 2 - worldY];
}

function fromScreen(sx, sy) {
  return [sx - canvasW / 2, canvasH / 2 - sy];
}

// ============================================================
// Drawing helpers
// ============================================================
function clearWhite() {
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, canvasW * dpr, canvasH * dpr);
}

function drawGlobalGrid() {
  clearWhite();
  const halfW = canvasW / 2;
  const halfH = canvasH / 2;

  ctx.strokeStyle = GRID_COLOR;
  ctx.lineWidth = GRID_LINE_WIDTH * dpr;

  // Vertical lines
  let x = -halfW;
  while (x <= halfW) {
    const [sx] = toScreen(x, 0);
    ctx.beginPath();
    ctx.moveTo(sx * dpr, 0);
    ctx.lineTo(sx * dpr, canvasH * dpr);
    ctx.stroke();
    x += GRID_SPACING_PX;
  }

  // Horizontal lines
  let y = -halfH;
  while (y <= halfH) {
    const [, sy] = toScreen(0, y);
    ctx.beginPath();
    ctx.moveTo(0, sy * dpr);
    ctx.lineTo(canvasW * dpr, sy * dpr);
    ctx.stroke();
    y += GRID_SPACING_PX;
  }
}

function drawLocalView(worldPos) {
  // Black background outside local window
  ctx.fillStyle = '#000000';
  ctx.fillRect(0, 0, canvasW * dpr, canvasH * dpr);

  // White local window centered on screen
  const halfW = LOCAL_WINDOW_PX / 2;
  const cx = canvasW / 2;
  const cy = canvasH / 2;

  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect((cx - halfW) * dpr, (cy - halfW) * dpr, LOCAL_WINDOW_PX * dpr, LOCAL_WINDOW_PX * dpr);

  // Grid lines in local window (world coordinates shifted)
  ctx.save();
  ctx.beginPath();
  ctx.rect((cx - halfW) * dpr, (cy - halfW) * dpr, LOCAL_WINDOW_PX * dpr, LOCAL_WINDOW_PX * dpr);
  ctx.clip();

  ctx.strokeStyle = GRID_COLOR;
  ctx.lineWidth = GRID_LINE_WIDTH * dpr;

  const worldLeft = worldPos[0] - halfW;
  const worldRight = worldPos[0] + halfW;
  const worldBottom = worldPos[1] - halfW;
  const worldTop = worldPos[1] + halfW;

  // Vertical grid lines
  let startX = Math.floor(worldLeft / GRID_SPACING_PX) * GRID_SPACING_PX;
  for (let wx = startX; wx <= worldRight; wx += GRID_SPACING_PX) {
    const screenX = cx + (wx - worldPos[0]);
    ctx.beginPath();
    ctx.moveTo(screenX * dpr, (cy - halfW) * dpr);
    ctx.lineTo(screenX * dpr, (cy + halfW) * dpr);
    ctx.stroke();
  }

  // Horizontal grid lines
  let startY = Math.floor(worldBottom / GRID_SPACING_PX) * GRID_SPACING_PX;
  for (let wy = startY; wy <= worldTop; wy += GRID_SPACING_PX) {
    const screenY = cy - (wy - worldPos[1]);
    ctx.beginPath();
    ctx.moveTo((cx - halfW) * dpr, screenY * dpr);
    ctx.lineTo((cx + halfW) * dpr, screenY * dpr);
    ctx.stroke();
  }

  ctx.restore();

  // Border around local window — PsychoPy [0.3,0.3,0.3] = #A5A5A5
  ctx.strokeStyle = '#A5A5A5';
  ctx.lineWidth = 3 * dpr;
  ctx.strokeRect((cx - halfW) * dpr, (cy - halfW) * dpr, LOCAL_WINDOW_PX * dpr, LOCAL_WINDOW_PX * dpr);
}

// Original PsychoPy arrow vertices (Y-up):
// [(-18,-10),(0,-10),(0,-20),(20,0),(0,20),(0,10),(-18,10)]
// PsychoPy uses ori rotation; in demo, arrow doesn't rotate (ori=0).
// In local view, ori = -(heading_deg) so arrow points in movement direction.
// Canvas Y is inverted, so we negate Y in the vertex list.
const ARROW_VERTS = [
  [-18,  10], [0,  10], [0,  20], [20, 0],
  [0, -20], [0, -10], [-18, -10],
];

function drawArrow(screenX, screenY, heading) {
  const cx = screenX * dpr;
  const cy = screenY * dpr;
  const sc = dpr * _screenScale;      // scale factor for arrow

  ctx.save();
  ctx.translate(cx, cy);
  // PsychoPy ori rotation: positive = counter-clockwise
  // Canvas rotate: positive = clockwise
  // The heading passed here is math-convention (atan2), so rotate accordingly.
  ctx.rotate(-heading * Math.PI / 180);

  ctx.fillStyle = ARROW_COLOR;
  ctx.strokeStyle = ARROW_COLOR;
  ctx.lineWidth = 1 * dpr;
  ctx.beginPath();
  ctx.moveTo(ARROW_VERTS[0][0] * sc, ARROW_VERTS[0][1] * sc);
  for (let i = 1; i < ARROW_VERTS.length; i++) {
    ctx.lineTo(ARROW_VERTS[i][0] * sc, ARROW_VERTS[i][1] * sc);
  }
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.restore();
}

function drawCircleMarker(worldX, worldY, color, radius = MARKER_RADIUS, label = null) {
  const [sx, sy] = toScreen(worldX, worldY);
  ctx.beginPath();
  ctx.arc(sx * dpr, sy * dpr, radius * _screenScale * dpr, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  if (label) {
    ctx.save();
    ctx.font = `${Math.round(24 * _screenScale) * dpr}px "Microsoft YaHei", "PingFang SC", sans-serif`;
    ctx.fillStyle = '#333333';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillText(label, sx * dpr, (sy - radius * _screenScale - 8) * dpr);
    ctx.restore();
  }
}

/**
 * Draw participant's click location as a blue dot with a label.
 * Shown immediately on touchend so elderly participants can confirm
 * their tap registered at the intended position.
 *
 * Citations:
 *   Jenkins et al. (2016) JAD 54:1169 — physical response requirements in elderly tablet testing
 *   Zhang et al. (2015) Hum Mov Sci 39:97 — visual tap-location feedback improves elderly accuracy
 *   WCAG 4.1.3 — status changes must have perceivable feedback
 */
function drawClickMarker(worldX, worldY) {
  drawCircleMarker(worldX, worldY, CLICK_MARKER_COLOR, MARKER_RADIUS, '您点的位置');
}

function drawTraceLine(points) {
  if (points.length < 2) return;
  ctx.beginPath();
  const [sx0, sy0] = toScreen(points[0][0], points[0][1]);
  ctx.moveTo(sx0 * dpr, sy0 * dpr);
  for (let i = 1; i < points.length; i++) {
    const [sx, sy] = toScreen(points[i][0], points[i][1]);
    ctx.lineTo(sx * dpr, sy * dpr);
  }
  ctx.strokeStyle = '#000000';
  ctx.lineWidth = TRACE_LINE_WIDTH * dpr;
  ctx.stroke();
}

/**
 * 彗星尾效果 — 路径尾部按距离从 head 逐渐透明.
 * 用于 guided 阶段: 箭头走的时候后面有一截尾巴,保持一定长度,超出部分渐变淡.
 * 到尾巴末端完全透明,不会突然消失.
 *
 * headArcOverride: 传入"虚拟 head 位置"(世界坐标系弧长, 从 path 起点算).
 *   不传 = 使用 points 最后一个点作为 head(等于正在走路的箭头位置).
 *   传入 > totalArc = 模拟 head 继续前进,用于 fade-out 收尾动画.
 */
function drawFadingTrail(points, headArcOverride) {
  if (points.length < 2) return;
  const arcLen = [0];
  for (let i = 1; i < points.length; i++) {
    arcLen.push(arcLen[i-1] + Math.hypot(
      points[i][0] - points[i-1][0],
      points[i][1] - points[i-1][1]
    ));
  }
  const headArc = (headArcOverride != null) ? headArcOverride : arcLen[arcLen.length - 1];
  const solidDist = GRID_SPACING_PX * 1.0;   // 距 head 1 格以内: 全黑
  const fadeDist  = GRID_SPACING_PX * 3.5;   // 距 head 3.5 格: 全透明

  function alphaAt(a) {
    const d = headArc - a;
    if (d < 0) return 0;
    if (d <= solidDist) return 1.0;
    if (d >= fadeDist) return 0.0;
    return 1.0 - (d - solidDist) / (fadeDist - solidDist);
  }

  ctx.lineWidth = TRACE_LINE_WIDTH * dpr;
  ctx.lineCap = 'round';

  for (let i = 0; i < points.length - 1; i++) {
    const a0 = alphaAt(arcLen[i]);
    const a1 = alphaAt(arcLen[i+1]);
    if (a0 <= 0.01 && a1 <= 0.01) continue;

    const [sx0, sy0] = toScreen(points[i][0], points[i][1]);
    const [sx1, sy1] = toScreen(points[i+1][0], points[i+1][1]);

    if (Math.abs(a0 - a1) < 0.02) {
      ctx.strokeStyle = `rgba(0,0,0,${(a0 + a1) / 2})`;
    } else {
      const grad = ctx.createLinearGradient(sx0 * dpr, sy0 * dpr, sx1 * dpr, sy1 * dpr);
      grad.addColorStop(0, `rgba(0,0,0,${a0})`);
      grad.addColorStop(1, `rgba(0,0,0,${a1})`);
      ctx.strokeStyle = grad;
    }
    ctx.beginPath();
    ctx.moveTo(sx0 * dpr, sy0 * dpr);
    ctx.lineTo(sx1 * dpr, sy1 * dpr);
    ctx.stroke();
  }
}

/**
 * Feedback 阶段回放完整路径 — 深蓝实心粗线,区别于动画阶段的绿色彗星尾.
 * 视觉意图: "这就是刚才箭头实际走过的路线,记住它的形状".
 */
function drawReviewPath(points) {
  if (points.length < 2) return;
  ctx.beginPath();
  const [sx0, sy0] = toScreen(points[0][0], points[0][1]);
  ctx.moveTo(sx0 * dpr, sy0 * dpr);
  for (let i = 1; i < points.length; i++) {
    const [sx, sy] = toScreen(points[i][0], points[i][1]);
    ctx.lineTo(sx * dpr, sy * dpr);
  }
  ctx.strokeStyle = GUIDED_REVIEW_COLOR;
  ctx.lineWidth = GUIDED_REVIEW_WIDTH * dpr;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.stroke();
}

/**
 * 动画把剩余尾巴一次性淡出去 (guided 阶段 click 前的过渡).
 * 原理: 把虚拟 head 继续向前推进 extraDist, 导致最后一段尾巴也进入透明区.
 */
async function fadeOutTrail(points, endXY, durationMs = 700) {
  if (points.length < 2) return;
  let totalArc = 0;
  for (let i = 1; i < points.length; i++) {
    totalArc += Math.hypot(
      points[i][0] - points[i-1][0],
      points[i][1] - points[i-1][1]
    );
  }
  const extraDist = GRID_SPACING_PX * 4.5;
  const startTime = performance.now();

  await new Promise(resolve => {
    function frame() {
      const elapsed = performance.now() - startTime;
      const frac = Math.min(elapsed / durationMs, 1);
      const virtualHead = totalArc + extraDist * frac;

      drawGlobalGrid();
      drawFadingTrail(points, virtualHead);
      drawCircleMarker(endXY[0], endXY[1], END_MARKER_COLOR, MARKER_RADIUS, '终点');

      if (frac < 1) requestAnimationFrame(frame);
      else resolve();
    }
    requestAnimationFrame(frame);
  });
}

function drawFixation() {
  clearWhite();
  const cx = canvasW / 2 * dpr;
  const cy = canvasH / 2 * dpr;
  const size = 20 * dpr;
  ctx.strokeStyle = '#000000';
  ctx.lineWidth = 3 * dpr;
  ctx.beginPath();
  ctx.moveTo(cx - size, cy);
  ctx.lineTo(cx + size, cy);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(cx, cy - size);
  ctx.lineTo(cx, cy + size);
  ctx.stroke();
}

// ============================================================
// Animation
// ============================================================
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/** Play audio file — stops previous audio before playing new */
let _currentAudio = null;
function playAudioFile(src) {
  try {
    if (_currentAudio) { _currentAudio.pause(); _currentAudio = null; }
    const a = new Audio(src);
    _currentAudio = a;
    a.addEventListener('ended', () => { if (_currentAudio === a) _currentAudio = null; });
    a.play().catch(() => {});
  } catch (e) {}
}

/**
 * Smooth luminance fade between local view (black bg) and global view (white bg).
 * Draws a semi-transparent overlay that transitions canvas from one state to another
 * over `durationMs` ms. The path animation does NOT start until the fade completes.
 *
 * direction: 'to-black' (global→local) | 'to-white' (local→global)
 *
 * Visual comfort rationale: Murata et al. (2004) Ergonomics 47:194 — abrupt
 * high-contrast switches increase visual fatigue; gradual transitions reduce
 * after-image effects for elderly participants.
 */
async function fadeTransition(direction, durationMs = 400) {
  const frames = Math.round(durationMs / 16);  // ~60fps
  // Snapshot the current canvas state BEFORE we start painting over it.
  // Each frame: restore snapshot → draw semi-transparent overlay at increasing alpha.
  const snapshot = ctx.getImageData(0, 0, canvasW * dpr, canvasH * dpr);
  const color = direction === 'to-black' ? '0,0,0' : '255,255,255';

  for (let i = 1; i <= frames; i++) {
    const alpha = i / frames;                  // 0 → 1 linearly
    ctx.putImageData(snapshot, 0, 0);          // restore base each frame
    ctx.fillStyle = `rgba(${color},${alpha})`;
    ctx.fillRect(0, 0, canvasW * dpr, canvasH * dpr);
    await new Promise(resolve => requestAnimationFrame(resolve));
  }
}

async function animateMovement(points, mode, instrText) {
  // mode: 'local' (moving dot in local view) or 'demo' (global view with trace)
  let totalDuration = 0;
  const currentTrail = [points[0]];

  for (let i = 0; i < points.length - 1; i++) {
    const start = points[i];
    const end = points[i + 1];
    const dx = end[0] - start[0];
    const dy = end[1] - start[1];
    const headingDeg = Math.atan2(dy, dx) * 180 / Math.PI;
    const segLen = Math.hypot(dx, dy);
    if (segLen <= 0) continue;
    const segTime = segLen / SPEED_PX_S;
    totalDuration += segTime;

    const startTime = performance.now();
    const segTimeMs = segTime * 1000;

    await new Promise(resolve => {
      function frame() {
        const elapsed = performance.now() - startTime;
        const frac = Math.min(elapsed / segTimeMs, 1);
        const worldX = start[0] + dx * frac;
        const worldY = start[1] + dy * frac;

        if (mode === 'local') {
          drawLocalView([worldX, worldY]);
          // Arrow at center of screen
          drawArrow(canvasW / 2, canvasH / 2, headingDeg);
        } else {
          // Demo / Guided: global view with trail
          drawGlobalGrid();
          if (instrText) {
            ctx.font = `bold ${34 * dpr}px "Microsoft YaHei", "PingFang SC", sans-serif`;
            ctx.fillStyle = '#333333';
            ctx.textAlign = 'center';
            ctx.fillText(instrText, canvasW / 2 * dpr, 44 * dpr);
          }
          // Draw trail so far + current position.
          // 'demo' 模式: 实心全轨迹(看完整路径)
          // 'guided' 模式: 彗星尾,尾部渐隐(避免"看到线直接点"太简单)
          const trailWithCurrent = [...currentTrail, [worldX, worldY]];
          if (mode === 'guided') {
            drawFadingTrail(trailWithCurrent);
          } else {
            drawTraceLine(trailWithCurrent);
          }
          const [sx, sy] = toScreen(worldX, worldY);
          drawArrow(sx, sy, headingDeg);
        }

        if (frac < 1) {
          requestAnimationFrame(frame);
        } else {
          currentTrail.push(end);
          resolve();
        }
      }
      requestAnimationFrame(frame);
    });
  }

  return totalDuration;
}

// ============================================================
// Instruction overlay
// ============================================================
function showInstruction(title, body, hint) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'nav-overlay';
    overlay.innerHTML = `
      <h2>${title}</h2>
      <p>${body}</p>
      ${hint ? `<p class="hint">${hint}</p>` : ''}
      <button class="btn-primary" style="position:fixed; bottom:32px; left:50%; transform:translateX(-50%); z-index:200; min-width:240px; min-height:96px;">继续</button>
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

// ============================================================
// Click response collection
// ============================================================
function collectClick(instrText) {
  const instrDiv = document.getElementById('nav-instruction');
  if (instrDiv) instrDiv.textContent = instrText;

  return new Promise(resolve => {
    const startTime = performance.now();

    // v2: 漂移追踪 — 记录 pointerdown→pointerup 之间的运动轨迹
    // 设计: pointerdown = 认知决策时刻(RT), pointerup = 最终提交位置(不改)
    // 漂移数据 = 运动控制精度指标 (Iakovakis 2018; Elboim-Gabyzon 2021)
    let downTime = null, downClientX = null, downClientY = null;
    let driftMaxSq = 0, driftPath = 0, lastMoveX = 0, lastMoveY = 0;
    let inputType = null;
    let tapCount = 0;

    function onPointerDown(e) {
      tapCount++;
      if (tapCount === 1) {
        // 第一次按下: 记录认知决策时刻
        downTime = performance.now();
        downClientX = e.clientX;
        downClientY = e.clientY;
        lastMoveX = e.clientX;
        lastMoveY = e.clientY;
        driftMaxSq = 0;
        driftPath = 0;
        inputType = e.pointerType || null;
      }
      // 后续按下: 只增加 tap_count, 不更新 RT
    }

    function onPointerMove(e) {
      if (downClientX === null) return;
      const dx = e.clientX - downClientX;
      const dy = e.clientY - downClientY;
      const distSq = dx * dx + dy * dy;
      if (distSq > driftMaxSq) driftMaxSq = distSq;
      driftPath += Math.sqrt(
        Math.pow(e.clientX - lastMoveX, 2) + Math.pow(e.clientY - lastMoveY, 2)
      );
      lastMoveX = e.clientX;
      lastMoveY = e.clientY;
    }

    function onPointerUp(e) {
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      const [wx, wy] = fromScreen(sx, sy);
      // RT = pointerdown 时刻 (认知决策时间, Kay 2013 PVT-Touch)
      // 回退: 如果没有 pointerdown 数据, 用 pointerup (兼容鼠标)
      const rt = downTime !== null ? (downTime - startTime) : (performance.now() - startTime);
      const holdDuration = downTime !== null ? (performance.now() - downTime) : 0;
      const driftEnd = downClientX !== null
        ? Math.sqrt(Math.pow(e.clientX - downClientX, 2) + Math.pow(e.clientY - downClientY, 2))
        : 0;

      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup', onPointerUp);
      if (instrDiv) instrDiv.textContent = '';

      // Immediately draw click marker so participant can confirm tap position
      // (WCAG 2.5.2: action on up-event; Zhang et al. 2015: tap feedback for elderly)
      drawClickMarker(wx, wy);

      resolve({
        clickX: wx, clickY: wy,
        rtMs: Math.round(rt),
        // v2: 运动功能指标
        rt_hold: Math.round(holdDuration),
        drift_max: Math.round(Math.sqrt(driftMaxSq)),
        drift_path: Math.round(driftPath),
        drift_end: Math.round(driftEnd),
        tap_count: tapCount,
        input_type: inputType,
      });
    }

    // pointerdown: 记录认知决策时刻 + 开始漂移追踪
    canvas.addEventListener('pointerdown', onPointerDown);
    // pointermove: 追踪漂移轨迹
    canvas.addEventListener('pointermove', onPointerMove);
    // pointerup: 最终提交位置 (WCAG 2.5.2 Pointer Cancellation)
    canvas.addEventListener('pointerup', onPointerUp);
  });
}

// ============================================================
// CSV generation
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

// ============================================================
// Practice runner (supports retry rounds)
// ============================================================
/**
 * Run up to MAX_PRACTICE_ROUNDS rounds of practice.
 * Each round has 3 trials (PRACTICE_TRIALS). A trial is "passed" if distance
 * error ≤ PRACTICE_PASS_DISTANCE (3 grid cells). A round is passed if ≥70%
 * of trials are passed (Flanker convention). On failure, offer retry.
 *
 * Returns array of practice trial data rows to append to main trialData.
 *
 * Citations for retry design:
 *   Howett et al. (2019) Brain 142:1751 — practice with feedback before formal
 *   Flanker paradigm convention (this codebase) — 70% threshold, max 3 rounds
 */
/**
 * Run guided practice — 2 trials with full-view path + click feedback.
 * 插在 demo 和 practice 之间,用 demo 的视觉(全景 + 完整路径),
 * 走完后让老人自己点起点,无论对错都显示正确位置并语音反馈.
 * 目的: 把"只看 demo"→"无辅助 practice" 之间的心理台阶拆成两步.
 * 不参与 pass/fail 判定,固定 2 trial 跑完就进 practice.
 * 数据写入 CSV, phase='guided', 分析时按 phase 过滤即可忽略.
 */
async function runGuidedPractice(sid, sessionId, startTrialCounter) {
  const guidedData = [];
  let trialCounter = startTrialCounter;
  const AUDIO_BASE_G = '../../audio/visuospatial';

  // ── Intro VoiceGuide (2026-04-23 晓烨标注 — 5 步红框, 含按钮区单步提示) ──
  await VoiceGuide.show({
    image: 'img/guided_intro.webp',
    btnRegion: { x: '78.9%', y: '4.5%', w: '16.7%', h: '8.6%' },
    buttonText: '开始',
    steps: [
      { region: { x: '4.7%', y: '20.5%', w: '28.6%', h: '62%' }, lines: [
        { audio: `${AUDIO_BASE_G}/guided_intro_s01.mp3?v=20260423b`, subtitle: '刚才看了4次演示，接下来让我们来试一试自己点击起点位置' },
      ] },
      { region: { x: '36.7%', y: '20.5%', w: '26.9%', h: '61.3%' }, lines: [
        { audio: `${AUDIO_BASE_G}/guided_intro_s02.mp3?v=20260423c`, subtitle: '箭头走过会留下一段痕迹，请您跟着看，并且记住它是怎么走的' },
      ] },
      { region: { x: '72.7%', y: '40.7%', w: '21.4%', h: '32.4%' }, lines: [
        { audio: `${AUDIO_BASE_G}/guided_intro_s03.mp3?v=20260423b`, subtitle: '箭头停下后，请在地图上点出它出发时的真正位置' },
      ] },
      { region: { x: '67.1%', y: '20.8%', w: '28.3%', h: '61.7%' }, lines: [
        { audio: `${AUDIO_BASE_G}/guided_intro_s04.mp3?v=20260423b`, subtitle: '点错也没关系，系统会告诉您正确位置在哪里' },
      ] },
      { region: { x: '78.3%', y: '3.9%', w: '18%', h: '10.2%' }, lines: [
        { audio: `${AUDIO_BASE_G}/guided_intro_s05.mp3?v=20260423b`, subtitle: '明白了就点击开始' },
      ] },
    ],
  });

  for (const trial of GUIDED_TRIALS) {
    trialCounter++;
    const { id: pathId, turnCount, turns, lengths, heading, startXY } = trial;

    const rawPoints = generatePathPoints(startXY, heading, turns, lengths);
    const points = shiftPointsToCenter(rawPoints, [0, 0]);
    const actualStartXY = points[0];
    const endXY = points[points.length - 1];

    // 1. Global grid + endpoint (1s, 锚定)
    drawGlobalGrid();
    drawCircleMarker(0, 0, END_MARKER_COLOR, MARKER_RADIUS, '终点');
    await sleep(1000);

    // 2. Show initial arrow on global view (1.5s)
    drawGlobalGrid();
    const [sx, sy] = toScreen(actualStartXY[0], actualStartXY[1]);
    drawArrow(sx, sy, heading);
    await sleep(1500);

    // 3. Animate on global view with comet-tail fading trail ('guided' 模式)
    const movementTime = await animateMovement(points, 'guided', null);

    // 3.5. 走完后花 700ms 把残留尾巴平滑淡出 (head 继续虚拟前进推进 fade 窗口)
    await fadeOutTrail(points, endXY, 700);

    // 4. Ask click: 只剩格子 + 终点 + 点起点语音
    drawGlobalGrid();
    drawCircleMarker(0, 0, END_MARKER_COLOR, MARKER_RADIUS, '终点');
    playAudioFile(`${AUDIO_BASE_G}/guided_ask.mp3`);
    const response = await collectClick('请点击起点位置');
    const { clickX, clickY, rtMs: clickRt,
            rt_hold: rHold, drift_max: dMax, drift_path: dPath,
            drift_end: dEnd, tap_count: tCount, input_type: iType } = response;

    // 5. Feedback: 重画完整画面 — 格子 + 完整路径回放(蓝) + 终点 + 用户点 + 正确位置(红)
    const distErrorPx = Math.hypot(clickX - actualStartXY[0], clickY - actualStartXY[1]);
    const distErrorM = distErrorPx / PX_PER_M;
    const clickAngle = Math.atan2(clickY - endXY[1], clickX - endXY[0]) * 180 / Math.PI;
    const correctAngle = Math.atan2(actualStartXY[1] - endXY[1], actualStartXY[0] - endXY[0]) * 180 / Math.PI;
    const angleError = degWrap(clickAngle - correctAngle);
    const correct = distErrorPx <= PRACTICE_PASS_DISTANCE;

    drawGlobalGrid();
    drawReviewPath(points);                                                                  // 蓝色完整路径(刚才走过的)
    drawCircleMarker(endXY[0], endXY[1], END_MARKER_COLOR, MARKER_RADIUS, '终点');
    drawCircleMarker(clickX, clickY, CLICK_MARKER_COLOR, MARKER_RADIUS, '您点的位置');
    drawCircleMarker(actualStartXY[0], actualStartXY[1], FEEDBACK_MARKER_COLOR, MARKER_RADIUS, '正确位置');
    playAudioFile(`${AUDIO_BASE_G}/${correct ? 'guided_correct' : 'guided_show_answer'}.mp3`);
    await sleep(correct ? 2500 : 4000);  // 给"对"短停,给"错"长停让老人看清答案

    guidedData.push({
      participantId: sid,
      sessionId: sessionId,
      phase: 'guided',
      trialIndex: trialCounter,
      pathId: pathId,
      turnCount: turnCount,
      turnDirections: turns.join('-'),
      turnAnglesDeg: Array(turnCount).fill('90').join('-'),
      segmentLengthsM: lengths.join(';'),
      totalPathLengthM: lengths.reduce((a, b) => a + b, 0),
      startX: actualStartXY[0].toFixed(2),
      startY: actualStartXY[1].toFixed(2),
      endX: endXY[0].toFixed(2),
      endY: endXY[1].toFixed(2),
      movementDurationMs: Math.round(movementTime * 1000),
      speedPxPerS: SPEED_PX_S,
      gridSpacingPx: GRID_SPACING_PX,
      localWindowPx: LOCAL_WINDOW_PX,
      clickX: clickX.toFixed(2),
      clickY: clickY.toFixed(2),
      clickRTms: clickRt,
      rt_hold: rHold, drift_max: dMax, drift_path: dPath,
      drift_end: dEnd, tap_count: tCount, input_type: iType,
      distanceErrorPx: distErrorPx.toFixed(2),
      distanceErrorM: distErrorM.toFixed(3),
      angleErrorDeg: angleError.toFixed(2),
      deviceInfo: `${canvasW}x${canvasH}`,
    });
  }

  // ── 无 outro: 走完 guided 直接进 runPractice 的原 5 步红框指导语(避免内容重叠) ──

  return { data: guidedData, nextCounter: trialCounter };
}

async function runPractice(sid, sessionId, startTrialCounter) {
  const practiceData = [];
  let trialCounter = startTrialCounter;

  // Voice-guided practice intro (2026-04-23 晓烨重构 — 6 steps, 13 lines, 新增"难度升级"等过渡)
  const AUDIO_BASE_P = '../../audio/visuospatial';
  await VoiceGuide.show({
    image: 'img/practice_intro.webp',
    btnRegion: { x: '80.1%', y: '4.9%', w: '15%', h: '8.2%' },
    buttonText: '开始练习',
    pauseBetween: 500,
    steps: [
      { region: { x: '6.1%', y: '14.8%', w: '27.3%', h: '59.8%' }, lines: [
        { audio: `${AUDIO_BASE_P}/practice_upgrade.mp3?v=20260423b`, subtitle: '您已经会了，接下来难度升级' },
        { audio: `${AUDIO_BASE_P}/practice_s01.mp3`,                 subtitle: '练习时视野会变小，移动时只能看到箭头附近一小块' },
        { audio: `${AUDIO_BASE_P}/practice_s02.mp3`,                 subtitle: '请您跟着箭头一起走' },
        { audio: `${AUDIO_BASE_P}/practice_s03.mp3`,                 subtitle: '根据背景变化感受一下它走了多远、往哪边拐了弯' },
      ] },
      { region: { x: '36.5%', y: '15.2%', w: '27.2%', h: '59.4%' }, lines: [
        { audio: `${AUDIO_BASE_P}/practice_walked.mp3?v=20260423b`,  subtitle: '这张图是箭头实际走过的路线，与您上一轮的练习一样' },
        { audio: `${AUDIO_BASE_P}/practice_endpoint.mp3?v=20260423b`, subtitle: '黑点为终点，您需要点击起点' },
      ] },
      { region: { x: '77.6%', y: '48.5%', w: '5.5%', h: '6.7%' }, lines: [
        { audio: `${AUDIO_BASE_P}/practice_diff.mp3?v=20260423c`,    subtitle: '区别在于终点最终会固定在地图正中间，也就是那个黑色圆点' },
        { audio: `${AUDIO_BASE_P}/practice_s05.mp3`,                 subtitle: '这时候您又会看到整张大地图' },
      ] },
      { region: { x: '67.3%', y: '15.7%', w: '27%', h: '59.2%' }, lines: [
        { audio: `${AUDIO_BASE_P}/practice_predict.mp3?v=20260423c`, subtitle: '请根据您刚才记住的路线，根据终点位置推测出箭头出发的位置' },
        { audio: `${AUDIO_BASE_P}/practice_click.mp3?v=20260423b`,   subtitle: '并在地图上点击起点位置' },
        { audio: `${AUDIO_BASE_P}/practice_s07.mp3`,                 subtitle: '点击后蓝色圆点就是您选的起点' },
      ] },
      { region: { x: '4.4%', y: '78%', w: '91.2%', h: '16.6%' }, lines: [
        { audio: `${AUDIO_BASE_P}/practice_s08.mp3`,                 subtitle: '练习阶段会显示正确答案，正式阶段不会' },
      ] },
      { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
        { audio: `${AUDIO_BASE_P}/practice_s09.mp3`,                 subtitle: '明白了就点击开始练习' },
      ] },
    ],
  });

  for (let round = 1; round <= MAX_PRACTICE_ROUNDS; round++) {
    const passResults = [];

    for (const trial of PRACTICE_TRIALS) {
      trialCounter++;
      const { id: pathId, turnCount, turns, lengths, heading, startXY } = trial;

      const rawPoints = generatePathPoints(startXY, heading, turns, lengths);
      const points = shiftPointsToCenter(rawPoints, [0, 0]);
      const actualStartXY = points[0];
      const endXY = points[points.length - 1];

      // 1. Global grid preview with endpoint (1s) — anchor before movement starts
      drawGlobalGrid();
      drawCircleMarker(0, 0, END_MARKER_COLOR, MARKER_RADIUS, '终点');
      await sleep(1000);

      // 2. Fade from global grid to black (snapshot is the white grid → overlay darkens)
      await fadeTransition('to-black', 400);

      // 3. Show local view start position (1.5s)
      drawLocalView(actualStartXY);
      drawArrow(canvasW / 2, canvasH / 2, heading);
      await sleep(1500);

      // 4. Animate movement in local view
      const movementTime = await animateMovement(points, 'local', null);

      // 5. Fade from local view (black) to white
      await fadeTransition('to-white', 400);

      // 6. Response: draw grid + endpoint, then collect click
      drawGlobalGrid();
      drawCircleMarker(0, 0, END_MARKER_COLOR, MARKER_RADIUS, '终点');
      const response = await collectClick('请点击起点位置');
      const { clickX, clickY, rtMs: clickRt,
              rt_hold: rHold, drift_max: dMax, drift_path: dPath,
              drift_end: dEnd, tap_count: tCount, input_type: iType } = response;

      // 7. Calculate error
      const distErrorPx = Math.hypot(clickX - actualStartXY[0], clickY - actualStartXY[1]);
      const distErrorM = distErrorPx / PX_PER_M;
      const clickAngle = Math.atan2(clickY - endXY[1], clickX - endXY[0]) * 180 / Math.PI;
      const correctAngle = Math.atan2(actualStartXY[1] - endXY[1], actualStartXY[0] - endXY[0]) * 180 / Math.PI;
      const angleError = degWrap(clickAngle - correctAngle);
      const trialPassed = distErrorPx <= PRACTICE_PASS_DISTANCE;
      passResults.push(trialPassed);

      // 8. Feedback: canvas already has grid + endpoint + blue click marker (from collectClick).
      // Just add red dot on top — do NOT redraw grid (clearWhite causes flash).
      // Howett et al. (2019) Brain 142:1751 — practice shows both participant and correct location
      drawCircleMarker(actualStartXY[0], actualStartXY[1], FEEDBACK_MARKER_COLOR, MARKER_RADIUS, '正确位置'); // red: correct
      await sleep(2000);

      practiceData.push({
        participantId: sid,
        sessionId: sessionId,
        phase: `practice_r${round}`,
        trialIndex: trialCounter,
        pathId: pathId,
        turnCount: turnCount,
        turnDirections: turns.join('-'),
        turnAnglesDeg: Array(turnCount).fill('90').join('-'),
        segmentLengthsM: lengths.join(';'),
        totalPathLengthM: lengths.reduce((a, b) => a + b, 0),
        startX: actualStartXY[0].toFixed(2),
        startY: actualStartXY[1].toFixed(2),
        endX: endXY[0].toFixed(2),
        endY: endXY[1].toFixed(2),
        movementDurationMs: Math.round(movementTime * 1000),
        speedPxPerS: SPEED_PX_S,
        gridSpacingPx: GRID_SPACING_PX,
        localWindowPx: LOCAL_WINDOW_PX,
        clickX: clickX.toFixed(2),
        clickY: clickY.toFixed(2),
        clickRTms: clickRt,
        rt_hold: rHold, drift_max: dMax, drift_path: dPath,
        drift_end: dEnd, tap_count: tCount, input_type: iType,
        distanceErrorPx: distErrorPx.toFixed(2),
        distanceErrorM: distErrorM.toFixed(3),
        angleErrorDeg: angleError.toFixed(2),
        deviceInfo: `${canvasW}x${canvasH}`,
      });
    }

    const passRate = passResults.filter(p => p).length / passResults.length;
    const roundPassed = passRate >= PRACTICE_PASS_RATE;

    if (roundPassed || round === MAX_PRACTICE_ROUNDS) break;

    // Offer retry
    await showInstruction(
      '再练一次',
      `我们再来练习一遍吧<br><br>记住：先在小窗口里看清楚箭头走了几步、转了哪个方向<br>走完后，在地图上点出<b>出发点</b>`,
      ''
    );
  }

  // 注意力探针（练习结束后）
  await showAttentionProbeAsync('visuospatial', 'after_practice');

  // Ready confirmation
  await showInstruction(
    '准备好了吗？',
    '接下来正式开始，不会再告诉您正确答案<br>请认真观察每一段路线',
    ''
  );

  return { data: practiceData, nextCounter: trialCounter };
}

// ============================================================
// Main task runner
// ============================================================
async function main() {
  canvas = document.getElementById('nav-canvas');
  dpr = window.devicePixelRatio || 1;
  canvasW = window.innerWidth;
  canvasH = window.innerHeight;
  canvas.width = canvasW * dpr;
  canvas.height = canvasH * dpr;
  canvas.style.width = canvasW + 'px';
  canvas.style.height = canvasH + 'px';
  ctx = canvas.getContext('2d');

  const sid = subjectId || 'P001';
  const sessionId = timestamp();

  // F4 (2026-04-19): Block-level resume
  // 语义: block 0 = demo(4 trials), block 1 = practice(1-3 轮), block 2 = formal(16 trials)
  let START_BLOCK = 0;
  let SKIP_INSTRUCTIONS = false;
  if (window.ProgressAPI && window.ProgressAPI.getResumeParams) {
    const _rp = window.ProgressAPI.getResumeParams();
    START_BLOCK = _rp.startBlock;
    SKIP_INSTRUCTIONS = _rp.skipInstructions;
  }
  const VSPA_TOTAL_BLOCKS = 3;
  if (START_BLOCK >= VSPA_TOTAL_BLOCKS) {
    console.warn('[visuospatial] startBlock', START_BLOCK, '>= totalBlocks, falling back to 0');
    START_BLOCK = 0;
    SKIP_INSTRUCTIONS = false;
    if (window.ProgressAPI) window.ProgressAPI.clear('visuospatial', sid);
  }
  window.__paradigmName = 'visuospatial';
  window.__subjectId = sid;
  window.__totalBlocks = VSPA_TOTAL_BLOCKS;
  window.__currentBlockIdx = START_BLOCK;
  window.__blockOrder = ['demo','practice','formal'];
  window.__balance = null;

  // Preload audio + instruction images
  await new Promise(function(resolve) {
    var audioBase = '../../audio/visuospatial/';
    var files = ['demo_0turn','demo_1turn','demo_2turn','demo_3turn','demo_end','demo_intro']
      .concat(['practice_s01','practice_s02','practice_s03','practice_s04','practice_s05','practice_s06','practice_s07','practice_s08','practice_s09'])
      .concat(['rules_s01','rules_s02','rules_s03','rules_s04','rules_s05','rules_s06','rules_s07'])
      .concat(['guided_intro_s01','guided_intro_s02','guided_intro_s03','guided_intro_s04','guided_intro_s05','guided_ask','guided_correct','guided_show_answer'])
      .concat(['practice_upgrade','practice_walked','practice_endpoint','practice_diff','practice_predict','practice_click'])
      .map(function(n) { return audioBase + n + '.mp3'; });
    var imgFiles = ['img/rules.webp','img/practice_intro.webp','img/guided_intro.webp'];
    var loaded = 0, total = files.length + imgFiles.length;
    function tick() { loaded++; if (loaded >= total) resolve(); }
    files.forEach(function(f) { var a = new Audio(); a.oncanplaythrough = tick; a.onerror = tick; a.src = f; });
    imgFiles.forEach(function(f) { var img = new Image(); img.onload = tick; img.onerror = tick; img.src = f; });
    setTimeout(resolve, 10000);
  });

  // Camera recording (optional)
  try {
    await window.ParadigmCamera.init('visuospatial', sid);
  } catch (e) {
    console.warn('[visuospatial] camera init skipped:', e.message);
  }

  // Data storage
  const trialData = [];
  const deviceInfo = `${canvasW}x${canvasH}`;
  const headers = [
    'participantId', 'sessionId', 'phase', 'trialIndex', 'pathId',
    'turnCount', 'turnDirections', 'turnAnglesDeg', 'segmentLengthsM', 'totalPathLengthM',
    'startX', 'startY', 'endX', 'endY',
    'movementDurationMs', 'speedPxPerS', 'gridSpacingPx', 'localWindowPx',
    'clickX', 'clickY', 'clickRTms',
    'rt_hold', 'drift_max', 'drift_path', 'drift_end', 'tap_count', 'input_type',
    'distanceErrorPx', 'distanceErrorM', 'angleErrorDeg', 'deviceInfo',
  ];

  // Checkpoint: save progress after each trial
  const checkpoint = createCheckpoint('visuospatial', sid, () => {
    if (trialData.length === 0) return null;
    return generateCSV(headers, trialData);
  });

  // Voice-guided rules instruction (2026-04-13 晓烨人工标注, 位置微调)
  const AUDIO_BASE = '../../audio/visuospatial';
  // F4: 仅 START_BLOCK === 0 时放完整 VoiceGuide;resume 场景用短提醒
  if (START_BLOCK === 0) {
    await VoiceGuide.show({
      image: 'img/rules.webp',
      btnRegion: { x: '80.1%', y: '4.9%', w: '15%', h: '8.2%' },
      buttonText: '开始',
      pauseBetween: 500,
      steps: [
        { region: { x: '6.2%', y: '16%', w: '27%', h: '56.4%' }, lines: [
          { audio: `${AUDIO_BASE}/rules_s01.mp3`, subtitle: '屏幕上会出现一个绿色小箭头' },
        ] },
        { region: { x: '36.2%', y: '16.1%', w: '27.7%', h: '56%' }, lines: [
          { audio: `${AUDIO_BASE}/rules_s02.mp3`, subtitle: '箭头会沿着一条路线移动，请注意观察它是怎么走的' },
          { audio: `${AUDIO_BASE}/rules_s03.mp3`, subtitle: '同时请记住箭头出发时的位置' },
        ] },
        { region: { x: '66.8%', y: '16.1%', w: '27.2%', h: '56.2%' }, lines: [
          { audio: `${AUDIO_BASE}/rules_s04.mp3`, subtitle: '箭头停下后，请在地图上点出它出发时的真正位置' },
        ] },
        { region: { x: '4.5%', y: '77.7%', w: '90.9%', h: '17.7%' }, lines: [
          { audio: `${AUDIO_BASE}/rules_s05.mp3`, subtitle: '接下来先看4次演示，从不转向到转3次方向' },
          { audio: `${AUDIO_BASE}/rules_s06.mp3`, subtitle: '演示中可以看到完整路线，请仔细观察' },
        ] },
        { region: { x: '79.6%', y: '4.1%', w: '16%', h: '9.8%' }, lines: [
          { audio: `${AUDIO_BASE}/rules_s07.mp3`, subtitle: '明白了就点击开始' },
        ] },
      ],
    });
  } else if (!SKIP_INSTRUCTIONS) {
    // 续做但不跳指导语 — 仍放完整(老人可能忘了规则)
    // 不给老人"接着做但看不到规则"的体验 — 放一个简短过渡页
    await showInstruction(
      '接着测试',
      START_BLOCK === 1
        ? '接下来从<b>练习</b>开始<br>箭头会在地图上走一段路<br>请在地图上点出它出发的位置'
        : '接下来进入<b>正式测试</b><br>箭头会在小视野里走一段路<br>请在地图上点出它出发的位置',
      ''
    );
  }
  // SKIP_INSTRUCTIONS 时完全跳过(主试已告知)

  let demoIdx = 0;
  let formalIdx = 0;
  let trialCounter = 0;
  const totalFormalTrials = FIXED_TRIALS.filter(t => t.phase === 'formal').length;
  let practiceDone = false;

  // Tester 模式下,给 4 次 demo 加一个"跳过"快捷键 + 浮动按钮
  let _skipDemoFlag = false;
  let _demoContinueResolve = null;  // 当前 demo 末尾"继续"等待的 resolver,Esc 时外部调用
  let _demoEscHandler = null;
  let _demoSkipBtn = null;
  const _testerMode = (() => {
    try { if (localStorage.getItem('tester_mode') === '1') return true; } catch(e){}
    return new URLSearchParams(location.search).get('tester') === '1';
  })();
  if (_testerMode && START_BLOCK < 1) {
    function _skipAllDemos() {
      _skipDemoFlag = true;
      if (_demoContinueResolve) { _demoContinueResolve(); _demoContinueResolve = null; }
    }
    _demoSkipBtn = document.createElement('button');
    _demoSkipBtn.textContent = '跳过演示 (Esc)';
    _demoSkipBtn.style.cssText = 'position:fixed;top:12px;right:12px;z-index:300;padding:8px 16px;min-height:34px;font-size:14px;font-family:"PingFang SC",sans-serif;background:rgba(60,60,60,0.6);color:#fff;border:none;border-radius:8px;cursor:pointer;touch-action:manipulation;';
    _demoSkipBtn.addEventListener('click', _skipAllDemos);
    document.body.appendChild(_demoSkipBtn);
    _demoEscHandler = (e) => { if (e.key === 'Escape') _skipAllDemos(); };
    document.addEventListener('keydown', _demoEscHandler);
  }
  function _cleanupDemoSkip() {
    if (_demoSkipBtn && _demoSkipBtn.parentNode) _demoSkipBtn.parentNode.removeChild(_demoSkipBtn);
    _demoSkipBtn = null;
    if (_demoEscHandler) { document.removeEventListener('keydown', _demoEscHandler); _demoEscHandler = null; }
  }

  for (const trial of FIXED_TRIALS) {
    trialCounter++;
    const { phase, id: pathId, turnCount, turns, lengths, heading, startXY, label } = trial;

    // F4 (2026-04-19): resume 时跳过 demo 阶段
    if (phase === 'demo' && START_BLOCK >= 1) continue;

    // ── Insert practice + formal-intro between demo and first formal trial ──
    if (phase === 'formal' && !practiceDone) {
      practiceDone = true;
      _cleanupDemoSkip();  // demo 阶段结束,撤掉 tester 跳过按钮
      // F4: demo 阶段刚结束(或被跳过) → 写 progress 标记 block 0 完成
      if (window.ProgressAPI && window.ProgressAPI.write) {
        window.ProgressAPI.write('visuospatial', sid, {
          lastCompletedBlockIdx: 0,
          totalBlocks: VSPA_TOTAL_BLOCKS,
          blockOrder: ['demo','practice','formal'],
        });
        window.__currentBlockIdx = 1;
      }
      // F4: resume 跳 practice(START_BLOCK>=2) 时不做 guided + practice
      if (START_BLOCK < 2) {
        // Guided (2 trials, full-view + click feedback) — demo→practice 之间的难度台阶
        const guidedResult = await runGuidedPractice(sid, sessionId, trialCounter);
        guidedResult.data.forEach(r => trialData.push(r));
        trialCounter = guidedResult.nextCounter;
        checkpoint.forceSave();

        const practiceResult = await runPractice(sid, sessionId, trialCounter);
        practiceResult.data.forEach(r => trialData.push(r));
        trialCounter = practiceResult.nextCounter;
        checkpoint.forceSave();
      }
      // practice 阶段结束 → 写 block 1 完成
      if (window.ProgressAPI && window.ProgressAPI.write) {
        window.ProgressAPI.write('visuospatial', sid, {
          lastCompletedBlockIdx: 1,
          totalBlocks: VSPA_TOTAL_BLOCKS,
          blockOrder: ['demo','practice','formal'],
        });
        window.__currentBlockIdx = 2;
      }
    }

    // Generate path
    const rawPoints = generatePathPoints(startXY, heading, turns, lengths);
    const points = shiftPointsToCenter(rawPoints, [0, 0]);
    const actualStartXY = points[0];
    const endXY = points[points.length - 1];

    let movementTime = 0;
    let clickX = null, clickY = null, clickRt = null;
    let rHold = '', dMax = '', dPath = '', dEnd = '', tCount = '', iType = '';
    let distErrorPx = null, distErrorM = null, angleError = null;

    if (phase === 'demo') {
      demoIdx++;

      // Tester 跳过 flag 已触发: 快速跳完剩余 demo,不跑动画不 draw
      if (_skipDemoFlag) continue;

      // Demo audio map
      const demoAudioMap = { 0: 'demo_0turn', 1: 'demo_1turn', 2: 'demo_2turn', 3: 'demo_3turn' };

      if (demoIdx === 1) {
        await showInstruction(
          '先看演示',
          '绿色箭头代表您自己<br><br>请看着箭头走过的路线<br>走完后，记住它从哪里出发的',
          ''
        );
        // Play intro audio (non-blocking, overlaps with instruction display)
        playAudioFile(`${AUDIO_BASE}/demo_intro.mp3`);
      }

      const instrText = `现在演示移动过程，当前${label || ''}，请认真观察。`;

      // Show initial position on global grid
      drawGlobalGrid();
      const [sx, sy] = toScreen(actualStartXY[0], actualStartXY[1]);
      drawArrow(sx, sy, heading);
      ctx.font = `bold ${34 * dpr}px "Microsoft YaHei", "PingFang SC", sans-serif`;
      ctx.fillStyle = '#333333';
      ctx.textAlign = 'center';
      ctx.fillText(instrText, canvasW / 2 * dpr, 44 * dpr);
      // Play demo audio for this turn count
      const demoAudioName = demoAudioMap[turnCount];
      if (demoAudioName) playAudioFile(`${AUDIO_BASE}/${demoAudioName}.mp3`);
      await sleep(1500);

      // Animate on global view
      if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
        window.ParadigmCamera.addEvent('path_start', { trial_index: trialCounter, phase: phase, turns: turnCount });
      }
      movementTime = await animateMovement(points, 'demo', instrText);
      if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
        window.ParadigmCamera.addEvent('path_end', { trial_index: trialCounter });
      }

      // Show feedback: red dot at start + continue button
      drawGlobalGrid();
      drawTraceLine(points);
      drawCircleMarker(actualStartXY[0], actualStartXY[1], FEEDBACK_MARKER_COLOR, MARKER_RADIUS, '出发点');
      ctx.font = `bold ${34 * dpr}px "Microsoft YaHei", "PingFang SC", sans-serif`;
      ctx.fillStyle = '#333333';
      ctx.textAlign = 'center';
      ctx.fillText('演示结束：红色圆点为真实出发点', canvasW / 2 * dpr, 44 * dpr);
      playAudioFile(`${AUDIO_BASE}/demo_end.mp3`);

      await new Promise(resolve => {
        let resolved = false;
        function done() {
          if (resolved) return;
          resolved = true;
          canvas.removeEventListener('pointerdown', onClick);
          if (btn.parentNode) btn.remove();
          _demoContinueResolve = null;
          resolve();
        }
        function onClick() { done(); }
        const btn = document.createElement('button');
        btn.className = 'btn-primary';
        btn.textContent = '继续';
        btn.style.cssText = 'position:fixed; bottom:40px; left:50%; transform:translateX(-50%); z-index:50; min-width:240px; min-height:96px;';
        document.body.appendChild(btn);
        btn.addEventListener('pointerup', done);
        canvas.addEventListener('pointerdown', onClick);
        // 允许 tester 跳过按钮/Esc 从外部触发 done
        _demoContinueResolve = done;
      });

    } else {
      // Formal phase
      formalIdx++;

      // Progress indicator (motivational, no spatial info — within-subject constant)
      const instrDiv = document.getElementById('nav-instruction');
      if (instrDiv) instrDiv.textContent = `第 ${formalIdx} / ${totalFormalTrials} 题`;

      // 1. Fixation (1s)
      drawFixation();
      await sleep(1000);

      // 2. Global grid + endpoint preview (1s) — anchor before movement
      drawGlobalGrid();
      drawCircleMarker(0, 0, END_MARKER_COLOR, MARKER_RADIUS, '终点');
      await sleep(1000);

      // 3. Fade from global grid to black, then show start position (1.5s)
      if (instrDiv) instrDiv.textContent = '';  // clear progress during local view
      await fadeTransition('to-black', 400);
      drawLocalView(actualStartXY);
      drawArrow(canvasW / 2, canvasH / 2, heading);
      await sleep(1500);

      // 4. Movement (local view)
      if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
        window.ParadigmCamera.addEvent('path_start', { trial_index: trialCounter, phase: phase, turns: turnCount });
      }
      movementTime = await animateMovement(points, 'local', null);
      if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
        window.ParadigmCamera.addEvent('path_end', { trial_index: trialCounter });
      }

      // 5. End pause in local view (1s)
      drawLocalView(endXY);
      drawArrow(canvasW / 2, canvasH / 2, 0);
      await sleep(1000);

      // 6. Fade from local view to white, then draw grid + endpoint + collect response
      await fadeTransition('to-white', 400);
      drawGlobalGrid();
      drawCircleMarker(0, 0, END_MARKER_COLOR, MARKER_RADIUS, '终点');
      const response = await collectClick('请点击起点位置');
      // collectClick already drew blue click marker immediately on tap
      clickX = response.clickX;
      clickY = response.clickY;
      clickRt = response.rtMs;
      rHold = response.rt_hold; dMax = response.drift_max; dPath = response.drift_path;
      dEnd = response.drift_end; tCount = response.tap_count; iType = response.input_type;

      // Calculate errors (no correct-answer feedback in formal phase)
      // Stangl et al. (2020) Nat Commun — formal trials have no feedback to avoid learning effects
      distErrorPx = Math.hypot(clickX - actualStartXY[0], clickY - actualStartXY[1]);
      distErrorM = distErrorPx / PX_PER_M;
      const clickAngle = Math.atan2(clickY - endXY[1], clickX - endXY[0]) * 180 / Math.PI;
      const correctAngle = Math.atan2(actualStartXY[1] - endXY[1], actualStartXY[0] - endXY[0]) * 180 / Math.PI;
      angleError = degWrap(clickAngle - correctAngle);
      if (typeof window.ParadigmCamera !== 'undefined' && window.ParadigmCamera.isRecording()) {
        window.ParadigmCamera.addEvent('response_click', { trial_index: trialCounter, click_x: Math.round(clickX), click_y: Math.round(clickY), error_px: Math.round(distErrorPx) });
      }

      // 7. ITI: canvas already shows grid + endpoint + click marker (drawn by collectClick).
      // Do NOT redraw — drawGlobalGrid() calls clearWhite() which causes grid flash.
      // Just wait, then clear for next trial.
      if (formalIdx < totalFormalTrials) {
        await sleep(ITI_S * 1000);
        clearWhite();
      }
    }

    // Record data
    trialData.push({
      participantId: sid,
      sessionId: sessionId,
      phase: phase,
      trialIndex: trialCounter,
      pathId: pathId,
      turnCount: turnCount,
      turnDirections: turns.join('-'),
      turnAnglesDeg: Array(turnCount).fill('90').join('-'),
      segmentLengthsM: lengths.join(';'),
      totalPathLengthM: lengths.reduce((a, b) => a + b, 0),
      startX: actualStartXY[0].toFixed(2),
      startY: actualStartXY[1].toFixed(2),
      endX: endXY[0].toFixed(2),
      endY: endXY[1].toFixed(2),
      movementDurationMs: Math.round(movementTime * 1000),
      speedPxPerS: SPEED_PX_S,
      gridSpacingPx: GRID_SPACING_PX,
      localWindowPx: LOCAL_WINDOW_PX,
      clickX: clickX !== null ? clickX.toFixed(2) : '',
      clickY: clickY !== null ? clickY.toFixed(2) : '',
      clickRTms: clickRt !== null ? clickRt : '',
      rt_hold: rHold, drift_max: dMax, drift_path: dPath,
      drift_end: dEnd, tap_count: tCount, input_type: iType,
      distanceErrorPx: distErrorPx !== null ? distErrorPx.toFixed(2) : '',
      distanceErrorM: distErrorM !== null ? distErrorM.toFixed(3) : '',
      angleErrorDeg: angleError !== null ? angleError.toFixed(2) : '',
      deviceInfo: deviceInfo,
    });

    // Checkpoint: save after each trial completes
    checkpoint.save();
  }

  // 注意力探针（正式结束后）
  await showAttentionProbeAsync('visuospatial', 'end');

  // Stop camera recording
  try {
    await window.ParadigmCamera.stopAndSave();
  } catch (e) {
    console.warn('[visuospatial] camera stop skipped:', e.message);
  }

  // Save data
  const ts = timestamp();
  const filename = `visuospatial_navigation_${sid}_${ts}.csv`;
  let csvContent = generateCSV(headers, trialData);
  // F4 (2026-04-19): 合并上次会话 CSV
  if (window.ProgressAPI && window.ProgressAPI.getPrior) {
    const priorCSV = window.ProgressAPI.getPrior('visuospatial', sid);
    if (priorCSV) {
      csvContent = window.ProgressAPI.merge(priorCSV, csvContent);
      console.log('[visuospatial] merged prior CSV,final rows:', csvContent.split('\n').length - 2);
    }
  }

  if (typeof window.LocalPack !== 'undefined') {
    window.LocalPack.add(filename, csvContent);
  }

  try {
    await saveCSV('visuospatial', sid, filename, csvContent);
    // Final data saved successfully — clear checkpoint
    checkpoint.clear();
  } catch (e) {
    console.error('Data save error:', e);
    // Keep checkpoint intact so data can be recovered
  }

  // Unified end screen
  window.showEndScreen('visuospatial', sid);
}

// Start
main().catch(e => {
  console.error('Visuospatial navigation error:', e);
  document.body.innerHTML = `<div class="nav-overlay"><h2>出错了</h2><p>${e.message}</p></div>`;
});
