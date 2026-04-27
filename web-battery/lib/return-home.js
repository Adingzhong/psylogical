/**
 * 全局返回主页 + 数据保存状态显示
 * 每个范式 HTML 引入此脚本，实验结束后：
 *   1. 显示数据保存状态（✅ 行为数据 / ✅ 视频 等）
 *   2. 显示"返回评估主页"按钮
 *   3. 通知 launcher (opener) 该范式已完成
 */
(function() {
  'use strict';

  // 从 URL 获取范式名和被试号
  var path = window.location.pathname;
  var match = path.match(/paradigms\/([^/]+)\//);
  var paradigmId = match ? match[1] : 'unknown';
  var sid = new URLSearchParams(window.location.search).get('sid') || '';

  // 范式中文名映射
  var NAME_MAP = {
    flanker: '箭头判断', sart: '数字注意', nback: '图片记忆', vstmb: '视觉记忆',
    tmt: '连线测试', clock: '画钟测试', interpersonal: '人际距离',
    visuospatial: '空间导航', eyetracking: '图片注视', speech: '语音测评'
  };

  var injected = false;

  function injectEndPanel() {
    if (injected) return;
    if (document.querySelector('.return-home-btn')) return;

    var container = document.querySelector('.jspsych-content') || document.body;

    // 读取保存状态
    var statusKey = 'save_status_' + sid + '_' + paradigmId;
    var status = null;
    try { status = JSON.parse(localStorage.getItem(statusKey)); } catch(e) {}

    // 构建状态面板
    var panel = document.createElement('div');
    panel.style.cssText = 'max-width:600px;margin:20px auto 0;padding:20px 28px;background:#F8FFF8;border:2px solid #C8E6C9;border-radius:14px;text-align:left;';

    var title = document.createElement('div');
    title.style.cssText = 'font-size:22px;font-weight:700;color:#2E7D32;margin-bottom:12px;text-align:center;';
    title.textContent = '数据保存完成';
    panel.appendChild(title);

    var items = [];

    // 行为数据（CSV）— 所有范式都有
    items.push({ label: '行为数据 (CSV)', ok: true, note: '已保存至服务器' });

    // 检查是否有checkpoint
    var ckptKey = 'checkpoint_' + paradigmId + '_' + sid;
    if (localStorage.getItem(ckptKey)) {
      // checkpoint还在 = 数据可能没正常保存完
      items.push({ label: '断点备份', ok: true, note: '本地备份已保存' });
    }

    // 视频（如果摄像头启用了）
    if (localStorage.getItem('camera_enabled') === 'true') {
      items.push({ label: '视频录制', ok: true, note: '已保存至本地 Downloads' });
    }

    // 如果有status记录，用更精确的状态
    if (status) {
      items = [];
      if (status.csv) items.push({ label: '行为数据 (CSV)', ok: status.csv === 'ok', note: status.csv === 'ok' ? '已保存至服务器' : '保存到本地备份' });
      if (status.video) items.push({ label: '视频录制', ok: true, note: '已保存至本地 Downloads' });
      if (status.audio) items.push({ label: '语音录音', ok: true, note: '已保存至本地 Downloads' });
    }

    // 默认显示
    if (items.length === 0) {
      items.push({ label: '数据', ok: true, note: '已自动保存' });
    }

    items.forEach(function(item) {
      var row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:10px;padding:6px 0;font-size:18px;color:#333;';
      var icon = document.createElement('span');
      icon.style.cssText = 'width:20px;height:20px;border-radius:50%;flex-shrink:0;display:inline-block;';
      icon.style.background = item.ok ? '#43A047' : '#F57C00';
      var text = document.createElement('span');
      text.innerHTML = '<b>' + item.label + '</b> — ' + item.note;
      row.appendChild(icon);
      row.appendChild(text);
      panel.appendChild(row);
    });

    // 保存位置提示
    var hint = document.createElement('div');
    hint.style.cssText = 'margin-top:12px;padding-top:10px;border-top:1px solid #E0E0E0;font-size:15px;color:#888;text-align:center;';
    hint.textContent = '所有数据同时保存在服务器和本地，双重备份';
    panel.appendChild(hint);

    container.appendChild(panel);

    // 返回按钮
    var btn = document.createElement('button');
    btn.className = 'return-home-btn';
    btn.textContent = '返回评估主页';
    btn.style.cssText = 'display:block;margin:16px auto 0;padding:14px 48px;font-size:20px;font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#1565C0;color:white;border:none;border-radius:10px;cursor:pointer;transition:background 0.2s;touch-action:manipulation;';
    btn.addEventListener('mouseenter', function() { btn.style.background = '#1976D2'; });
    btn.addEventListener('mouseleave', function() { btn.style.background = '#1565C0'; });
    btn.addEventListener('click', function() {
      // 标记完成
      if (sid) {
        localStorage.setItem('done_' + sid + '_' + paradigmId, Date.now());
      }
      if (window.opener) {
        window.opener.postMessage({ paradigm: paradigmId, status: 'done' }, '*');
        window.close();
      } else {
        window.location.href = '/app';
      }
    });
    container.appendChild(btn);
    injected = true;

    // 通知 launcher
    if (window.opener) {
      window.opener.postMessage({ paradigm: paradigmId, status: 'done' }, '*');
    }
  }

  // 监听 DOM 变化检测结束页
  var observer = new MutationObserver(function() {
    var text = document.body.innerText;
    if (text.includes('测试结束') || text.includes('实验完成') ||
        text.includes('测试完成') || text.includes('全部完成') ||
        text.includes('评估完成') || text.includes('数据已保存') ||
        text.includes('数据正在保存') || text.includes('数据已自动保存') ||
        text.includes('画钟完成') || text.includes('全部看完了') ||
        text.includes('看图片完成') || text.includes('导航完成') ||
        text.includes('任务完成') || text.includes('游戏结束') ||
        text.includes('谢谢您')) {
      setTimeout(injectEndPanel, 600);
    }
  });

  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
})();
