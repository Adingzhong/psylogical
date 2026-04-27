/**
 * Block-level 进度追踪 (F4 功能核心)
 *
 * 用法(经典脚本,非 ES 模块):
 *   <script src="../../lib/progress.js"></script>
 *
 *   // 读进度
 *   var prog = ProgressAPI.read('vstmb', 'P001');
 *   // prog === null (未开始) 或 { lastCompletedBlockIdx, totalBlocks, ... }
 *
 *   // Block 末写进度 (作为 jsPsych trial 插入 timeline)
 *   timeline.push(ProgressAPI.writeTrial('vstmb', sid, 1, 3, { blockOrder, balance }));
 *
 *   // 结束时清进度
 *   ProgressAPI.clear('vstmb', sid);
 *
 *   // saveData 时合并历史 CSV
 *   var priorCSV = ProgressAPI.getPrior('vstmb', sid);
 *   var merged   = ProgressAPI.merge(priorCSV, newCSV);
 *
 * Key 约定:
 *   progress_{sid}_{paradigm}  JSON,见 schema 注释
 *   checkpoint_{paradigm}_{sid} 历史 CSV (现有,本文件只读不写)
 */
(function () {
  'use strict';

  var SCHEMA_V = 1;

  /**
   * progress 对象 schema:
   *   v: 1
   *   paradigm: 'vstmb'
   *   sid: 'P001'
   *   totalBlocks: 3
   *   lastCompletedBlockIdx: 1        // -1 = 未完成任何 block
   *   blockOrder: ['Color','Binding','Object']   // VSTMB 拉丁方,其他 null
   *   balance: 'B'                    // VSTMB,其他 null
   *   paradigmState: { b4_gate: true } // N-back gate 等跨 block 状态
   *   updatedAt: 1713499200000
   *   startedAt: 1713498000000
   */

  function progressKey(paradigm, sid) {
    return 'progress_' + sid + '_' + paradigm;
  }

  function checkpointKey(paradigm, sid) {
    return 'checkpoint_' + paradigm + '_' + sid;
  }

  function readProgress(paradigm, sid) {
    if (!paradigm || !sid) return null;
    try {
      var raw = localStorage.getItem(progressKey(paradigm, sid));
      if (!raw) return null;
      var obj = JSON.parse(raw);
      // Schema 校验: 不匹配的老数据视为无效
      if (!obj || obj.v !== SCHEMA_V || obj.paradigm !== paradigm || obj.sid !== sid) {
        return null;
      }
      return obj;
    } catch (e) {
      return null;
    }
  }

  function writeProgress(paradigm, sid, patch) {
    if (!paradigm || !sid) return;
    try {
      var existing = {};
      try {
        var raw = localStorage.getItem(progressKey(paradigm, sid));
        if (raw) existing = JSON.parse(raw) || {};
      } catch (e) { /* corrupted, start fresh */ }

      var merged = {
        v: SCHEMA_V,
        paradigm: paradigm,
        sid: sid,
        totalBlocks: null,
        lastCompletedBlockIdx: -1,
        blockOrder: null,
        balance: null,
        paradigmState: null,
        startedAt: existing.startedAt || Date.now(),
      };
      // existing 覆盖默认 (保留老数据)
      for (var k in existing) merged[k] = existing[k];
      // patch 覆盖 existing (新写入)
      for (var k2 in patch) merged[k2] = patch[k2];
      merged.updatedAt = Date.now();

      localStorage.setItem(progressKey(paradigm, sid), JSON.stringify(merged));
    } catch (e) {
      // quota exceeded 或其他错误,silent 失败(不影响实验)
    }
  }

  function clearProgress(paradigm, sid) {
    if (!paradigm || !sid) return;
    try {
      localStorage.removeItem(progressKey(paradigm, sid));
    } catch (e) { /* ignore */ }
  }

  /**
   * 返回一个 jsPsychCallFunction trial,插入 timeline 在 block N 完成处。
   * 写入 progress + 更新 window.__currentBlockIdx(给三指退出用)。
   */
  function writeProgressTrial(paradigm, sid, blockIdx, totalBlocks, extras) {
    return {
      type: jsPsychCallFunction,
      func: function () {
        var patch = {
          lastCompletedBlockIdx: blockIdx,
          totalBlocks: totalBlocks,
        };
        if (extras) {
          for (var k in extras) patch[k] = extras[k];
        }
        writeProgress(paradigm, sid, patch);
        window.__currentBlockIdx = blockIdx + 1;
      },
    };
  }

  /**
   * 从 localStorage 读该被试该范式上一次未完成会话的 CSV (续写用)
   * 没有则返回空串
   */
  function getPriorCSV(paradigm, sid) {
    if (!paradigm || !sid) return '';
    try {
      return localStorage.getItem(checkpointKey(paradigm, sid)) || '';
    } catch (e) {
      return '';
    }
  }

  /**
   * 合并历史 CSV + 新 CSV (resume 时 saveData 上传用)
   * 假设 resume 只跑未做的 block,trial 不会重复 — 简单 concat + 去重(全行)
   *
   * @param priorCSV 上次会话的 CSV (可能为空)
   * @param newCSV   本次会话的 CSV
   * @return 合并后的 CSV
   */
  function mergeCSVByTrialIndex(priorCSV, newCSV) {
    var stripBOM = function (s) { return s.charCodeAt(0) === 0xFEFF ? s.slice(1) : s; };

    if (!priorCSV || !priorCSV.trim()) return newCSV || '';
    if (!newCSV || !newCSV.trim()) return priorCSV;

    var prior = stripBOM(priorCSV).replace(/\r\n/g, '\n').trim();
    var fresh = stripBOM(newCSV).replace(/\r\n/g, '\n').trim();

    var priorLines = prior.split('\n');
    var freshLines = fresh.split('\n');

    if (priorLines.length === 0 || freshLines.length === 0) return newCSV;

    var priorHeader = priorLines[0];
    var freshHeader = freshLines[0];

    if (priorHeader !== freshHeader) {
      console.warn('[Progress.merge] CSV header mismatch, using new CSV only');
      return newCSV;
    }

    // 合并: 用 fresh 的 header (相同) + 两份 data 行 + 去重(全行相等)
    var seen = Object.create(null);
    var out = [priorHeader];
    var all = priorLines.slice(1).concat(freshLines.slice(1));
    for (var i = 0; i < all.length; i++) {
      var line = all[i];
      if (!line) continue;
      if (seen[line]) continue;
      seen[line] = true;
      out.push(line);
    }

    // 保留 BOM (Excel 兼容)
    var prefix = priorCSV.charCodeAt(0) === 0xFEFF || newCSV.charCodeAt(0) === 0xFEFF ? '\uFEFF' : '';
    return prefix + out.join('\n') + '\n';
  }

  /**
   * 查询 URL 参数 ?disableResume=1 或 localStorage flag f4_disabled='1'
   * 命中时所有 resume 逻辑无视,走从头路径(紧急回滚用)
   */
  function isDisabled() {
    try {
      var urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('disableResume') === '1') return true;
      if (localStorage.getItem('f4_disabled') === '1') return true;
    } catch (e) { /* silent */ }
    return false;
  }

  /**
   * 从 URL 读 startBlock 和 skipInstructions
   * 返回规范化的 {startBlock, skipInstructions}
   */
  function getResumeParams() {
    try {
      if (isDisabled()) return { startBlock: 0, skipInstructions: false };
      var urlParams = new URLSearchParams(window.location.search);
      var sb = parseInt(urlParams.get('startBlock'), 10);
      if (isNaN(sb) || sb < 0) sb = 0;
      var si = urlParams.get('skipInstructions') === '1';
      return { startBlock: sb, skipInstructions: si };
    } catch (e) {
      return { startBlock: 0, skipInstructions: false };
    }
  }

  window.ProgressAPI = {
    read: readProgress,
    write: writeProgress,
    clear: clearProgress,
    writeTrial: writeProgressTrial,
    getPrior: getPriorCSV,
    merge: mergeCSVByTrialIndex,
    isDisabled: isDisabled,
    getResumeParams: getResumeParams,
  };
})();
