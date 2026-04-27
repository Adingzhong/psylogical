# GitHub 协作版上传说明

## 当前策略

GitHub 首次协作版以“能读懂、能审核、能用 Codex 辅助检查”为优先目标。

优先上传：

- 交接文档和 README 导航；
- 当前 Web 平台的核心代码；
- 范式流程相关的 `.js`、`.html`、`.csv`、`.json`；
- 原始开发文档和轻量证据文件；
- 4月27日分工、下发话术和时间节点文件。

暂不在首次推送中一次性上传：

- 大体积刺激图片全集；
- 大体积音频全集；
- 眼动多模态大素材；
- 备份音频、测试产物、缓存；
- 被试/测试数据、日志、私钥、本地数据库。

## 原因

本地完整仓库包含大量图片、音频、PPT/PDF 和旧版材料。一次性推送会形成数百 MB 的 Git pack，容易超时，也不利于后续协作查看。

首次协作版先保证大家能做：

- 范式参数审核；
- 代码和 CSV 输出字段检查；
- 原始设计与当前实现对照；
- 负责人分工和科研验证。

大型刺激材料如确实需要上 GitHub，建议后续单独处理：

- 分范式分批提交；
- 或使用 Git LFS；
- 或作为 GitHub Release 附件；
- 或保留在网盘/本地，只在 README 中索引。

## 不应上传的内容

- `web-battery/server/data/`
- `web-battery/server/logs/`
- `web-battery-https-certs/*.key`
- `4月19日 修改/hospital_query/data/`
- `伦理审查/` 中的正式伦理材料
- `社会认知/RMET【以此为基准】/result/*.csv`
- `node_modules/`
- `.pw-browsers/`
- `__pycache__/`
- `.DS_Store`
