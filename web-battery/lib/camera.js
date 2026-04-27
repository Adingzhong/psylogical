/**
 * 摄像头静默录制管理器
 * 使用 getUserMedia + MediaRecorder
 */
export class CameraRecorder {
  constructor() {
    this.stream = null;
    this.recorder = null;
    this.chunks = [];
    this.timestamps = [];
    this.startTime = 0;
  }

  /**
   * 初始化摄像头（请求权限）
   */
  async init(options = {}) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('当前访问地址不支持摄像头。局域网设备请使用 HTTPS 地址打开。');
    }

    const constraints = {
      video: {
        facingMode: options.facingMode || 'user',
        width: { ideal: options.width || 1280 },
        height: { ideal: options.height || 720 },
      },
      audio: false,
    };

    this.stream = await navigator.mediaDevices.getUserMedia(constraints);

    // 选择最佳编码
    const mimeTypes = [
      'video/webm;codecs=vp9',
      'video/webm;codecs=vp8',
      'video/webm',
      'video/mp4',
    ];
    this.mimeType = mimeTypes.find(t => MediaRecorder.isTypeSupported(t)) || '';
    console.log(`[Camera] initialized, codec: ${this.mimeType}`);
  }

  /**
   * 开始录制
   */
  start() {
    if (!this.stream) throw new Error('Camera not initialized');

    this.chunks = [];
    this.timestamps = [];
    this.startTime = performance.now();

    const options = this.mimeType ? { mimeType: this.mimeType } : {};
    this.recorder = new MediaRecorder(this.stream, options);

    this.recorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };

    // 每30秒取一次chunk，防止崩溃丢全部数据
    this.recorder.start(30000);
    console.log('[Camera] recording started');
  }

  /**
   * 添加时间戳标记（用于对齐视频和行为数据）
   */
  addTimestamp(eventName) {
    this.timestamps.push({
      event: eventName,
      time_ms: performance.now() - this.startTime,
      epoch_ms: Date.now(),
    });
  }

  /**
   * 停止录制
   */
  async stop() {
    return new Promise((resolve) => {
      if (!this.recorder || this.recorder.state === 'inactive') {
        resolve({ blob: null, timestamps: this.timestamps });
        return;
      }

      this.recorder.onstop = () => {
        const blob = new Blob(this.chunks, { type: this.mimeType || 'video/webm' });
        console.log(`[Camera] stopped, ${blob.size} bytes, ${this.timestamps.length} markers`);
        resolve({ blob, timestamps: this.timestamps });
      };

      this.recorder.stop();
    });
  }

  /**
   * 释放摄像头
   */
  destroy() {
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
    this.recorder = null;
    console.log('[Camera] destroyed');
  }

  /**
   * 时间戳导出为 CSV
   */
  timestampsToCSV() {
    const bom = '\uFEFF';
    const header = 'event,time_ms,epoch_ms\n';
    const rows = this.timestamps.map(t => `${t.event},${t.time_ms.toFixed(1)},${t.epoch_ms}`).join('\n');
    return bom + header + rows;
  }
}
