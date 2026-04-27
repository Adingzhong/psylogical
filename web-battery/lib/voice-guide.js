/**
 * VoiceGuide v4 — 统一 step-by-step + 可静音版 (2026-04-23)
 *
 * 交互合并:
 *   - 每步独立呈现红框 + 字幕,进入时自动播放音频(若未静音)
 *   - 底部三按钮: [上一步] [再听一遍] [下一步 N/M]
 *   - 最后一步"下一步"变为 buttonText(默认"开始练习")
 *   - 左上 "静音 / 开声音" 开关,状态持久化到 localStorage.voice_muted
 *   - 主试模式 (tester_mode): 右上显示 "跳过 (Esc)"
 *
 * 兼容:
 *   - localStorage.student_mode = '1' 或 ?student=1 → 初始静音(语义承接旧"学生模式")
 *   - URL ?mute=1 / ?mute=0 覆盖所有设置
 *   - btnRegion 仍覆盖图上的"开始练习"按钮,中间步临时显示"下一步"
 *   - 范式传参 API 不变: { image, steps, btnRegion, buttonText, pauseBetween }
 */
const VoiceGuide = (() => {
  'use strict';

  /* ---- Audio cache: 预创建 Audio 对象,避免每次 new Audio() 的磁盘 I/O 卡顿 ---- */
  const _audioCache = {};

  function _ensureCached(src) {
    if (!src) return;
    if (_audioCache[src]) return;
    const a = new Audio();
    a.preload = 'auto';
    a.src = src;
    _audioCache[src] = a;
  }

  function _precacheSteps(steps) {
    if (!steps) return;
    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      const lines = step.lines
        ? step.lines.map(l => typeof l === 'string' ? { subtitle: l } : l)
        : [{ audio: step.audio, subtitle: step.subtitle || '' }];
      for (let j = 0; j < lines.length; j++) {
        if (lines[j].audio) _ensureCached(lines[j].audio);
      }
    }
  }

  const STYLE_ID = 'voice-guide-style';
  function injectCSS() {
    if (document.getElementById(STYLE_ID)) return;
    const s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent = `
      .vg-overlay {
        position:fixed;inset:0;z-index:9000;background:#F0F2F5;
        display:flex;flex-direction:column;align-items:center;justify-content:center;
        padding:12px;gap:10px;
      }
      .vg-img-wrap { position:relative; }
      .vg-img-wrap img {
        max-width:94vw;max-height:76vh;object-fit:contain;border-radius:10px;
        box-shadow:0 2px 16px rgba(0,0,0,0.08);user-select:none;-webkit-user-drag:none;
      }
      .vg-highlight {
        position:absolute;border:3.5px solid #E53935;border-radius:6px;pointer-events:none;
        opacity:0;transition:left .35s ease,top .35s ease,width .35s ease,height .35s ease,opacity .25s;
        box-shadow:0 0 0 3px rgba(229,57,53,0.13);
      }
      .vg-highlight.active { opacity:1; }
      .vg-subtitle {
        width:94vw;max-width:1400px;min-height:48px;margin:0;padding:10px 28px;
        background:rgba(255,255,255,0.95);border-radius:10px;
        font-size:31px;line-height:1.5;color:#333;text-align:center;font-weight:bold;
        font-family:'PingFang SC',sans-serif;box-shadow:0 1px 6px rgba(0,0,0,0.05);
        box-sizing:border-box;
      }
      .vg-subtitle.hint { color:#999;font-size:22px;font-weight:normal; }
      /* 纯文字模式(无图): 字幕变大 + 占据主视觉区 */
      .vg-overlay.no-img .vg-subtitle {
        font-size:44px;line-height:1.55;min-height:32vh;
        max-width:1200px;padding:48px 64px;display:flex;
        align-items:center;justify-content:center;
      }
      .vg-img-btn {
        position:absolute;border:none;border-radius:20px;cursor:pointer;
        background:#1565C0;color:#fff;font-size:22px;font-weight:bold;
        font-family:'PingFang SC',sans-serif;box-shadow:0 2px 8px rgba(0,0,0,0.15);
        transition:background .2s;
      }
      .vg-img-btn:active { transform:scale(0.96); }

      /* 底部控制按钮栏 */
      .vg-ctrl-bar {
        display:flex;gap:14px;justify-content:center;align-items:stretch;
        width:94vw;max-width:1100px;margin:0;
      }
      .vg-ctrl-btn {
        flex:1;min-width:140px;max-width:340px;min-height:76px;padding:0 18px;
        font-size:24px;font-weight:bold;font-family:'PingFang SC',sans-serif;
        border-radius:18px;cursor:pointer;touch-action:manipulation;
        border:2px solid #707070;background:#B0B0B0;color:#1A1A1A;
        box-shadow:0 2px 8px rgba(0,0,0,0.15);
        transition:background .15s,transform .1s;
      }
      .vg-ctrl-btn:active { background:#8C8C8C;transform:scale(0.98); }
      .vg-ctrl-btn:disabled {
        background:#E8E8E8;color:#B0B0B0;border-color:#D0D0D0;
        cursor:not-allowed;box-shadow:none;transform:none;
      }
      .vg-ctrl-btn.vg-next {
        background:#1565C0;color:#fff;border-color:#0D47A1;
      }
      .vg-ctrl-btn.vg-next:active { background:#0D47A1; }
      .vg-ctrl-btn.vg-next.vg-next-final {
        background:#43A047;border-color:#2E7D32;
      }
      .vg-ctrl-btn.vg-next.vg-next-final:active { background:#2E7D32; }

      /* 左上静音开关 */
      .vg-mute-btn {
        position:fixed;top:12px;left:12px;z-index:9002;
        padding:8px 18px;min-height:38px;
        font-size:15px;font-family:'PingFang SC',sans-serif;font-weight:500;
        background:rgba(60,60,60,0.55);color:#fff;border:none;border-radius:8px;
        cursor:pointer;touch-action:manipulation;letter-spacing:1px;
      }
      .vg-mute-btn:hover { background:rgba(60,60,60,0.8); }
      .vg-mute-btn:active { background:rgba(60,60,60,0.95); }
      .vg-mute-btn.on { background:rgba(21,101,192,0.8); }

      /* 右上跳过 (主试模式) */
      .vg-skip-btn {
        position:fixed;top:12px;right:12px;z-index:9002;
        padding:6px 14px;min-height:28px;
        font-size:13px;font-family:'PingFang SC',sans-serif;
        background:rgba(60,60,60,0.55);color:#fff;border:none;border-radius:6px;
        cursor:pointer;touch-action:manipulation;
      }
      .vg-skip-btn:hover { background:rgba(60,60,60,0.8); }
      .vg-skip-btn:active { background:rgba(60,60,60,0.95); }

      /* 浏览器 autoplay 被 block 时的解锁遮罩 + 按钮 */
      .vg-unlock-mask {
        position:fixed;inset:0;z-index:9003;
        background:rgba(0,0,0,0.55);
        backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
        display:flex;align-items:center;justify-content:center;
        cursor:pointer;touch-action:manipulation;
      }
      .vg-unlock-hint {
        padding:28px 56px;font-size:30px;font-weight:bold;
        font-family:'PingFang SC',sans-serif;
        background:#1565C0;color:#fff;border:none;border-radius:20px;
        box-shadow:0 6px 30px rgba(0,0,0,0.35);cursor:pointer;touch-action:manipulation;
        animation:vg-pulse 1.4s ease-in-out infinite;letter-spacing:3px;
      }
      .vg-unlock-hint:active { background:#0D47A1;transform:scale(0.97); }
      @keyframes vg-pulse {
        0%,100% { box-shadow:0 6px 30px rgba(21,101,192,0.45); }
        50% { box-shadow:0 6px 50px rgba(21,101,192,0.85); }
      }
    `;
    document.head.appendChild(s);
  }

  /**
   * @param {Object} opts
   * @param {string} opts.image
   * @param {Array}  opts.steps - [{ audio, region, subtitle }] 或 [{ lines:[{audio,subtitle}], region }]
   * @param {Object} [opts.btnRegion] - {x,y,w,h} 图上"开始练习"按钮覆盖位置
   * @param {string} [opts.buttonText='开始练习']
   * @param {number} [opts.pauseBetween=400] - 保留兼容参数(v4 不再用自动串联播放)
   */
  function show(opts) {
    injectCSS();
    const { image, steps = [], btnRegion, buttonText = '开始练习' } = opts;

    _precacheSteps(steps);

    return new Promise(resolve => {
      /* ---- 展平成线性位置数组:每个 line 是一个可导航位置 ---- */
      const positions = [];
      steps.forEach((step, si) => {
        const lines = step.lines
          ? step.lines.map(l => typeof l === 'string' ? { subtitle: l } : l)
          : [{ audio: step.audio, subtitle: step.subtitle || '' }];
        const regions = step.regions && step.regions.length
          ? step.regions
          : (step.region ? [step.region] : []);
        lines.forEach((line, li) => {
          positions.push({
            stepIdx: si,
            lineIdx: li,
            audio: line.audio,
            subtitle: line.subtitle || '',
            regions,
          });
        });
      });
      const total = positions.length;

      /* ---- 初始状态 ---- */
      const _studentMode = (() => {
        try { if (localStorage.getItem('student_mode') === '1') return true; } catch(e){}
        return new URLSearchParams(location.search).get('student') === '1';
      })();
      const _testerMode = (() => {
        try { if (localStorage.getItem('tester_mode') === '1') return true; } catch(e){}
        return new URLSearchParams(location.search).get('tester') === '1';
      })();
      const _initMuted = (() => {
        const q = new URLSearchParams(location.search).get('mute');
        if (q === '1') return true;
        if (q === '0') return false;
        try {
          const ls = localStorage.getItem('voice_muted');
          if (ls === '1') return true;
          if (ls === '0') return false;
        } catch(e){}
        return _studentMode;  // 学生模式 → 默认静音
      })();
      // 自动播放模式: 音频播完自动进下一步, 老人不用点(最后一步例外, 必须手动点"开始")
      const _autoPlay = (() => {
        try { if (localStorage.getItem('auto_play_mode') === '1') return true; } catch(e){}
        return new URLSearchParams(location.search).get('autoplay') === '1';
      })();
      let muted = _initMuted;
      const AUTO_GAP_MS = 500;   // 自动进下一步的句间停顿
      let cur = 0;
      let curAudio = null;

      /* ---- DOM ---- */
      const overlay = document.createElement('div');
      overlay.className = 'vg-overlay' + (image ? '' : ' no-img');

      // 图片可选: image 为 falsy 时走纯文字模式(无 img / 无 region 高亮 / 无 imgBtn)
      let imgWrap = null;
      const _highlights = [];
      function _getHighlight(i) {
        if (!imgWrap) return null;
        if (_highlights[i]) return _highlights[i];
        const h = document.createElement('div');
        h.className = 'vg-highlight';
        imgWrap.appendChild(h);
        _highlights[i] = h;
        return h;
      }
      function _setActiveRegions(regions) {
        for (const h of _highlights) h.classList.remove('active');
        if (!imgWrap || !regions || !regions.length) return;
        regions.forEach((r, i) => {
          const h = _getHighlight(i);
          if (!h) return;
          h.style.left = r.x;
          h.style.top = r.y;
          h.style.width = r.w;
          h.style.height = r.h;
          h.classList.add('active');
        });
      }

      let imgBtn = null;
      if (image) {
        imgWrap = document.createElement('div');
        imgWrap.className = 'vg-img-wrap';
        const img = document.createElement('img');
        img.src = image;
        imgWrap.appendChild(img);

        if (btnRegion) {
          imgBtn = document.createElement('button');
          imgBtn.className = 'vg-img-btn';
          imgBtn.style.left = btnRegion.x;
          imgBtn.style.top = btnRegion.y;
          imgBtn.style.width = btnRegion.w;
          imgBtn.style.height = btnRegion.h;
          imgBtn.textContent = buttonText;
          imgWrap.appendChild(imgBtn);
        }

        overlay.appendChild(imgWrap);
      }

      const subtitle = document.createElement('div');
      subtitle.className = 'vg-subtitle';
      subtitle.textContent = '';
      overlay.appendChild(subtitle);

      /* ---- 底部控制栏: [上一步] [再听一遍] [下一步 / 开始练习] ---- */
      const ctrlBar = document.createElement('div');
      ctrlBar.className = 'vg-ctrl-bar';

      const prevBtn = document.createElement('button');
      prevBtn.className = 'vg-ctrl-btn vg-prev';
      prevBtn.textContent = '上一步';
      prevBtn.disabled = true;

      const replayBtn = document.createElement('button');
      replayBtn.className = 'vg-ctrl-btn vg-replay';
      replayBtn.textContent = '再听一遍';
      replayBtn.disabled = muted;

      const nextBtn = document.createElement('button');
      nextBtn.className = 'vg-ctrl-btn vg-next';
      nextBtn.textContent = buttonText;

      ctrlBar.append(prevBtn, replayBtn, nextBtn);
      overlay.appendChild(ctrlBar);

      /* ---- 左上静音开关 ---- */
      const muteBtn = document.createElement('button');
      muteBtn.className = 'vg-mute-btn' + (muted ? ' on' : '');
      muteBtn.textContent = muted ? '开声音' : '静音';
      overlay.appendChild(muteBtn);

      /* ---- 跳过按钮 + Esc (仅主试模式) ---- */
      let _vgEscHandler = null;
      function _vgExit() {
        _stopAudio();
        if (_vgEscHandler) {
          document.removeEventListener('keydown', _vgEscHandler);
          _vgEscHandler = null;
        }
        const _p = document.getElementById('_nback_progress');
        if (_p) _p.style.display = '';
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        resolve();
      }
      if (_testerMode) {
        const skipBtn = document.createElement('button');
        skipBtn.className = 'vg-skip-btn';
        skipBtn.textContent = '跳过 (Esc)';
        skipBtn.onclick = _vgExit;
        overlay.appendChild(skipBtn);
        _vgEscHandler = (e) => { if (e.key === 'Escape') _vgExit(); };
        document.addEventListener('keydown', _vgEscHandler);
      }

      document.body.appendChild(overlay);

      /* 隐藏可能残留的 N-back 进度计数器 */
      const progressEl = document.getElementById('_nback_progress');
      if (progressEl) progressEl.style.display = 'none';

      /* ---- 无 steps: 降级成老的"一张图 + 开始按钮"模式 ---- */
      if (!total) {
        ctrlBar.style.display = 'none';
        replayBtn.style.display = 'none';
        subtitle.className = 'vg-subtitle hint';
        subtitle.textContent = btnRegion ? '点击按钮开始' : '';
        if (imgBtn) {
          imgBtn.onclick = _vgExit;
        } else {
          nextBtn.onclick = _vgExit;
          ctrlBar.style.display = '';
          prevBtn.style.display = 'none';
          replayBtn.style.display = 'none';
        }
        return;
      }

      /* ---- 音频工具 + autoplay 解锁兜底 ---- */
      let _unlockMask = null;
      function _removeUnlock() {
        if (_unlockMask && _unlockMask.parentNode) _unlockMask.parentNode.removeChild(_unlockMask);
        _unlockMask = null;
      }
      function _showUnlock(src) {
        if (_unlockMask) return;
        const mask = document.createElement('div');
        mask.className = 'vg-unlock-mask';
        const btn = document.createElement('button');
        btn.className = 'vg-unlock-hint';
        btn.textContent = '开始介绍规则';
        mask.appendChild(btn);
        const handler = (e) => {
          e.stopPropagation();
          _removeUnlock();
          _playAudio(src);
        };
        mask.onclick = handler;
        btn.onclick = handler;
        overlay.appendChild(mask);
        _unlockMask = mask;
      }
      function _stopAudio() {
        if (curAudio) {
          try { curAudio.pause(); curAudio.currentTime = 0; } catch(e){}
          curAudio = null;
        }
      }
      function _playAudio(src) {
        if (!src || muted) return;
        let a = _audioCache[src];
        if (!a) { a = new Audio(src); _audioCache[src] = a; }
        try { a.pause(); a.currentTime = 0; } catch(e){}
        curAudio = a;

        // 自动播放模式: 音频播完触发 _goNext (仅当仍在同一步 & 非最后一步 & 未静音)
        if (a._vgEndedHandler) a.removeEventListener('ended', a._vgEndedHandler);
        const myPos = cur;
        a._vgEndedHandler = () => {
          if (!_autoPlay || muted) return;
          if (cur !== myPos) return;           // 用户已手动切走
          if (cur >= total - 1) return;        // 最后一步不自动关闭
          setTimeout(() => {
            if (cur === myPos && _autoPlay && !muted) _goNext();
          }, AUTO_GAP_MS);
        };
        a.addEventListener('ended', a._vgEndedHandler, { once: true });

        const p = a.play();
        if (p && typeof p.then === 'function') {
          p.then(() => { _removeUnlock(); })
           .catch((err) => {
             // 仅对 autoplay 被 block 的情况弹解锁按钮,其他错误(加载失败等)忽略
             if (err && (err.name === 'NotAllowedError' || /interact|gesture|user/i.test(err.message || ''))) {
               _showUnlock(src);
             }
           });
        }
      }

      /* ---- 位置渲染 ---- */
      function _render(i, { autoplay = true } = {}) {
        _stopAudio();
        if (i < 0) i = 0;
        if (i > total - 1) i = total - 1;
        cur = i;
        const p = positions[i];
        _setActiveRegions(p.regions);
        subtitle.className = 'vg-subtitle';
        subtitle.textContent = p.subtitle;

        const isLast = (i === total - 1);
        prevBtn.disabled = (i === 0);
        if (isLast) {
          nextBtn.textContent = buttonText;
          nextBtn.classList.add('vg-next-final');
        } else {
          nextBtn.textContent = `下一步 (${i + 1}/${total})`;
          nextBtn.classList.remove('vg-next-final');
        }
        if (imgBtn) {
          imgBtn.textContent = isLast ? buttonText : '下一步';
        }

        // 自动播放模式: 隐藏所有前进按钮,仅最后一步显示"开始"防止意外跳入练习
        if (_autoPlay) {
          prevBtn.style.display = 'none';
          replayBtn.style.display = 'none';
          nextBtn.style.display = isLast ? '' : 'none';
          if (imgBtn) imgBtn.style.display = isLast ? '' : 'none';
        }

        if (autoplay) _playAudio(p.audio);
      }

      /* ---- 按钮事件 ---- */
      function _goNext() {
        if (cur >= total - 1) _vgExit();
        else _render(cur + 1);
      }
      function _goPrev() {
        if (cur > 0) _render(cur - 1);
      }
      prevBtn.onclick = _goPrev;
      nextBtn.onclick = _goNext;
      if (imgBtn) imgBtn.onclick = _goNext;
      replayBtn.onclick = () => {
        _stopAudio();
        _playAudio(positions[cur].audio);
      };
      muteBtn.onclick = () => {
        muted = !muted;
        try { localStorage.setItem('voice_muted', muted ? '1' : '0'); } catch(e){}
        muteBtn.textContent = muted ? '开声音' : '静音';
        muteBtn.classList.toggle('on', muted);
        replayBtn.disabled = muted;
        if (muted) {
          _stopAudio();
          _removeUnlock();
        } else if (positions[cur].audio) {
          _playAudio(positions[cur].audio);
        }
      };

      /* ---- 首次渲染 ---- */
      _render(0);
    });
  }

  /* ---- 独立短音频 + 字幕(给非指导语场景用,保留原接口) ---- */
  function playClip(audioSrc, subtitleText) {
    return new Promise(resolve => {
      if (!audioSrc) { resolve(); return; }
      injectCSS();
      const el = document.createElement('div');
      el.className = 'vg-subtitle';
      el.style.cssText = 'position:fixed;bottom:36px;left:50%;transform:translateX(-50%);z-index:9000;';
      el.textContent = subtitleText || '';
      document.body.appendChild(el);
      let a = _audioCache[audioSrc];
      if (a) {
        a.currentTime = 0;
      } else {
        a = new Audio(audioSrc);
      }
      const done = () => { el.remove(); resolve(); };
      a.addEventListener('ended', done, { once: true });
      a.addEventListener('error', done, { once: true });
      a.play().catch(done);
    });
  }

  return { show, playClip };
})();
