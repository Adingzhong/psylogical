/**
 * touch-hardening.js — 老年触屏适配模块 v2.0
 *
 * 解决 Surface 平板老年人施测中的触屏问题:
 *   1. 长按弹出系统菜单  → contextmenu 全局阻止
 *   2. 按住不放不被识别   → pointerdown/pointerup 替代 click, 容忍长按+漂移
 *   3. 手指漂移导致滚动   → touch-action:none + overscroll-behavior
 *   4. 按键反馈太弱      → pointerdown 立即变色, pointerup 确认闪烁
 *   5. RT 应在按下时记录  → pointerdown 记录时间, hold 时长单独保存
 *   6. 一手搭屏一手点    → html,body touch-action:none 防止双指缩放
 *   7. 漂移距离记录      → pointermove 追踪运动轨迹 (运动功能指标)
 *   8. 重复点击记录      → tap_count 计数, 第一次记RT后续只计数
 *   9. 输入类型记录      → e.pointerType 区分 touch/pen/mouse
 *
 * 用法:
 *   HTML: <script src="../../lib/touch-hardening.js"></script>
 *   自动初始化, 自动包装 jsPsych 按钮.
 *
 *   自定义按钮:
 *     TouchHardening.setupButton(el, function(e) { ... });
 *
 *   RT 校正 (在 jsPsych trial 的 on_finish 中):
 *     on_finish: function(data) { TouchHardening.correctRT(data); }
 *
 * 设计原则:
 *   - 仅拦截 touch/pen 输入, 鼠标走原生 click 路径 (开发调试不受影响)
 *   - RT = pointerdown 时刻 (认知心理学标准, Bjorklund 1991; Kay 2013 PVT-Touch)
 *   - 漂移容忍 50px ≈ 9.5mm (覆盖老年人95%漂移, Elboim-Gabyzon 2021)
 *   - 防抖 400ms (工信部适老化规范 2021)
 *   - 视觉反馈 <100ms (Nielsen Norman Group 标准)
 *   - Hold time 作为运动功能指标 (Park 2024 MCI AUC=.847; neuroQWERTY FDA突破性设备)
 *   - Drift path/max 区分震颤与漂移 (Iakovakis 2018 touchscreen PD AUC=0.92)
 *
 * 参考:
 *   - 工信部 APP 适老化通用设计规范 (2021)
 *   - Chung et al. (2021) PMC7924826 — TATOO 老年触屏数据
 *   - Bjorklund (1991) — key-press vs key-release RT
 *   - Kay et al. (2013) PVT-Touch — touch-down 等价物理按键
 *   - Park (2024) PMC11561447 — 击键动力学检测MCI
 *   - Iakovakis et al. (2018) — 触屏打字检测帕金森
 *   - WCAG 2.2 SC 2.5.8 — touch target size
 */

