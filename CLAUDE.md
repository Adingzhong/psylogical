# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Zhejiang University MCI cognitive assessment platform. Two versions coexist:

1. **PsychoPy desktop version** (legacy) — `Flanker/`, `SART/`, `N-back/`, `TMT/`, `VSTMB/`, etc.
2. **Web version** (actively deployed) — `web-battery/` — jsPsych 8 + FastAPI, runs on any browser

The Web version is the **primary deployment target** for field testing on Surface tablets and the A100 server.

## Web Platform (web-battery/)

### Quick Start (Local)
```bash
cd web-battery
pip install fastapi uvicorn python-multipart
python -m uvicorn server.main:app --host 127.0.0.1 --port 8082
# Browser: http://localhost:8082
```

### Server Deployment (ZJU A100)
```
Server: 10.130.12.71 (zjupsych11-G5500-V7, Ubuntu 22.04, 8x A100 80GB)
User: zju-psych-11
Project: ~/projects/cognitive-assessment/
Web files: ~/projects/cognitive-assessment/web-battery/
Data: ~/projects/cognitive-assessment/web-battery/server/data/{subject_id}/
Start: bash ~/projects/cognitive-assessment/start.sh
Stop: bash ~/projects/cognitive-assessment/stop.sh
Log: /tmp/cognitive-assessment.log
Port: 8082
Access: http://10.130.12.71:8082 (campus network)
```

### 10 Paradigms (Web)
| # | Name | File | Domain | ~Duration |
|---|------|------|--------|-----------|
| 1 | Flanker | `paradigms/flanker/` | Selective attention | ~5 min |
| 2 | SART | `paradigms/sart/` | Sustained attention | ~4 min |
| 3 | N-back | `paradigms/nback/` | Working memory (B1-B3, B4 removed) | ~6 min |
| 4 | VSTMB | `paradigms/vstmb/` | Short-term memory binding | ~8 min |
| 5 | TMT | `paradigms/tmt/` | Executive function | ~8 min |
| 6 | Clock Drawing | `paradigms/clock/` | Executive function | ~5 min |
| 7 | Interpersonal Distance | `paradigms/interpersonal/` | Social cognition | ~3 min |
| 8 | Visuospatial Navigation | `paradigms/visuospatial/` | Spatial ability | ~10 min |
| 9 | Eye Tracking | `paradigms/eyetracking/` | Naturalistic gaze (will be redesigned as VPC) | ~7 min |
| 10 | Speech | `paradigms/speech/` | Language/speech | ~11 min |

### Web Tech Stack
- **Frontend**: jsPsych 8 + vanilla HTML/CSS/JS, no framework
- **Backend**: Python FastAPI (data save + ZIP download)
- **Shared libs** (`lib/`):
  - `jspsych.js` — jsPsych core
  - `safe-fetch.js` — fetch wrapper with 15s timeout (all paradigms use this for data saves)
  - `attention-probe.js` — unified 1-9 attention rating probe (all paradigms)
  - `touch-hardening.js` — elderly touch adaptation (debounce, drift tolerance, RT correction)
  - `paradigm-camera.js` — front camera recording (OPFS chunked, 30s intervals)
  - `end-screen.js` — unified completion screen + LocalPack ZIP download
  - `data-sync.js` — server save + localStorage backup + download fallback (ES module, used by TMT/Visuospatial)
- **Styling**: `css/common.css` — unified button/feedback/probe styles across all paradigms
- **Data**: POST to `/api/save`, download ZIP via `/api/download/{sid}`

### Data Safety Architecture (as of 2026-04-09 audit)
- All `saveData()` calls are **awaited** before `showEndScreen()` — no data loss on early page close
- All fetch calls use `safeFetch()` with **15s AbortController timeout** — weak WiFi triggers fallback download
- All multi-file saves check **resp.ok on every fetch** — partial saves trigger fallback
- All paradigms have **`_dataSaved` double-save guard** — prevents duplicate data on accidental re-trigger
- **Three-finger double-tap** exits paradigm (via `touch-hardening.js`) — saves checkpoint before closing
- **Launcher auto-fullscreen** on subject ID confirmation
- Popup blocker detection on paradigm launch

