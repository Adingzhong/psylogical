# tmt

连线测试 / TMT 当前 Web 实现目录。交接对象：黄朝琮。

主要文件：

- `tmt.html`：范式页面和画布布局。
- `tmt.js`：任务顺序、触控连线、错误处理、计时、stall/skip 和数据记录。
- `layouts/`：A0、B2、B1、A1、B3、B4 的节点布局 JSON。
- `img/`：页面内辅助图片。

相关材料：

- `web-battery/stimuli/tmt-fruits/`
- `开发文档/TMT范式开发文档.md`
- `TMT/初版TMT/`
- `4月6日 反馈/03_TMT.md`
- `UX图片/脚本/脚本_TMT.md`
- `按钮修正/适老化触控交互文献调研.md`

重点审核：

- 正式任务取消 40 秒硬上限是否接受；
- stall/skip 是否影响完成时间指标；
- B4 固定 layout 1 是否破坏平衡；
- 当前 layout 节点数以哪个版本为准。
