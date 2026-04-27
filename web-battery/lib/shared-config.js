/**
 * 统一配置 — 所有范式共用
 */
export const CONFIG = {
  // 字体
  fontFamily: '"Microsoft YaHei", "PingFang SC", "Heiti SC", sans-serif',

  // 配色
  colors: {
    primary: '#1A8CFF',
    primaryHover: '#4DA6FF',
    primaryPress: '#0066CC',
    bg: '#FFFFFF',
    text: '#1A1A2E',
    textSecondary: '#666666',
    success: '#4CAF50',
    error: '#F44336',
    warning: '#FF9800',
    border: '#E0E0E0',
    cardBg: '#F8F9FA',
  },

  // 触摸按钮（老年友好）
  button: {
    minHeight: 80,       // px
    fontSize: 36,        // px
    borderRadius: 12,    // px
    padding: '16px 40px',
  },

  // 指导语页
  instruction: {
    titleSize: 48,       // px
    bodySize: 32,        // px
    imageMaxHeight: '60vh',
    continueButtonText: '继续',
    minWaitMs: 800,      // 防误触最短等待
  },

  // 数据
  data: {
    csvBOM: '\uFEFF',    // UTF-8 BOM for Excel
    timestampFormat: 'YYYYMMDD_HHmmss',
  },

  // 摄像头
  camera: {
    width: 1280,
    height: 720,
    facingMode: 'user',
    mimeType: 'video/webm;codecs=vp9',
    chunkIntervalMs: 30000, // 30s chunks
  },
};

/**
 * 获取 URL 参数
 */
export function getUrlParams() {
  const params = new URLSearchParams(window.location.search);
  return {
    subjectId: params.get('sid') || '',
    session: params.get('session') || 'S001',
    sex: params.get('sex') || '',
  };
}

/**
 * 生成文件名时间戳
 */
export function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}
