/**
 * 断点保存工具 — 实验过程中定期将已有数据保存到服务器
 *
 * 用法:
 *   import { createCheckpoint } from '../../lib/checkpoint.js';
 *   const checkpoint = createCheckpoint('flanker', subjectId, () => buildCSV());
 *   // 在每个trial/block结束后调用:
 *   checkpoint.save();
 *
 * 特性:
 *   - 非阻塞: 保存失败不影响实验流程
 *   - 节流: 最少间隔5秒，避免高频trial冲爆服务器
 *   - 覆盖式: 每次保存同名文件，服务器覆盖旧版本
 *   - localStorage双保险: 同时写localStorage防断网
 */

const API_BASE = window.location.origin;
const MIN_INTERVAL_MS = 5000; // 最少5秒保存一次

/**
 * 创建断点保存实例
 * @param {string} paradigm - 范式名 (flanker/sart/nback/...)
 * @param {string} subjectId - 被试编号
 * @param {Function} getDataFn - 返回当前已有CSV字符串的函数
 * @returns {{ save: Function, forceSave: Function }}
 */
export function createCheckpoint(paradigm, subjectId, getDataFn) {
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

    // 1. localStorage 备份 (同步, 即时)
    try { localStorage.setItem(lsKey, csv); } catch (e) { /* quota exceeded, ignore */ }

    // 2. 服务器保存 (异步, best-effort)
    try {
      await fetch(`${API_BASE}/api/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paradigm,
          subject_id: subjectId,
          filename,
          content: csv,
        }),
      });
    } catch (e) {
      // 静默失败 — localStorage已有备份
      console.debug(`[Checkpoint] ${paradigm} server save failed, localStorage backup exists`);
    }

    saving = false;

    // 处理节流期间积压的请求
    if (pendingSave) {
      pendingSave = false;
      doSave();
    }
  }

  return {
    /** 节流保存 — 高频调用安全，最少间隔5秒 */
    save() {
      const elapsed = Date.now() - lastSaveTime;
      if (elapsed < MIN_INTERVAL_MS) {
        // 还没到间隔，标记待保存，等下次调用
        if (!pendingSave) {
          pendingSave = true;
          setTimeout(() => {
            if (pendingSave) { pendingSave = false; doSave(); }
          }, MIN_INTERVAL_MS - elapsed);
        }
        return;
      }
      doSave();
    },

    /** 强制保存 — 跳过节流，用于block结束等重要节点 */
    forceSave() {
      doSave();
    },

    /** 清除checkpoint（实验正常结束后调用） */
    clear() {
      try { localStorage.removeItem(lsKey); } catch (e) { /* ignore */ }
    },
  };
}
