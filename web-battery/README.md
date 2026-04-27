# oldman-web

浙江大学老年认知评估 Web 平台 — 前端 + 静态资源。

基于 jsPsych 8 构建的多范式认知测评系统，面向老年人群（60+），支持 Surface 平板触屏施测。

## 范式列表（12 个）

| # | 范式 | 目录 | 认知域 | 时长 |
|---|------|------|--------|------|
| 1 | Flanker | `paradigms/flanker/` | 选择性注意 | ~5 min |
| 2 | SART | `paradigms/sart/` | 持续性注意 | ~4 min |
| 3 | N-back (B1-B3) | `paradigms/nback/` | 工作记忆 | ~6 min |
| 4 | VSTMB | `paradigms/vstmb/` | 短时记忆捆绑 | ~8 min |
| 5 | TMT | `paradigms/tmt/` | 执行功能 | ~8 min |
| 6 | 画钟测验 | `paradigms/clock/` | 执行功能 | ~5 min |
| 7 | 人际距离 | `paradigms/interpersonal/` | 社会认知 | ~3 min |
| 8 | 空间导航 | `paradigms/visuospatial/` | 空间能力 | ~10 min |
| 9 | 眼动追踪 | `paradigms/eyetracking/` | 自然注视 | ~7 min |
| 10 | VPC | `paradigms/vpc/` | 视觉配对比较 | ~5 min |
| 11 | 语音 | `paradigms/speech/` | 语言/言语 | ~11 min |
| 12 | Precheck | `paradigms/precheck/` | 设备预检 | ~1 min |

全流程约 67 分钟。

## 目录结构

```
├── index.html              # 主控台（施测工作台）
├── landing.html            # 着陆页
├── paradigms/              # 12 个范式实现
├── stimuli/                # 刺激图片素材
├── audio/                  # 语音指导语音频
├── lib/                    # 公共 JS 库
│   ├── jspsych.js          # jsPsych 核心
│   ├── safe-fetch.js       # fetch 封装（15s 超时）
│   ├── attention-probe.js  # 注意力探针（1-9 Likert）
│   ├── touch-hardening.js  # 触屏适老化（防抖/漂移容忍/RT 校正）
│   ├── paradigm-camera.js  # 前置摄像头录制
│   ├── end-screen.js       # 结束画面 + LocalPack ZIP 下载
│   └── data-sync.js        # 数据保存 + localStorage 备份
├── css/common.css          # 统一样式（按钮/反馈/探针）
├── server/                 # FastAPI 后端（见 oldman-service 仓库）
│   ├── main.py
│   └── requirements.txt
├── sw.js                   # Service Worker（PWA 离线缓存）
├── manifest.json           # PWA manifest
└── Dockerfile
```

## 部署指南

### 环境要求

- Python 3.11+
- pip

### 方式一：直接部署（推荐）

```bash
# 1. 克隆仓库
git clone <本仓库地址> /opt/oldman-web
cd /opt/oldman-web

# 2. 安装 Python 依赖
pip install -r server/requirements.txt

# 3. 创建数据目录
mkdir -p server/data

# 4. 启动服务
python -m uvicorn server.main:app --host 0.0.0.0 --port 8082
```

访问 `http://<服务器IP>:8082` 即可看到着陆页。

### 方式二：Docker

```bash
git clone <本仓库地址> /opt/oldman-web
cd /opt/oldman-web

docker build -t oldman-web .
docker run -d --name oldman-web \
  -p 8082:8082 \
  -v /opt/oldman-web/server/data:/app/server/data \
  --restart unless-stopped \
  oldman-web
```

### 后台常驻（systemd）

不用 Docker 的话，建议用 systemd 管理进程：

```ini
# /etc/systemd/system/oldman-web.service
[Unit]
Description=Oldman Cognitive Assessment Web
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/oldman-web
ExecStart=/usr/bin/python3 -m uvicorn server.main:app --host 0.0.0.0 --port 8082
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now oldman-web
sudo systemctl status oldman-web    # 查看状态
sudo journalctl -u oldman-web -f   # 查看日志
```

### Nginx 反向代理（HTTPS）

如果域名已备案并配好 SSL 证书：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate     /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    client_max_body_size 100M;  # 视频上传需要

    location / {
        proxy_pass http://127.0.0.1:8082;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

> **注意**：语音范式需要录音权限，浏览器要求 HTTPS 才能使用麦克风。如果不配 HTTPS，语音和摄像头功能将不可用。

### 数据说明

被试数据保存在 `server/data/{被试编号}/{范式名}/`，包含 CSV、JSON、PNG、WebM 等文件。

```bash
# 查看所有被试
ls server/data/

# 下载某个被试的全部数据（ZIP）
curl -O http://localhost:8082/api/download/{被试编号}
```

建议定期备份 `server/data/` 目录。

### 更新代码

```bash
cd /opt/oldman-web
git pull
# 如果用 systemd：
sudo systemctl restart oldman-web
# 如果用 Docker：
docker restart oldman-web
```

## 技术栈

- **jsPsych 8** — 实验框架
- **Vanilla HTML/CSS/JS** — 无前端框架依赖
- **FastAPI** — 后端数据服务（`server/`）

## 适老化设计

- 灰色响应按钮（#B0B0B0），避免 Stroop 干扰
- 非惩罚性练习反馈（"✓ 对了" / "没关系，再看仔细"）
- 触屏 RT 校正至 pointerdown（认知决策时刻）
- 三指双击退出范式（施测人员专用）
- 全屏自动启动 + 弹窗拦截检测
