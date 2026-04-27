/**
 * attention-probe.js — 统一注意力自评探针
 *
 * 所有范式共用。在自然休息点插入 1-9 专注度评分。
 * 用法: timeline.push(buildAttentionProbe(jsPsych, paradigm, position));
 *
 * 视觉标准:
 *   - 96×96 灰色按钮 (#B0B0B0)，和响应按钮同风格
 *   - 选中变蓝 (#1565C0)
 *   - "继续"按钮选择前禁用
 */
(function () {
  'use strict';

  /**
   * 构建一个注意力探针 trial（jsPsych html-button-response）
   *
   * @param {object} jsPsych    jsPsych 实例
   * @param {string} paradigm   范式名（如 'flanker'）
   * @param {string} position   探针位置标识（如 'after_block_1', 'end'）
   * @returns {object} jsPsych trial 节点，可直接 push 到 timeline
   */
  window.buildAttentionProbe = function (jsPsych, paradigm, position) {
    var _probeRating = null;
    var _probeStartTime = 0;

    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: function () {
        return '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:60vh;padding:24px 40px;text-align:center;">' +
          '<div style="font-size:48px;font-weight:bold;color:#1A1A2E;margin-bottom:16px;">休息一下</div>' +
          '<div style="font-size:32px;color:#555;margin-bottom:24px;">请评价您刚才对任务的<b>专注程度</b></div>' +
          '<div style="font-size:22px;color:#999;margin-bottom:20px;">1 = 完全走神 &nbsp;&nbsp;&nbsp;&nbsp; 9 = 非常专注</div>' +
          '<div class="attn-probe-buttons" style="display:flex;gap:12px;flex-wrap:wrap;justify-content:center;margin-bottom:20px;">' +
          [1, 2, 3, 4, 5, 6, 7, 8, 9].map(function (n) {
            return '<button class="attn-probe-btn" data-rating="' + n + '">' + n + '</button>';
          }).join('') +
          '</div>' +
          '<div style="font-size:20px;color:#AAA;font-style:italic;">选择评分后点击继续</div>' +
          '</div>';
      },
      choices: ['继续'],
      button_html: function (choice) {
        return '<button class="jspsych-btn" id="_attn_probe_continue" style="margin-top:12px;">' + choice + '</button>';
      },
      on_load: function () {
        _probeRating = null;
        _probeStartTime = performance.now();

        // 禁用继续按钮
        var continueBtn = document.getElementById('_attn_probe_continue');
        if (continueBtn) {
          continueBtn.disabled = true;
          continueBtn.style.opacity = '0.4';
        }

        // 评分按钮点击
        var buttons = document.querySelectorAll('.attn-probe-btn');
        buttons.forEach(function (btn) {
          btn.addEventListener('click', function () {
            // 取消其他选中
            buttons.forEach(function (b) { b.classList.remove('selected'); });
            // 选中当前
            btn.classList.add('selected');
            _probeRating = parseInt(btn.dataset.rating);
            // 启用继续按钮
            if (continueBtn) {
              continueBtn.disabled = false;
              continueBtn.style.opacity = '1';
            }
          });
        });
      },
      on_finish: function (data) {
        var rt = Math.round(performance.now() - _probeStartTime);
        data.trial_type = 'attention_probe';
        data.paradigm = paradigm;
        data.probe_position = position;
        data.attention_rating = _probeRating || 5;
        data.probe_rt_ms = rt;
        data.probe_timestamp = new Date().toISOString();

        // 存到全局收集器（如果存在）
        if (window._attentionProbeData) {
          window._attentionProbeData.push({
            paradigm: paradigm,
            position: position,
            rating: _probeRating || 5,
            rt_ms: rt,
            timestamp: new Date().toISOString(),
          });
        }
      },
    };
  };

  /**
   * 非 jsPsych 版本：用 DOM 弹窗显示注意力探针，返回 Promise
   * 适用于 TMT、Visuospatial 等不用 jsPsych timeline 的范式
   *
   * @param {string} paradigm   范式名
   * @param {string} position   探针位置标识
   * @returns {Promise<{rating:number, rt_ms:number}>}
   */
  window.showAttentionProbeAsync = function (paradigm, position) {
    return new Promise(function (resolve) {
      var startTime = performance.now();
      var selectedRating = null;

      var overlay = document.createElement('div');
      overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:white;z-index:99990;display:flex;align-items:center;justify-content:center;';

      var box = document.createElement('div');
      box.style.cssText = 'text-align:center;max-width:800px;padding:40px;';
      box.innerHTML =
        '<div style="font-size:48px;font-weight:bold;color:#1A1A2E;margin-bottom:16px;">休息一下</div>' +
        '<div style="font-size:32px;color:#555;margin-bottom:24px;">请评价您刚才对任务的<b>专注程度</b></div>' +
        '<div style="font-size:22px;color:#999;margin-bottom:20px;">1 = 完全走神 &nbsp;&nbsp;&nbsp;&nbsp; 9 = 非常专注</div>' +
        '<div id="_async_probe_btns" style="display:flex;gap:12px;flex-wrap:wrap;justify-content:center;margin-bottom:20px;"></div>' +
        '<div style="font-size:20px;color:#AAA;font-style:italic;margin-bottom:16px;">选择评分后点击继续</div>' +
        '<button id="_async_probe_continue" class="jspsych-btn" disabled style="opacity:0.4;margin-top:12px;">继续</button>';

      overlay.appendChild(box);
      document.body.appendChild(overlay);

      // 生成9个按钮
      var btnContainer = document.getElementById('_async_probe_btns');
      for (var n = 1; n <= 9; n++) {
        (function (rating) {
          var btn = document.createElement('button');
          btn.className = 'attn-probe-btn';
          btn.textContent = rating;
          btn.addEventListener('click', function () {
            // 取消其他选中
            btnContainer.querySelectorAll('.attn-probe-btn').forEach(function (b) { b.classList.remove('selected'); });
            btn.classList.add('selected');
            selectedRating = rating;
            var cont = document.getElementById('_async_probe_continue');
            cont.disabled = false;
            cont.style.opacity = '1';
          });
          btnContainer.appendChild(btn);
        })(n);
      }

      // 继续按钮
      document.getElementById('_async_probe_continue').addEventListener('click', function () {
        var rt = Math.round(performance.now() - startTime);
        var result = { rating: selectedRating || 5, rt_ms: rt };
        overlay.remove();

        // 存到全局收集器
        if (window._attentionProbeData) {
          window._attentionProbeData.push({
            paradigm: paradigm,
            position: position,
            rating: result.rating,
            rt_ms: result.rt_ms,
            timestamp: new Date().toISOString(),
          });
        }

        resolve(result);
      });
    });
  };

  // 全局探针数据收集器
  window._attentionProbeData = window._attentionProbeData || [];

})();
