/**
 * Service Worker — 认知评估平台离线缓存
 *
 * 缓存策略:
 *   /api/*               → 不缓存（数据上传必须到服务器）
 *   /audio/*, /stimuli/* → Cache-first（大文件，几乎不变）
 *   HTML (navigate)      → Network-first（保证拿到最新HTML，离线时用缓存）
 *   JS/CSS/其他          → Cache-first（由HTML里的 ?v= 控制版本）
 *
 * 更新部署：
 *   - 只改代码（JS/CSS/HTML）→ 改 SHELL_VER → 旧 shell 缓存清除，素材保留
 *   - 改了刺激图/音频        → 改 ASSET_VER → 素材缓存清除
 */

var SHELL_VER = 'shell-v23';
var ASSET_VER = 'assets-v5';
var VALID = [SHELL_VER, ASSET_VER];

/* ---- Install: 立即激活，不等旧SW退出 ---- */
self.addEventListener('install', function () {
  self.skipWaiting();
});

/* ---- Activate: 清理旧版缓存 + 立即接管所有页面 ---- */
self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return VALID.indexOf(k) === -1; })
            .map(function (k) { return caches.delete(k); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

/* ---- Fetch: 按URL模式分发策略 ---- */
self.addEventListener('fetch', function (event) {
  var url = new URL(event.request.url);

  // 非 GET 请求（POST 数据保存等）：直接放行
  if (event.request.method !== 'GET') return;

  // blob: URL（本地内存下载）：不拦截，否则报网络错误
  if (url.protocol === 'blob:') return;

  // /api/* ：永远走网络
  if (url.pathname.startsWith('/api/')) return;

  // /dispatch/* : 调度系统,状态实时变化,永远走网络 (不缓存)
  // /dispatch-static/* 例外 (CSS/JS 可缓存)
  if (url.pathname.startsWith('/dispatch/')) return;

  // sw.js 自身：不缓存
  if (url.pathname === '/sw.js') return;

  // 音频 & 刺激图：cache-first（205MB，首次加载后全走缓存）
  if (url.pathname.startsWith('/audio/') || url.pathname.startsWith('/stimuli/')) {
    event.respondWith(cacheFirst(event.request, ASSET_VER));
    return;
  }

  // HTML 页面导航：network-first（保证拿到最新 HTML，离线走缓存）
  // 判断：navigate 模式，或 .html 结尾，或根路径
  if (event.request.mode === 'navigate' ||
      url.pathname.endsWith('.html') ||
      url.pathname === '/' ||
      url.pathname === '/app') {
    event.respondWith(networkFirst(event.request, SHELL_VER));
    return;
  }

  // JS / CSS / 字体 / 其他静态资源：cache-first
  // HTML 里的 ?v=20260410c 保证版本更新时 URL 变化 → 自动 cache miss → 拉新版
  event.respondWith(cacheFirst(event.request, SHELL_VER));
});

/* ============================================================
   策略实现
   ============================================================ */

/**
 * 带退避重试的 fetch (2026-04-19 加)
 * 网络抖动 < 1s 通常能 recover,重试两次足够覆盖大部分场景
 * 每次间隔: 第 1 次 300ms, 第 2 次 700ms(总累积 < 1s)
 */
function fetchWithRetry(request) {
  function tryFetch(attempt) {
    return fetch(request).then(function (response) {
      // 5xx 也当失败重试(不止网络错)
      if (!response.ok && response.status >= 500 && attempt < 2) {
        throw new Error('retry_on_' + response.status);
      }
      return response;
    }).catch(function (err) {
      if (attempt < 2) {
        var delay = attempt === 0 ? 300 : 700;
        return new Promise(function (resolve) {
          setTimeout(function () { resolve(tryFetch(attempt + 1)); }, delay);
        });
      }
      throw err;
    });
  }
  return tryFetch(0);
}

/**
 * Cache-first: 有缓存就用，没有才走网络并缓存结果。
 * 适用于稳定不变的大文件（音频/图片）和有版本号的 JS/CSS。
 */
function cacheFirst(request, cacheName) {
  return caches.match(request).then(function (cached) {
    if (cached) return cached;

    return fetchWithRetry(request).then(function (response) {
      if (response.ok) {
        var clone = response.clone();
        caches.open(cacheName).then(function (cache) { cache.put(request, clone); });
      }
      return response;
    }).catch(function () {
      return new Response('', { status: 503, statusText: 'Offline' });
    });
  });
}

/**
 * Network-first: 先走网络，失败才用缓存。
 * 适用于 HTML 页面（需要拿到最新版本，但离线时也能用）。
 */
function networkFirst(request, cacheName) {
  return fetchWithRetry(request).then(function (response) {
    if (response.ok) {
      var clone = response.clone();
      // 缓存时去掉 ?sid= 等查询参数，同一个 HTML 只存一份
      var url = new URL(request.url);
      var cleanUrl = url.origin + url.pathname;
      var cacheKey = new Request(cleanUrl);
      caches.open(cacheName).then(function (cache) { cache.put(cacheKey, clone); });
    }
    return response;
  }).catch(function () {
    // 网络失败 → 从缓存取（用去掉参数的 key 匹配）
    var url = new URL(request.url);
    var cleanUrl = url.origin + url.pathname;
    return caches.match(new Request(cleanUrl)).then(function (cached) {
      return cached || new Response(
        '<!DOCTYPE html><html><body style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;font-size:24px;color:#666;">当前处于离线模式，该页面尚未缓存</body></html>',
        { status: 503, headers: { 'Content-Type': 'text/html;charset=utf-8' } }
      );
    });
  });
}