(function () {
  'use strict';

  /* ================================================================
     配置
     ================================================================ */
  var CONFIG = {
    MAX_DRIFT_PX: 50,       // 漂移容忍 (px) — 老年人平均漂移8-12mm≈42-63px on Surface
    MAX_HOLD_MS: 10000,     // 最大按住时长 (ms)
    DEBOUNCE_MS: 400,       // 防抖间隔 (ms)
    CONFIRM_FLASH_MS: 300,  // 确认闪烁时长 (ms)
    SOUND_ENABLED: false    // 音效反馈 (默认关闭, 多人施测避免干扰)
  };

  /* ================================================================
     全局状态
     ================================================================ */
  // { downTime, upTime, startX, startY, driftMaxSq, driftPath, lastX, lastY,
  //   tapCount, inputType, driftEndX, driftEndY }
  window.__touchRT = null;
  var _lastResponseTime = 0; // 防抖时间戳

  /* ================================================================
     1. 全局触摸防护
     ================================================================ */
  function initTouchProtection() {
    // 1a. 阻止长按上下文菜单
    document.addEventListener('contextmenu', function (e) {
      e.preventDefault();
    });

    // 1b. 多指触控：不阻止第二个触点
    // 老人一手搭屏、另一手点按钮的场景需要允许多触点
    // 双指缩放通过 html,body touch-action:none 阻止，不需要事件级拦截
    // pointer events 的 pointerId 机制天然隔离各手指的事件流

    // 1c. 阻止双击缩放 (300ms 内二次 touchend)
    var lastTouchEnd = 0;
    document.addEventListener('touchend', function (e) {
      var now = Date.now();
      if (now - lastTouchEnd <= 300) e.preventDefault();
      lastTouchEnd = now;
    }, false);

    // 1d. 阻止 Ctrl+滚轮 缩放
    document.addEventListener('wheel', function (e) {
      if (e.ctrlKey) e.preventDefault();
    }, { passive: false });

    // 1e. 注入加固 CSS
    var style = document.createElement('style');
    style.id = 'touch-hardening-css';
    style.textContent =
      /* 全局: 禁止所有浏览器手势(pan/zoom/pinch)、长按弹出、overscroll弹性 */
      /* touch-action:none 在文档根级别 — 不管手指在哪个元素上都不会触发缩放 */
      /* 解决: 左手搭屏+右手按按钮 → 浏览器把两指理解为pinch → 页面缩放+按钮失效 */
      'html, body {\n' +
      '  touch-action: none !important;\n' +
      '  -webkit-touch-callout: none !important;\n' +
      '  overscroll-behavior: none !important;\n' +
      '}\n' +
      '\n' +
      /* 所有按钮: 冗余保护 (html,body 已经 none, 这里是防御性编程) */
      'button, .jspsych-btn, .response-btn, .vstmb-btn,\n' +
      '.sart-tap-btn, .rating-btn, [role="button"] {\n' +
      '  touch-action: none !important;\n' +
      '}\n' +
      '\n' +
      /* 按下状态 — pointerdown 立即添加 */
      '.elderly-pressing {\n' +
      '  opacity: 0.80 !important;\n' +
      '  transform: scale(0.92) !important;\n' +
      '  transition: opacity 0.06s, transform 0.06s !important;\n' +
      '}\n' +
      '\n' +
      /* 确认高亮 — pointerup 后短暂白色边框（适配黑底和白底） */
      '.elderly-confirmed {\n' +
      '  box-shadow: 0 0 0 4px rgba(255,255,255,0.7), 0 0 12px rgba(255,255,255,0.3) !important;\n' +
      '  transition: box-shadow 0.08s !important;\n' +
      '}\n' +
      '\n' +
      /* 触摸设备: 禁止 hover 粘滞 (jsPsych issue #977) */
      '@media (hover: none) {\n' +
      '  .jspsych-btn:hover, .response-btn:hover,\n' +
      '  .vstmb-btn:hover, .sart-tap-btn:hover {\n' +
      '    filter: none !important;\n' +
      '  }\n' +
      '}\n';
    document.head.appendChild(style);

    // 1f. 强化 viewport meta (防止双指缩放)
    var vp = document.querySelector('meta[name="viewport"]');
    if (vp) {
      var content = vp.getAttribute('content') || '';
      if (content.indexOf('maximum-scale') === -1) {
        vp.setAttribute('content', content + ', maximum-scale=1.0');
      }
    }
  }

  /* ================================================================
     2. jsPsych 按钮自动包装 (MutationObserver)
     ================================================================ */
  function autoWrapJsPsychButtons() {
    var observer = new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i++) {
        var added = mutations[i].addedNodes;
        for (var j = 0; j < added.length; j++) {
          var node = added[j];
          if (node.nodeType !== 1) continue;
          // 直接就是 btngroup
          if (node.id === 'jspsych-html-button-response-btngroup' ||
              node.id === 'jspsych-image-button-response-btngroup') {
            wrapButtonGroup(node);
          }
          // 或者子树里包含 btngroup
          if (node.querySelectorAll) {
            var groups = node.querySelectorAll(
              '#jspsych-html-button-response-btngroup, #jspsych-image-button-response-btngroup'
            );
            for (var k = 0; k < groups.length; k++) wrapButtonGroup(groups[k]);
          }
        }
      }
    });
    observer.observe(document.body || document.documentElement, {
      childList: true, subtree: true
    });
  }

  function wrapButtonGroup(group) {
    var buttons = group.querySelectorAll('button');
    for (var i = 0; i < buttons.length; i++) {
      wrapJsPsychButton(buttons[i]);
    }
  }

  /**
   * 包装单个 jsPsych 按钮
   *  - 有 data-choice 属性 → 试次响应按钮 → 记录 RT + 防抖
   *  - 无 data-choice      → 指导语 "继续" 按钮 → 不记录 RT, 不防抖
   *
   * Ghost-click 防护 (2026-04-19 加):
   *   上一个 trial pointerup 后 Surface Edge 会在 ~300ms 合成 phantom click,
   *   落到刚渲染的新 trial 指导语按钮 → 指导语被穿透跳过。
   *   修法:按钮被 wrap 起(≈ DOM 刚插入)的前 700ms 内,只放行"刚 pointerdown 触发的 click",
   *   拦截其他来源的 click (phantom synth click 没有前置 pointerdown)。
   */
  function wrapJsPsychButton(btn) {
    if (btn.dataset.elderlyWrapped) return;
    btn.dataset.elderlyWrapped = 'true';

    var isResponseBtn = btn.dataset.choice !== undefined;
    var startX, startY, startTime, pointerId;
    var isActive = false;
    // v2: 漂移追踪
    var driftMaxSq = 0, driftPath = 0, lastMoveX = 0, lastMoveY = 0;

    // Ghost-click shield 状态
    var wrapTime = Date.now();
    var GHOST_CLICK_SHIELD_MS = 700;
    var _lastPointerAt = 0;  // 最近一次 pointerdown 在本按钮发生的时间

    // click 事件 shield — capture 阶段先于 jsPsych handler
    btn.addEventListener('click', function (e) {
      // 真实触摸/鼠标点击: pointerdown handler 刚跑过,_lastPointerAt 在 100ms 内 → 放行
      if (Date.now() - _lastPointerAt < 100) return;
      // 超过 shield 窗口(按钮已渲染 > 700ms): phantom click 也放行(正常操作阶段)
      if (Date.now() - wrapTime >= GHOST_CLICK_SHIELD_MS) return;
      // 在 shield 窗口内,且无对应 pointerdown → 就是 phantom synth click,拦
      e.stopImmediatePropagation();
      e.preventDefault();
    }, true);

    btn.addEventListener('pointerdown', function (e) {
      _lastPointerAt = Date.now();  // 任何 pointerdown(含 mouse)都算真实输入
      // 仅拦截 touch/pen, 鼠标走原生 click
      if (!e.isPrimary || e.pointerType === 'mouse') return;
      if (btn.disabled || btn.getAttribute('disabled') !== null) return;

      // 响应按钮防抖
      if (isResponseBtn) {
        var now = Date.now();
        if (now - _lastResponseTime < CONFIG.DEBOUNCE_MS) return;
      }

      isActive = true;
      pointerId = e.pointerId;
      startX = e.clientX;
      startY = e.clientY;
      startTime = Date.now();
      // v2: 重置漂移追踪
      driftMaxSq = 0;
      driftPath = 0;
      lastMoveX = e.clientX;
      lastMoveY = e.clientY;

      // RT 记录 (仅响应按钮)
      if (isResponseBtn) {
        if (!window.__touchRT || window.__touchRT.responded) {
          // 首次按下，或上一次已响应 → 新建记录
          window.__touchRT = {
            downTime: performance.now(), upTime: null,
            startX: e.clientX, startY: e.clientY,
            driftMaxSq: 0, driftPath: 0, lastX: e.clientX, lastY: e.clientY,
            driftEndX: e.clientX, driftEndY: e.clientY,
            tapCount: 1, inputType: e.pointerType, responded: false
          };
        } else {
          // 已有记录但未响应（不应发生在auto-wrap中，但防御性处理）
          window.__touchRT.tapCount = (window.__touchRT.tapCount || 1) + 1;
        }
      }

      try { btn.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
      btn.classList.add('elderly-pressing');
      btn.classList.remove('elderly-confirmed');
    });

    // v2: 漂移追踪
    btn.addEventListener('pointermove', function (e) {
      if (!isActive || e.pointerId !== pointerId) return;

      // 更新漂移数据
      var dx = e.clientX - startX;
      var dy = e.clientY - startY;
      var distSq = dx * dx + dy * dy;
      if (distSq > driftMaxSq) driftMaxSq = distSq;
      driftPath += Math.sqrt(
        Math.pow(e.clientX - lastMoveX, 2) + Math.pow(e.clientY - lastMoveY, 2)
      );
      lastMoveX = e.clientX;
      lastMoveY = e.clientY;

      // 同步到全局状态
      if (window.__touchRT && !window.__touchRT.responded) {
        window.__touchRT.driftMaxSq = driftMaxSq;
        window.__touchRT.driftPath = driftPath;
        window.__touchRT.lastX = e.clientX;
        window.__touchRT.lastY = e.clientY;
      }
    });

    btn.addEventListener('pointerup', function (e) {
      if (!isActive || e.pointerId !== pointerId) return;
      isActive = false;
      btn.classList.remove('elderly-pressing');

      if (e.pointerType === 'mouse') return; // 鼠标走原生

      var elapsed = Date.now() - startTime;
      var dx = Math.abs(e.clientX - startX);
      var dy = Math.abs(e.clientY - startY);
      var drift = Math.sqrt(dx * dx + dy * dy);

      if (elapsed <= CONFIG.MAX_HOLD_MS && drift <= CONFIG.MAX_DRIFT_PX) {
        // 记录 upTime + 漂移终点
        if (isResponseBtn && window.__touchRT) {
          window.__touchRT.upTime = performance.now();
          window.__touchRT.driftEndX = e.clientX;
          window.__touchRT.driftEndY = e.clientY;
          window.__touchRT.responded = true;
        }
        if (isResponseBtn) {
          _lastResponseTime = Date.now();
        }

        // 确认闪烁
        btn.classList.add('elderly-confirmed');
        setTimeout(function () { btn.classList.remove('elderly-confirmed'); }, CONFIG.CONFIRM_FLASH_MS);

        // 触发 click → jsPsych 响应处理器
        btn.click();
      }
      // 不满足条件 → 忽略 (老人手指滑走了)
    });

    btn.addEventListener('pointercancel', function () {
      isActive = false;
      btn.classList.remove('elderly-pressing');
    });
  }

  /* ================================================================
     3. 自定义按钮包装 (N-back/人际距离等范式自建按钮)
     ================================================================ */

  /**
   * 将自定义按钮改造为老年友好触摸按钮
   *
   * @param {HTMLElement} element    按钮元素
   * @param {Function}    callback   有效按压后的回调 (接收 PointerEvent)
   * @param {Object}      [opts]
   * @param {boolean}     [opts.trackRT=true]       是否记录 RT
   * @param {boolean}     [opts.debounce=true]      是否防抖
   * @param {boolean}     [opts.confirmFlash=true]   确认闪烁
   * @param {boolean}     [opts.mouseAlso=false]     是否也拦截鼠标 (默认否)
   */
  function setupButton(element, callback, opts) {
    opts = Object.assign(
      { trackRT: true, debounce: true, confirmFlash: true, mouseAlso: false },
      opts || {}
    );

    var startX, startY, startTime, pointerId;
    var isActive = false;
    // v2: 漂移追踪
    var driftMaxSq = 0, driftPath = 0, lastMoveX = 0, lastMoveY = 0;

    // Ghost-click shield (2026-04-19): 防止 Surface Edge 前一个 trial 的
    // synth click 落到本按钮。pinpoint:isTrusted + 无前置 pointerdown
    var wrapTime = Date.now();
    var GHOST_CLICK_SHIELD_MS = 700;
    var _lastPointerAt = 0;

    element.addEventListener('click', function (e) {
      if (!e.isTrusted) return;                                    // 程序 .click() 调用,放行
      if (Date.now() - _lastPointerAt < 100) return;               // 刚 pointerdown 过(真实触摸/鼠标)
      if (Date.now() - wrapTime >= GHOST_CLICK_SHIELD_MS) return;  // shield 过期
      // shield 窗口内,无对应 pointerdown → phantom synth click,拦
      e.stopImmediatePropagation();
      e.preventDefault();
    }, true);

    element.addEventListener('contextmenu', function (e) { e.preventDefault(); });

    element.addEventListener('pointerdown', function (e) {
      _lastPointerAt = Date.now();
      if (!e.isPrimary) return;
      if (!opts.mouseAlso && e.pointerType === 'mouse') return;

      if (opts.debounce) {
        var now = Date.now();
        if (now - _lastResponseTime < CONFIG.DEBOUNCE_MS) return;
      }

      isActive = true;
      pointerId = e.pointerId;
      startX = e.clientX;
      startY = e.clientY;
      startTime = Date.now();
      // v2: 重置漂移
      driftMaxSq = 0;
      driftPath = 0;
      lastMoveX = e.clientX;
      lastMoveY = e.clientY;

      if (opts.trackRT) {
        if (!window.__touchRT || window.__touchRT.responded) {
          window.__touchRT = {
            downTime: performance.now(), upTime: null,
            startX: e.clientX, startY: e.clientY,
            driftMaxSq: 0, driftPath: 0, lastX: e.clientX, lastY: e.clientY,
            driftEndX: e.clientX, driftEndY: e.clientY,
            tapCount: 1, inputType: e.pointerType, responded: false
          };
        } else {
          window.__touchRT.tapCount = (window.__touchRT.tapCount || 1) + 1;
        }
      }

      try { element.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
      element.classList.add('elderly-pressing');
      element.classList.remove('elderly-confirmed');
    });

    // v2: 漂移追踪
    element.addEventListener('pointermove', function (e) {
      if (!isActive || e.pointerId !== pointerId) return;

      var dx = e.clientX - startX;
      var dy = e.clientY - startY;
      var distSq = dx * dx + dy * dy;
      if (distSq > driftMaxSq) driftMaxSq = distSq;
      driftPath += Math.sqrt(
        Math.pow(e.clientX - lastMoveX, 2) + Math.pow(e.clientY - lastMoveY, 2)
      );
      lastMoveX = e.clientX;
      lastMoveY = e.clientY;

      if (opts.trackRT && window.__touchRT && !window.__touchRT.responded) {
        window.__touchRT.driftMaxSq = driftMaxSq;
        window.__touchRT.driftPath = driftPath;
        window.__touchRT.lastX = e.clientX;
        window.__touchRT.lastY = e.clientY;
      }
    });

    element.addEventListener('pointerup', function (e) {
      if (!isActive || e.pointerId !== pointerId) return;
      isActive = false;
      element.classList.remove('elderly-pressing');

      if (!opts.mouseAlso && e.pointerType === 'mouse') return;

      var elapsed = Date.now() - startTime;
      var dx = Math.abs(e.clientX - startX);
      var dy = Math.abs(e.clientY - startY);
      var drift = Math.sqrt(dx * dx + dy * dy);

      if (elapsed <= CONFIG.MAX_HOLD_MS && drift <= CONFIG.MAX_DRIFT_PX) {
        if (opts.trackRT && window.__touchRT) {
          window.__touchRT.upTime = performance.now();
          window.__touchRT.driftEndX = e.clientX;
          window.__touchRT.driftEndY = e.clientY;
          window.__touchRT.responded = true;
        }
        if (opts.debounce) {
          _lastResponseTime = Date.now();
        }
        if (opts.confirmFlash) {
          element.classList.add('elderly-confirmed');
          setTimeout(function () { element.classList.remove('elderly-confirmed'); }, CONFIG.CONFIRM_FLASH_MS);
        }
        callback(e);
      }
    });

    element.addEventListener('pointercancel', function () {
      isActive = false;
      element.classList.remove('elderly-pressing');
    });
  }

  /* ================================================================
     4. RT 校正工具
     ================================================================ */

  /**
   * 在 jsPsych trial 的 on_finish 中调用, 将 RT 校正为 pointerdown 时刻,
   * 并输出运动功能指标.
   *
   * jsPsych 默认在 click 事件 (≈pointerup) 时记录 RT, 这包含了老人的
   * 按住时长. 此函数将 RT 修正为 pointerdown 时刻, 并保存按住时长和
   * 漂移指标作为独立的运动功能指标.
   *
   * 校正后的 data 字段:
   *   rt              — 校正后 RT (pointerdown 时刻, 认知决策时间)
   *   rt_original     — 原始 RT (click 时刻)
   *   rt_hold         — 按住时长 ms (pointerup - pointerdown)
   *   drift_max       — 按压期间离初始触点最大位移 (px)
   *   drift_path      — 手指运动轨迹总长 (px)
   *   drift_end       — 松手时离起点距离 (px)
   *   tap_count       — 本试次内点击次数 (含首次, ≥1)
   *   input_type      — 输入类型: 'touch' / 'pen' / 'mouse'
   *
   * 运动功能派生指标 (分析时计算):
   *   precision_index = drift_path / rt_hold  — 高=不稳
   *   tremor_ratio    = drift_path / drift_max — 远>1 提示震颤
   *
   * @param {Object} data  jsPsych trial data 对象
   */
  function correctRT(data) {
    if (!window.__touchRT) return;
    var t = window.__touchRT;

    // RT 校正 (仅在有完整 down+up 数据时)
    if (t.downTime != null && t.upTime != null && data.rt != null) {
      var holdDuration = Math.round(t.upTime - t.downTime);
      data.rt_original = data.rt;
      data.rt_hold = holdDuration;
      data.rt = Math.max(0, data.rt - holdDuration);
    }

    // v2: 漂移指标 (无论RT是否校正都输出)
    if (t.startX != null) {
      data.drift_max = Math.round(Math.sqrt(t.driftMaxSq || 0));
      data.drift_path = Math.round(t.driftPath || 0);
      var dEndX = (t.driftEndX || t.startX) - t.startX;
      var dEndY = (t.driftEndY || t.startY) - t.startY;
      data.drift_end = Math.round(Math.sqrt(dEndX * dEndX + dEndY * dEndY));
    }

    // v2: 点击次数和输入类型
    data.tap_count = t.tapCount || 1;
    data.input_type = t.inputType || null;

    window.__touchRT = null;
  }

  /* ================================================================
     5. 三指双击退出（施测人员专用）
     ================================================================ */

  /**
   * 三根手指在 500ms 内拍两下 → 弹出暂停确认框
   * 老人不会做这个动作，只有施测人员知道。
   * 退出时保存当前数据（通过 saveData / checkpoint），回到启动器。
   */
  function initTripleTapExit() {
    var lastTripleTapTime = 0;
    var DOUBLE_TAP_WINDOW = 500; // ms

    document.addEventListener('touchstart', function (e) {
      if (e.touches.length < 3) return; // 不是三指，忽略

      var now = Date.now();
      if (now - lastTripleTapTime < DOUBLE_TAP_WINDOW) {
        // 第二次三指触摸 → 触发退出流程
        lastTripleTapTime = 0;
        e.preventDefault();
        showExitDialog();
      } else {
        // 第一次三指触摸 → 记录时间
        lastTripleTapTime = now;
      }
    }, { passive: false });
  }

  function showExitDialog() {
    // 如果已有弹窗，不重复
    if (document.getElementById('_exit_overlay')) return;

    var overlay = document.createElement('div');
    overlay.id = '_exit_overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:99999;display:flex;align-items:center;justify-content:center;';

    var box = document.createElement('div');
    box.style.cssText = 'background:white;border-radius:16px;padding:40px;text-align:center;max-width:480px;width:90%;font-family:"PingFang SC","Microsoft YaHei",sans-serif;';
    box.innerHTML =
      '<div style="font-size:36px;font-weight:bold;color:#1A1A2E;margin-bottom:12px;">主试操作面板</div>' +
      '<div style="font-size:22px;color:#888;margin-bottom:20px;line-height:1.6;">' +
        '当前范式无法暂停，退出后需<b>重新完成本范式</b>。<br>' +
        '已完成的其他范式不受影响。' +
      '</div>' +
      '<div style="background:#FFF8E1;border-radius:10px;padding:14px 20px;margin-bottom:24px;font-size:20px;color:#E65100;line-height:1.5;">' +
        '提示：如需短暂休息，可直接关闭此面板让被试继续。<br>仅在确需中断时选择"退出"。' +
      '</div>' +
      '<div style="display:flex;gap:20px;justify-content:center;">' +
        '<button id="_exit_resume" style="padding:16px 48px;font-size:24px;font-weight:600;border:2px solid #E0E0E0;border-radius:12px;background:#F5F5F5;color:#333;cursor:pointer;min-width:160px;">关闭面板</button>' +
        '<button id="_exit_quit" style="padding:16px 48px;font-size:24px;font-weight:600;border:none;border-radius:12px;background:#D32F2F;color:white;cursor:pointer;min-width:160px;">退出本范式</button>' +
      '</div>';

    overlay.appendChild(box);
    document.body.appendChild(overlay);

    document.getElementById('_exit_resume').addEventListener('click', function () {
      overlay.remove();
    });

    document.getElementById('_exit_quit').addEventListener('click', function () {
      overlay.remove();
      // 尝试强制保存 checkpoint
      try {
        if (window._checkpoint && window._checkpoint.forceSave) window._checkpoint.forceSave();
        if (window._ckpt && window._ckpt.forceSave) window._ckpt.forceSave();
      } catch (e) { /* best-effort */ }

      // 2026-04-19 F4: 如果范式声明了 __paradigmName + __subjectId,写 progress 让 launcher 显示"进行中"
      // 只改 updatedAt,lastCompletedBlockIdx 保持不动(当前 block 未完)
      // 如果范式未做 F4 改造(未声明 __paradigmName),整段 skip — 保留老行为
      try {
        if (window.ProgressAPI && window.__paradigmName && window.__subjectId) {
          // 判断是否值得写 progress:只在有过 block 完成的情况下(currentBlockIdx > 0)
          // 否则写一个 lastCompletedBlockIdx=-1 的"刚开始就退"标记(launcher 不显示 partial)
          var curBlock = typeof window.__currentBlockIdx === 'number' ? window.__currentBlockIdx : 0;
          window.ProgressAPI.write(window.__paradigmName, window.__subjectId, {
            totalBlocks: window.__totalBlocks || null,
            blockOrder: window.__blockOrder || null,
            balance: window.__balance || null,
            paradigmState: window.__paradigmState || null,
            // 注意: lastCompletedBlockIdx 不动 — writeProgressTrial 在 block 末已写过
            // 这里只是刷新 updatedAt
          });

          if (window.opener) {
            try {
              window.opener.postMessage({
                paradigm: window.__paradigmName,
                status: 'partial',
                lastBlock: curBlock - 1,
              }, '*');
            } catch (e) { /* ignore */ }
          }
        }
      } catch (e) { /* best-effort,不影响退出 */ }

      // 回到启动器
      if (window.opener) {
        window.close();
      } else {
        window.location.href = '/';
      }
    });
  }

  /* ================================================================
     6. 资源加载失败全局监听 (2026-04-19)
     ================================================================ */
  // 捕获阶段监听 window error — <img>/<audio>/<script> 加载失败会 fire
  // 用户诉求:范式开始做题前,主试要能知道有资源加载失败(避免老人看破图乱答)
  var _loadFailures = [];
  function initLoadFailureWatch() {
    window.addEventListener('error', function (e) {
      var tgt = e.target;
      if (!tgt || tgt === window) return;
      var tag = tgt.tagName;
      if (tag !== 'IMG' && tag !== 'AUDIO' && tag !== 'VIDEO' && tag !== 'SOURCE') return;
      var url = tgt.src || tgt.currentSrc;
      if (!url) return;
      // 忽略我们自己造的 blob URL (结束页 ZIP 下载等)
      if (url.indexOf('blob:') === 0) return;
      _loadFailures.push({ url: url, tag: tag, time: Date.now() });
    }, true);  // capture phase
  }

  /**
   * 检查当前累积的加载失败数,多于阈值弹框告警主试.
   * 各范式在 jsPsychPreload 之后调用一次.
   * @param {Object} [opts]
   * @param {number} [opts.threshold=0]   超过阈值才告警
   * @param {string} [opts.paradigmName]  弹框里显示的范式名
   * @returns {Promise<'continue'|'restart'>}
   */
  function checkLoadFailures(opts) {
    opts = opts || {};
    var threshold = opts.threshold || 0;
    var name = opts.paradigmName || '本范式';
    if (_loadFailures.length <= threshold) return Promise.resolve('continue');
    return new Promise(function (resolve) {
      var count = _loadFailures.length;
      // 最多列 5 条供主试判断,避免遮挡屏幕
      var preview = _loadFailures.slice(0, 5).map(function (f) {
        var short = f.url.split('/').pop();
        return '<div style="font-size:13px;color:#999;font-family:monospace;margin:2px 0;">• ' + short + '</div>';
      }).join('');
      var more = count > 5 ? '<div style="font-size:13px;color:#BBB;margin-top:4px;">... 还有 ' + (count - 5) + ' 个</div>' : '';

      var overlay = document.createElement('div');
      overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.72);z-index:99998;display:flex;align-items:center;justify-content:center;font-family:"PingFang SC","Microsoft YaHei",sans-serif;';
      overlay.innerHTML =
        '<div style="background:white;border-radius:16px;padding:36px;text-align:center;max-width:620px;width:92%;">' +
          '<div style="font-size:30px;font-weight:bold;color:#E65100;margin-bottom:12px;">资源加载异常</div>' +
          '<div style="font-size:20px;color:#555;margin-bottom:20px;line-height:1.6;">' +
            name + ' 预加载阶段有 <b style="color:#C62828;">' + count + '</b> 个文件失败<br>' +
            '<span style="font-size:16px;color:#888;">(图片/音频)</span>' +
          '</div>' +
          '<div style="background:#FAFAFA;border-radius:8px;padding:10px 14px;margin-bottom:18px;text-align:left;max-height:160px;overflow-y:auto;">' +
            preview + more +
          '</div>' +
          '<div style="background:#FFF8E1;border-radius:8px;padding:12px 18px;margin-bottom:20px;font-size:17px;color:#E65100;line-height:1.5;">' +
            '老人可能看到破图/听不到指导语。<br>建议<b>重开</b>范式让资源重新加载。' +
          '</div>' +
          '<div style="display:flex;gap:16px;justify-content:center;">' +
            '<button id="_lfRestart" style="padding:16px 40px;font-size:22px;font-weight:600;border:none;border-radius:12px;background:#43A047;color:white;cursor:pointer;min-width:150px;">重开范式</button>' +
            '<button id="_lfContinue" style="padding:16px 40px;font-size:18px;font-weight:600;border:2px solid #E0E0E0;border-radius:12px;background:#F5F5F5;color:#666;cursor:pointer;min-width:150px;">继续(有风险)</button>' +
          '</div>' +
        '</div>';
      document.body.appendChild(overlay);
      document.getElementById('_lfRestart').addEventListener('click', function () {
        overlay.remove();
        // 刷新当前页面 — 让 SW 重新拉资源
        window.location.reload();
        resolve('restart');
      });
      document.getElementById('_lfContinue').addEventListener('click', function () {
        overlay.remove();
        resolve('continue');
      });
    });
  }

  function clearLoadFailures() { _loadFailures.length = 0; }
  function getLoadFailures() { return _loadFailures.slice(); }

  /* ================================================================
     7. 初始化
     ================================================================ */
  function init() {
    initTouchProtection();
    autoWrapJsPsychButtons();
    initTripleTapExit();
    initLoadFailureWatch();
    console.log('[TouchHardening] v2.0 initialized — elderly touch adaptation active');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  /* ================================================================
     导出
     ================================================================ */
  window.TouchHardening = {
    setupButton: setupButton,
    correctRT: correctRT,
    showExitDialog: showExitDialog,
    CONFIG: CONFIG,
    // 资源加载失败追踪(2026-04-19)
    checkLoadFailures: checkLoadFailures,
    clearLoadFailures: clearLoadFailures,
    getLoadFailures: getLoadFailures,
  };

})();
