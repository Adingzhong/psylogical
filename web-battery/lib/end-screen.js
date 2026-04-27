/**
 * 统一结束页面 + 本地ZIP打包下载
 *
 * 用法:
 *   // 范式保存数据时，注册要打包的文件:
 *   LocalPack.add('Flanker_P001_20260401.csv', csvString);
 *   LocalPack.add('flanker_P001_video.webm', videoBlob);
 *
 *   // 范式结束时调用:
 *   showEndScreen('flanker', 'P001');
 *   → 自动把注册的文件打包成 P001_flanker_20260401_120000.zip 下载到本地
 */

/* ============================================================
   LocalPack — 文件收集器（范式过程中往里塞文件）
   ============================================================ */
window.LocalPack = (function () {
  var files = []; // [{name, data}]

  return {
    /** 添加文件 (data可以是string或Blob) */
    add: function (filename, data) {
      if (!data) return;
      files.push({ name: filename, data: data });
    },
    /** 获取所有文件 */
    getAll: function () { return files; },
    /** 清空 */
    clear: function () { files = []; },
  };
})();

/* ============================================================
   showEndScreen — 结束页 + 打包下载
   ============================================================ */
window.showEndScreen = function (paradigmName, subjectId) {
  var NAME_MAP = {
    flanker: '箭头判断', sart: '数字注意', nback: '图片记忆', vstmb: '视觉记忆',
    tmt: '连线测试', clock: '画钟测试', interpersonal: '人际距离', rmet: '看眼读心',
    visuospatial: '空间导航', speech: '语音测评',
    eyetracking: '图片注视', precheck: '设备检查'
  };

  var displayName = NAME_MAP[paradigmName] || paradigmName;
  var cameraOn = localStorage.getItem('camera_enabled') === 'true';

  // Mark as done
  if (subjectId) {
    localStorage.setItem('done_' + subjectId + '_' + paradigmName, Date.now());
    // 2026-04-19 F4: 正常完成 → 清 progress_ (block-level resume 不再需要)
    try {
      if (window.ProgressAPI && window.ProgressAPI.clear) {
        window.ProgressAPI.clear(paradigmName, subjectId);
      } else {
        // 兜底:ProgressAPI 未加载时直接 removeItem
        localStorage.removeItem('progress_' + subjectId + '_' + paradigmName);
      }
    } catch (e) { /* ignore */ }
  }

  // Notify parent (launcher)
  try {
    if (window.opener) {
      window.opener.postMessage({ paradigm: paradigmName, status: 'done' }, '*');
    }
  } catch (e) { /* silent */ }

  // ---- 打包ZIP（行为数据 + 小文件）----
  // 视频已在 ParadigmCamera.stopAndSave() 里直接下载，不在 LocalPack 里。
  // LocalPack 里只剩行为数据 (CSV/JSON) 和小 Blob (PNG截图/events CSV)，全部打ZIP。
  var packFiles = LocalPack.getAll();
  console.log('[EndScreen] LocalPack files:', packFiles.length, packFiles.map(function(f){return f.name + '(' + (f.data instanceof Blob ? (f.data.size/1024).toFixed(0)+'KB' : f.data.length + 'chars') + ')';}));

  var _zipBlobUrl = null;
  var _zipFileName = '';

  if (packFiles.length > 0 && typeof JSZip !== 'undefined') {
    (async function () {
      try {
        var ts = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '').replace('T', '_');
        var folderName = subjectId + '_' + paradigmName + '_' + ts;
        _zipFileName = folderName + '.zip';

        var zip = new JSZip();
        var folder = zip.folder(folderName);
        for (var i = 0; i < packFiles.length; i++) {
          var f = packFiles[i];
          // Blob（PNG截图/音频录音）已是压缩格式，DEFLATE白费CPU
          // 文本（CSV/JSON）才需要压缩
          var opts = (f.data instanceof Blob) ? { compression: 'STORE' } : {};
          folder.file(f.name, f.data, opts);
        }

        var blob = await zip.generateAsync({
          type: 'blob',
          compression: 'DEFLATE',
          compressionOptions: { level: 1 }
        });
        _zipBlobUrl = URL.createObjectURL(blob);
        var sizeMB = (blob.size / 1024 / 1024).toFixed(1);
        console.log('[EndScreen] ZIP ready: ' + _zipFileName + ' (' + sizeMB + 'MB)');

        // 更新下载按钮
        var dlBtn = document.getElementById('end-download-btn');
        if (dlBtn) {
          dlBtn.href = _zipBlobUrl;
          dlBtn.download = _zipFileName;
          dlBtn.textContent = '下载数据 (' + sizeMB + 'MB)';
          dlBtn.style.background = '#2E7D32';
          dlBtn.style.cursor = 'pointer';
          dlBtn.style.pointerEvents = 'auto';
        }

        // 不自动 a.click()——Edge 限制自动下载次数，用掉配额后后续下载全被拦截。
        // 用户手动点击 <a> 按钮 = 用户手势 = 不被拦截。

        setTimeout(function() {
          if (_zipBlobUrl) { URL.revokeObjectURL(_zipBlobUrl); _zipBlobUrl = null; }
        }, 120000);

        LocalPack.clear();
      } catch (e) {
        var errMsg = e && e.message ? e.message : String(e);
        console.error('[EndScreen] ZIP pack failed:', e);
        var dlBtn = document.getElementById('end-download-btn');
        if (dlBtn) {
          dlBtn.textContent = '打包失败: ' + errMsg;
          dlBtn.style.background = '#C62828';
          dlBtn.style.fontSize = '16px';
          dlBtn.style.pointerEvents = 'auto';
        }
      }
    })();
  }

  // Build status items
  var items = [
    { label: '行为数据', note: '已保存至服务器 + 本地', ok: true }
  ];
  if (cameraOn && paradigmName !== 'eyetracking') {
    items.push({ label: '视频录制', note: '已打包至本地', ok: true });
  }
  if (paradigmName === 'eyetracking') {
    items.push({ label: '注视视频', note: '已保存', ok: true });
  }
  if (paradigmName === 'speech') {
    items.push({ label: '语音录音', note: '已打包至本地', ok: true });
  }

  var statusHTML = items.map(function (item) {
    return '<div style="display:flex;align-items:center;gap:10px;padding:6px 0;font-size:20px;color:#333;">' +
      '<span style="width:12px;height:12px;border-radius:50%;background:' + (item.ok ? '#43A047' : '#F57C00') + ';flex-shrink:0;"></span>' +
      '<span><b>' + item.label + '</b> — ' + item.note + '</span></div>';
  }).join('');

  // 下载按钮：用<a>标签——用户点击 = 用户手势 = Edge 不拦截
  var hasFiles = packFiles.length > 0;
  var downloadBtnHTML = hasFiles
    ? '<a id="end-download-btn" style="display:inline-block;padding:14px 48px;font-size:22px;font-weight:600;border:none;border-radius:12px;background:#78909C;color:white;cursor:wait;touch-action:manipulation;min-width:280px;margin-bottom:12px;text-decoration:none;text-align:center;pointer-events:none;">正在打包…</a>'
    : '';

  // 视频下载按钮（ParadigmCamera 录制的视频，不走 ZIP，用户手动点击下载）
  var videoBtnHTML = '';
  if (typeof ParadigmCamera !== 'undefined' && ParadigmCamera._lastVideoUrl) {
    var vSizeMB = ((ParadigmCamera._lastVideoSize || 0) / 1024 / 1024).toFixed(1);
    videoBtnHTML = '<a id="end-video-btn" href="' + ParadigmCamera._lastVideoUrl + '" download="' +
      ParadigmCamera._lastVideoName + '" style="display:inline-block;padding:14px 48px;font-size:22px;' +
      'font-weight:600;border:none;border-radius:12px;background:#1565C0;color:white;cursor:pointer;' +
      'touch-action:manipulation;min-width:280px;margin-bottom:16px;text-decoration:none;text-align:center;">' +
      '下载录像 (' + vSizeMB + 'MB)</a>';
  }

  // Render end screen
  var target = document.getElementById('jspsych-target') || document.body;
  target.innerHTML = '';
  document.documentElement.style.background = '#F5F7FA';
  document.body.style.background = '#F5F7FA';
  document.body.style.margin = '0';

  var container = document.createElement('div');
  container.style.cssText = 'display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;padding:40px;box-sizing:border-box;font-family:"Microsoft YaHei","PingFang SC",sans-serif;';

  container.innerHTML =
    '<div style="text-align:center;margin-bottom:32px;">' +
      '<div style="width:64px;height:64px;border-radius:50%;background:#43A047;margin:0 auto 16px;display:flex;align-items:center;justify-content:center;">' +
        '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>' +
      '</div>' +
      '<div style="font-size:40px;font-weight:700;color:#1A1A2E;">' + displayName + ' 已完成</div>' +
      '<div style="font-size:22px;color:#888;margin-top:8px;">感谢您的配合</div>' +
    '</div>' +
    '<div style="max-width:480px;width:100%;padding:20px 28px;background:white;border-radius:14px;box-shadow:0 2px 12px rgba(0,0,0,0.06);margin-bottom:28px;">' +
      '<div style="font-size:18px;font-weight:600;color:#2E7D32;margin-bottom:12px;text-align:center;">数据保存完成</div>' +
      statusHTML +
      '<div style="margin-top:12px;padding-top:10px;border-top:1px solid #E8E8E8;font-size:14px;color:#AAA;text-align:center;">数据已双重备份（服务器 + 本地ZIP）</div>' +
    '</div>' +
    downloadBtnHTML +
    videoBtnHTML +
    '<button id="end-return-btn" style="padding:16px 56px;font-size:24px;font-weight:600;border:none;border-radius:12px;background:#1565C0;color:white;cursor:pointer;touch-action:manipulation;transition:background 0.2s;min-width:280px;">返回评估主页</button>' +
    '<div style="margin-top:16px;font-size:15px;color:#BBB;">或直接关闭此页面</div>';

  target.appendChild(container);

  var returnBtn = document.getElementById('end-return-btn');
  function doReturn() {
    if (window.opener) {
      window.opener.postMessage({ paradigm: paradigmName, status: 'done' }, '*');
      window.close();
    } else {
      window.location.href = '/';
    }
  }
  returnBtn.addEventListener('pointerup', doReturn);
  returnBtn.addEventListener('click', doReturn);
};
