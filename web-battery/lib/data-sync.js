/**
 * 数据同步 — 发送到 FastAPI 后端 + 本地备份
 */

const API_BASE = window.location.origin;

/**
 * 保存 CSV 数据到后端
 */
export async function saveCSV(paradigm, subjectId, filename, csvContent) {
  // 1. localStorage 备份（防崩溃）
  const key = `backup_${paradigm}_${subjectId}_${Date.now()}`;
  try {
    localStorage.setItem(key, csvContent);
  } catch (e) {
    console.warn('localStorage backup failed:', e);
  }

  // 2. 发送到后端
  try {
    const _sf = typeof safeFetch === 'function' ? safeFetch : fetch;
    const resp = await _sf(`${API_BASE}/api/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paradigm, subject_id: subjectId, filename, content: csvContent }),
    });
    if (resp.ok) {
      // 保存成功，清除备份
      localStorage.removeItem(key);
      return { success: true, path: (await resp.json()).path };
    }
    throw new Error(`HTTP ${resp.status}`);
  } catch (e) {
    console.error('Save to server failed, data preserved in localStorage + LocalPack:', e);
    // 不再单独a.click()下载——数据已在LocalPack，showEndScreen的ZIP统一打包
    return { success: false, fallback: 'localpack' };
  }
}

/**
 * 保存 JSON 数据到后端
 */
export async function saveJSON(paradigm, subjectId, filename, jsonContent) {
  try {
    const _sf = typeof safeFetch === 'function' ? safeFetch : fetch;
    const resp = await _sf(`${API_BASE}/api/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paradigm, subject_id: subjectId, filename, content: jsonContent }),
    });
    if (resp.ok) return { success: true };
    throw new Error(`HTTP ${resp.status}`);
  } catch (e) {
    console.warn('JSON save to server failed, LocalPack has backup:', e);
    return { success: false, fallback: 'localpack' };
  }
}

/**
 * 上传视频到后端
 */
export async function saveVideo(subjectId, filename, blob) {
  try {
    const formData = new FormData();
    formData.append('file', blob, filename);
    formData.append('subject_id', subjectId);
    const _sf = typeof safeFetch === 'function' ? safeFetch : fetch;
    const resp = await _sf(`${API_BASE}/api/video`, {
      method: 'POST',
      body: formData,
    });
    if (resp.ok) return { success: true };
    throw new Error(`HTTP ${resp.status}`);
  } catch (e) {
    console.warn('Video upload failed, LocalPack has backup:', e);
    return { success: false, fallback: 'localpack' };
  }
}

/**
 * 浏览器下载 fallback
 */
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
