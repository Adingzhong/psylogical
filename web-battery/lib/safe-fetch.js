/**
 * safe-fetch.js — 带超时的 fetch 封装 + 自动注入主试字段
 *
 * 解决: 弱网环境下 fetch 无限挂起，永远不触发 fallback 下载。
 * 用法: 把关键 save 请求的 fetch(...) 换成 safeFetch(...)，接口完全一样。
 * 默认 15 秒超时，超时后 reject（触发 catch → fallback 下载）。
 *
 * 2026-04-18 增补: 当 URL 走 /api/ 且 body 是 JSON/FormData 时,
 * 自动把 localStorage 里的 examiner_name / examiner_id 附加上去。
 * 目的: 不改 11 个范式文件,统一在 fetch 入口注入主试信息。
 */
(function () {
  'use strict';

  var DEFAULT_TIMEOUT_MS = 15000;

  function getExaminer() {
    try {
      return {
        name: (localStorage.getItem('examiner_name') || '').trim(),
        id: (localStorage.getItem('examiner_id') || '').trim(),
      };
    } catch (e) { return { name: '', id: '' }; }
  }

  // 给 opts.body 追加主试字段(JSON 或 FormData)。返回新的 opts。
  function injectExaminer(url, opts) {
    if (!url || url.indexOf('/api/') === -1) return opts;
    var exam = getExaminer();
    if (!exam.name) return opts;  // 没登录主试,不注入(静默降级)
    if (!opts || !opts.body) return opts;

    // FormData: 直接 append
    if (opts.body instanceof FormData) {
      if (!opts.body.has('examiner_name')) opts.body.append('examiner_name', exam.name);
      if (exam.id && !opts.body.has('examiner_id')) opts.body.append('examiner_id', exam.id);
      return opts;
    }

    // JSON (string body with Content-Type JSON)
    var ct = opts.headers && (opts.headers['Content-Type'] || opts.headers['content-type']);
    if (typeof opts.body === 'string' && ct && ct.indexOf('application/json') !== -1) {
      try {
        var obj = JSON.parse(opts.body);
        if (typeof obj === 'object' && obj !== null) {
          if (!obj.examiner_name) obj.examiner_name = exam.name;
          if (exam.id && !obj.examiner_id) obj.examiner_id = exam.id;
          opts = Object.assign({}, opts, { body: JSON.stringify(obj) });
        }
      } catch (e) { /* body 不是合法 JSON,跳过 */ }
    }
    return opts;
  }

  /**
   * Drop-in replacement for fetch() with timeout + examiner injection.
   */
  window.safeFetch = function (url, opts, timeoutMs) {
    timeoutMs = timeoutMs || DEFAULT_TIMEOUT_MS;
    opts = injectExaminer(url, opts);

    // If caller already set their own AbortSignal, don't override
    if (opts && opts.signal) {
      return fetch(url, opts);
    }

    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, timeoutMs);
    var fetchOpts = Object.assign({}, opts || {}, { signal: controller.signal });

    return fetch(url, fetchOpts).finally(function () {
      clearTimeout(timer);
    });
  };
})();