### Unified Visual Standards (as of 2026-04-09)
- **Response buttons**: `#B0B0B0` grey, `2px solid #707070`, 12px radius, 42px font, `#8C8C8C` on press
- **Practice feedback**: Non-punitive — "✓ 对了" (green `#66BB6A`) / "没关系，再看仔细" (red `#E57373`), 72px, 2000ms auto-advance. No red X, no "错误" text.
- **Attention probes**: 1-9 Likert scale at natural break points (15 probes across full battery, ~1.2 min total). Defined in `lib/attention-probe.js` + `css/common.css .attn-probe-btn`.
- **Trial progress**: Right-top corner, block-level count (e.g., "1/20"), practice shows "练习 1/4"
- **Flanker transition**: White↔black background with 0.5s CSS ease transition
- **Standards docs**: `UX图片/标准_练习阶段.md`, `UX图片/标准_语音脚本规范.md`, `UX图片/标准_指导语架构模板.md`

### Web Data Output
- CSV (UTF-8 BOM) per paradigm, saved to `server/data/{subject_id}/{paradigm}/`
- JSON summary with SDT metrics (A', β) where applicable (SART, N-back, VSTMB, Eyetracking)
- Audio recordings (WebM) for speech paradigm
- Video recordings (WebM) via ParadigmCamera for all paradigms (optional, enabled in launcher)
- Canvas screenshots (PNG) for clock drawing
- TMT: 4 CSV types (summary, segments, raw_path, event_marker)
- Attention probe data collected in `window._attentionProbeData` array

### Server Maintenance
```bash
ssh zju-psych-11@10.130.12.71
cd ~/projects/cognitive-assessment
tar xzf ~/web-battery-deploy.tar.gz
bash stop.sh && bash start.sh
tail -f /tmp/cognitive-assessment.log
# Download data: http://10.130.12.71:8082/api/download/{subject_id}
```

---

## Eye Tracking Redesign (VPC)

The current naturalistic gaze paradigm (`paradigms/eyetracking/`) will be redesigned as a **Distributed Decay Slope VPC** paradigm. See:
- `眼动多模态/01_VPC总方案_分布式衰减斜率设计.md` — full design spec
- `眼动多模态/数据保存标准_新范式必读.md` — data safety requirements for new implementation

---

## PsychoPy Desktop Version (legacy)

Not actively developed. Web version supersedes for all field testing.

```bash
cd VSTMB/VSTMB && python main.py
cd N-back/N-back/run && python run_all.py
cd SART/SART/范式程序 && python main.py
cd TMT/初版TMT/run最终 && python run_all_updated.py
cd Flanker/实验程序 && python flanker_psychopy.py
```

## Key Design Rules

- **N-back**: B4 (2-back) removed — elderly cannot complete it. B1-B3 only. Adaptive gating code preserved but B4 gate conditions naturally skip.
- **Buttons**: All paradigms use unified grey (#B0B0B0) response buttons. No colored buttons (avoids Stroop interference in VSTMB).
- **Feedback**: Non-punitive practice feedback per `UX图片/标准_练习阶段.md`. No red X, no "错误", no accuracy percentages shown to participants.
- **Instructions**: Will be replaced with unified image-based instruction pages (`UX图片/修改后的规则png/`) + TTS voice guidance.
- **Eye-tracking**: Being redesigned as VPC distributed decay slope paradigm (see `眼动多模态/`).
- **Touch input**: `TouchHardening.correctRT()` corrects RT to pointerdown moment (cognitive decision time, not finger release). Applied in Flanker, SART, N-back, VSTMB, Interpersonal.
- **Audit trail**: Full 30-issue audit in `4月6日 反馈/代码审计_30个问题.md`
- Development docs in `开发文档/`
- Ethics docs in `伦理审查/` (v3.1, finalized 2026-03-27)
