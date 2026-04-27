/**
 * 范式摄像头录制模块 v2 — OPFS静默断点保存 + 事件标记
 *
 * 特性:
 *   - 每30秒将视频chunk写入OPFS（浏览器内部存储），老人完全无感
 *   - 关页面/崩溃最多丢30秒，其余数据持久保存
 *   - 事件标记(stimulus_onset/response等)双时间戳，方便后续视频-行为对齐
 *   - 范式结束时自动合并chunks为完整视频 + 导出事件CSV
 *   - 主页可检测残留数据并恢复
 *
 * 用法:
 *   await ParadigmCamera.init('flanker', 'P001');
 *   ParadigmCamera.addEvent('stimulus_onset', { trial: 1, image: 'xxx.png' });
 *   ParadigmCamera.addEvent('response', { trial: 1, key: 'left', rt: 456 });
 *   await ParadigmCamera.stopAndSave();
 *
 * 事件CSV输出格式:
 *   event,time_ms,epoch_ms,trial_index,detail
 */

window.ParadigmCamera = (function () {
  'use strict';

  var CHUNK_INTERVAL_MS = 30000; // 30秒一个chunk

  // State
  var stream = null;
  var recorder = null;
  var mimeType = '';
  var paradigmName = '';
  var subjectId = '';
  var recordingStartTime = 0; // performance.now() at recording start
  var recordingStartEpoch = 0; // Date.now() at recording start
  var events = [];
  var enabled = false;
  var opfsDir = null; // OPFS directory handle
  var chunkIndex = 0;
  var pendingChunk = null; // blob being written to OPFS

  // ============================================================
  // OPFS helpers
  // ============================================================

  async function getOpfsRoot() {
    try {
      var root = await navigator.storage.getDirectory();
      return await root.getDirectoryHandle('paradigm_video', { create: true });
    } catch (e) {
      console.warn('[ParadigmCamera] OPFS not available:', e.message);
      return null;
    }
  }

  async function getSessionDir(name, sid) {
    if (!opfsDir) return null;
    var dirName = name + '_' + sid + '_' + Date.now();
    try {
      return await opfsDir.getDirectoryHandle(dirName, { create: true });
    } catch (e) {
      console.warn('[ParadigmCamera] cannot create session dir:', e);
      return null;
    }
  }

  var sessionDir = null;
  var sessionDirName = '';

  async function writeChunkToOPFS(blob, idx) {
    if (!sessionDir) return;
    try {
      var filename = 'chunk_' + String(idx).padStart(4, '0') + '.webm';
      var fh = await sessionDir.getFileHandle(filename, { create: true });
      var writable = await fh.createWritable();
      await writable.write(blob);
      await writable.close();
    } catch (e) {
      console.warn('[ParadigmCamera] OPFS chunk write failed:', e.message);
    }
  }

  async function writeMetaToOPFS() {
    if (!sessionDir) return;
    try {
      var meta = {
        paradigm: paradigmName,
        subject_id: subjectId,
        start_epoch: recordingStartEpoch,
        chunk_count: chunkIndex,
        mime_type: mimeType,
        completed: false,
      };
      var fh = await sessionDir.getFileHandle('meta.json', { create: true });
      var w = await fh.createWritable();
      await w.write(JSON.stringify(meta));
      await w.close();
    } catch (e) { /* silent */ }
  }

  async function writeEventsToOPFS() {
    if (!sessionDir) return;
    try {
      var csv = buildEventsCSV();
      var fh = await sessionDir.getFileHandle('events.csv', { create: true });
      var w = await fh.createWritable();
      await w.write(csv);
      await w.close();
    } catch (e) { /* silent */ }
  }

  async function readAllChunks() {
    if (!sessionDir) return [];
    var blobs = [];
    try {
      var entries = [];
      for await (var entry of sessionDir.values()) {
        if (entry.kind === 'file' && entry.name.startsWith('chunk_')) {
          entries.push(entry);
        }
      }
      entries.sort(function(a, b) { return a.name.localeCompare(b.name); });
      for (var i = 0; i < entries.length; i++) {
        var file = await entries[i].getFile();
        blobs.push(file);
      }
    } catch (e) {
      console.warn('[ParadigmCamera] read chunks failed:', e);
    }
    return blobs;
  }

  async function deleteSessionDir() {
    if (!opfsDir || !sessionDirName) return;
    try {
      await opfsDir.removeEntry(sessionDirName, { recursive: true });
    } catch (e) { /* silent */ }
  }

  // ============================================================
  // Events
  // ============================================================

  function buildEventsCSV() {
    var BOM = '\uFEFF';
    var header = 'event,time_ms,epoch_ms,trial_index,detail\n';
    var rows = events.map(function (e) {
      var detail = e.detail ? JSON.stringify(e.detail).replace(/"/g, "'") : '';
      return e.event + ',' + e.time_ms.toFixed(1) + ',' + e.epoch_ms + ',' +
        (e.trial_index !== undefined ? e.trial_index : '') + ',' + detail;
    }).join('\n');
    return BOM + header + rows;
  }

  // ============================================================
  // Face alignment overlay
  // ============================================================

  function showFaceAlignment() {
    return new Promise(function (resolve) {
      var overlay = document.createElement('div');
      overlay.id = 'pc-face-overlay';
      overlay.innerHTML =
        '<div style="position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(255,255,255,0.97);z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding:16px 40px 0;box-sizing:border-box;">' +
          '<div style="font-size:36px;font-weight:700;color:#1A1A2E;margin-bottom:4px;">请对准面部位置</div>' +
          '<div style="font-size:22px;color:#666;margin-bottom:12px;">将面部对准下方轮廓框内</div>' +
          '<div style="position:relative;width:280px;height:340px;border-radius:16px;overflow:hidden;background:#1A1A2E;box-shadow:0 4px 24px rgba(0,0,0,0.15);">' +
            '<video id="pc-face-video" autoplay playsinline muted style="width:100%;height:100%;object-fit:cover;transform:scaleX(-1);"></video>' +
            '<svg style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;" viewBox="0 0 280 340">' +
              '<ellipse cx="140" cy="155" rx="90" ry="115" fill="none" stroke="#4CAF50" stroke-width="3" stroke-dasharray="10,5" opacity="0.85"/>' +
            '</svg>' +
          '</div>' +
          '<div style="margin-top:10px;font-size:20px;color:#666;">请保持面部在框内</div>' +
          '<button id="pc-face-confirm" style="margin-top:14px;padding:16px 48px;font-size:28px;font-weight:600;border:none;border-radius:12px;background:#1565C0;color:white;cursor:pointer;touch-action:manipulation;min-width:280px;">位置已对准，开始</button>' +
        '</div>';
      document.body.appendChild(overlay);

      var video = document.getElementById('pc-face-video');
      if (stream) video.srcObject = stream;

      document.getElementById('pc-face-confirm').addEventListener('click', function () {
        video.srcObject = null;
        document.body.removeChild(overlay);
        resolve();
      }, { once: true });
    });
  }

  // ============================================================
  // Public API
  // ============================================================

  async function init(name, sid) {
    paradigmName = name;
    subjectId = sid;
    events = [];
    chunkIndex = 0;

    // 2026-04-19: 清理上一次的 blob URL(同 tab 反复 init 时防内存泄漏)
    if (ParadigmCamera._lastVideoUrl) {
      try { URL.revokeObjectURL(ParadigmCamera._lastVideoUrl); } catch (e) { /* ignore */ }
      ParadigmCamera._lastVideoUrl = null;
    }

    if (localStorage.getItem('camera_enabled') !== 'true') {
      console.log('[ParadigmCamera] recording not enabled, skipping');
      return false;
    }

    // Request camera
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
    } catch (e) {
      console.warn('[ParadigmCamera] camera unavailable:', e.message);
      return false;
    }

    // Codec
    var types = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm', 'video/mp4'];
    mimeType = '';
    for (var i = 0; i < types.length; i++) {
      if (MediaRecorder.isTypeSupported(types[i])) { mimeType = types[i]; break; }
    }

    // Setup OPFS
    opfsDir = await getOpfsRoot();
    if (opfsDir) {
      sessionDirName = name + '_' + sid + '_' + Date.now();
      try {
        sessionDir = await opfsDir.getDirectoryHandle(sessionDirName, { create: true });
      } catch (e) { sessionDir = null; }
    }

    // Request persistent storage
    try { await navigator.storage.persist(); } catch (e) { /* silent */ }

    // Face alignment
    await showFaceAlignment();

    // Start recording
    recordingStartTime = performance.now();
    recordingStartEpoch = Date.now();

    var opts = mimeType ? { mimeType: mimeType } : {};
    recorder = new MediaRecorder(stream, opts);

    recorder.ondataavailable = function (e) {
      if (e.data && e.data.size > 0) {
        var idx = chunkIndex++;
        // Write to OPFS silently
        writeChunkToOPFS(e.data, idx);
        // Also update meta
        writeMetaToOPFS();
        // Periodically save events too
        if (idx % 2 === 0) writeEventsToOPFS();
      }
    };

    recorder.start(CHUNK_INTERVAL_MS);
    enabled = true;

    addEvent('recording_start', { paradigm: name, mime: mimeType });
    console.log('[ParadigmCamera] recording started, OPFS session:', sessionDirName);
    return true;
  }

  /**
   * 添加事件标记（视频-行为同步用）
   * @param {string} eventName - 事件名 (stimulus_onset, response, block_start, etc.)
   * @param {object} detail - 额外信息 {trial_index, image, key, rt, ...}
   */
  function addEvent(eventName, detail) {
    if (!enabled) return;
    var now = performance.now();
    var evt = {
      event: eventName,
      time_ms: now - recordingStartTime,
      epoch_ms: Date.now(),
      trial_index: detail && detail.trial_index !== undefined ? detail.trial_index : undefined,
      detail: detail || null,
    };
    events.push(evt);
  }

  /**
   * 停止录制 + 合并chunks + 保存
   */
  async function stopAndSave() {
    if (!enabled || !recorder) {
      _destroy();
      return { video: false, events: false };
    }

    addEvent('recording_end', { chunks: chunkIndex });

    // Stop recorder and get final chunk
    var finalBlob = await new Promise(function (resolve) {
      recorder.onstop = function () { resolve(null); };
      // Request final data
      try { recorder.requestData(); } catch (e) { /* silent */ }
      recorder.stop();
    });

    // Wait a moment for last ondataavailable to fire
    await new Promise(function (r) { setTimeout(r, 500); });

    // Save events to OPFS
    await writeEventsToOPFS();

    // Read all chunks from OPFS and merge
    var chunks = await readAllChunks();
    var mergedBlob;
    if (chunks.length > 0) {
      mergedBlob = new Blob(chunks, { type: mimeType || 'video/webm' });
      console.log('[ParadigmCamera] merged ' + chunks.length + ' chunks, ' +
        (mergedBlob.size / 1024 / 1024).toFixed(1) + 'MB');
    }

    var ts = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '').replace('T', '_');
    // sid 开头便于按被试编号在文件管理器里排序分组(所有 ZIP 也是 sid 开头)
    var videoFilename = subjectId + '_' + paradigmName + '_' + ts + '_video.webm';
    var eventsFilename = subjectId + '_' + paradigmName + '_' + ts + '_events.csv';
    var eventsCSV = buildEventsCSV();
    var result = { video: false, events: false };

    // 视频不自动下载！Edge 限制每个页面只允许一次自动下载(a.click)，
    // 如果这里用掉了，后面 showEndScreen 的 ZIP 下载就被拦截。
    // 改为：存储 blob URL，由 showEndScreen 显示手动下载按钮。
    if (mergedBlob && mergedBlob.size > 0) {
      var url = URL.createObjectURL(mergedBlob);
      // 暴露给 end-screen.js 使用
      ParadigmCamera._lastVideoUrl = url;
      ParadigmCamera._lastVideoName = videoFilename;
      ParadigmCamera._lastVideoSize = mergedBlob.size;
      result.video = true;
      console.log('[ParadigmCamera] video ready for download: ' + videoFilename +
        ' (' + (mergedBlob.size / 1024 / 1024).toFixed(1) + 'MB)');

      // 2026-04-19 不再推视频到服务器 — 单个视频 ~1GB,几百被试会撑爆服务器.
      // 本地 LocalPack ZIP 已保留视频,主试手动下载即可.
      // (events CSV 和测评 CSV 继续上传服务器作数据备份)
    }

    // Events CSV 注册到 LocalPack（随行为数据一起 ZIP 下载）
    if (typeof LocalPack !== 'undefined' && eventsCSV && events.length > 1) {
      LocalPack.add(eventsFilename, eventsCSV);
    }

    // Events CSV 服务器备份
    if (eventsCSV && events.length > 1) {
      try {
        fetch(window.location.origin + '/api/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ paradigm: paradigmName, subject_id: subjectId, filename: eventsFilename, content: eventsCSV }),
        }).then(function () { result.events = true; }).catch(function () {});
      } catch (e) { /* silent */ }
    }

    // 延迟清理 OPFS —— a.click() 只排队下载，浏览器下载管理器是异步读取 Blob 数据的。
    // 如果立即删 OPFS，Blob 引用的 File handles 失效 → 下载报"网络错误"。
    // 延迟 3 分钟，给下载管理器充足时间读完数据。
    setTimeout(function () { deleteSessionDir(); }, 180000);

    _destroy();
    return result;
  }

  function _destroy() {
    if (stream) {
      stream.getTracks().forEach(function (t) { t.stop(); });
      stream = null;
    }
    recorder = null;
    enabled = false;
    sessionDir = null;
  }

  function isRecording() {
    return enabled && recorder && recorder.state === 'recording';
  }

  // ============================================================
  // Recovery: detect orphaned OPFS sessions
  // ============================================================

  /**
   * 检测未完成的录制会话（主页调用）
   * @returns {Promise<Array>} 未完成的会话列表 [{dir, meta}, ...]
   */
  async function detectOrphaned() {
    var root = await getOpfsRoot();
    if (!root) return [];
    var orphaned = [];
    try {
      for await (var entry of root.values()) {
        if (entry.kind === 'directory') {
          try {
            var metaFh = await entry.getFileHandle('meta.json');
            var metaFile = await metaFh.getFile();
            var meta = JSON.parse(await metaFile.text());
            if (!meta.completed) {
              orphaned.push({ dirName: entry.name, dir: entry, meta: meta });
            }
          } catch (e) { /* no meta = skip */ }
        }
      }
    } catch (e) { /* silent */ }
    return orphaned;
  }

  /**
   * 恢复并导出一个孤立会话的视频
   */
  async function recoverSession(dirEntry, meta) {
    var blobs = [];
    try {
      var entries = [];
      for await (var entry of dirEntry.values()) {
        if (entry.kind === 'file' && entry.name.startsWith('chunk_')) entries.push(entry);
      }
      entries.sort(function(a, b) { return a.name.localeCompare(b.name); });
      for (var i = 0; i < entries.length; i++) {
        blobs.push(await entries[i].getFile());
      }
    } catch (e) { return null; }

    if (blobs.length === 0) return null;
    var merged = new Blob(blobs, { type: meta.mime_type || 'video/webm' });
    return merged;
  }

  /**
   * 删除一个孤立会话
   */
  async function deleteOrphaned(dirName) {
    var root = await getOpfsRoot();
    if (!root) return;
    try { await root.removeEntry(dirName, { recursive: true }); } catch (e) { /* silent */ }
  }

  return {
    init: init,
    addEvent: addEvent,
    stopAndSave: stopAndSave,
    isRecording: isRecording,
    detectOrphaned: detectOrphaned,
    recoverSession: recoverSession,
    deleteOrphaned: deleteOrphaned,
    _lastVideoUrl: null,
    _lastVideoName: null,
    _lastVideoSize: 0,
  };
})();
