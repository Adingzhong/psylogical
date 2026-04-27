# Flanker PsychoPy 实验程序

主程序文件：`flanker_psychopy.py`

## 运行方式

在安装了 `PsychoPy` 的 Python 环境中运行：

```bash
python flanker_psychopy.py
```

也可以直接用 PsychoPy Coder 打开并运行这个脚本。

## 当前实现

- 按开发文档实现了练习、正式实验、Block 间休息评分
- 保留了 `is_popout` 和 `popout_type` 两个输出字段
- 正式实验为 `2 Block × 24 trial`
- 练习为 `6 trial`，正确率低于 `70%` 自动重做
- 记录了反应时、超时、过快反应和 `iti_response`

## 输出文件

程序运行后会在 `data` 子文件夹中生成：

- `*_flanker_trials_时间戳.csv`：逐试次数据
- `*_flanker_ratings_时间戳.csv`：Block 1 后的专注度评分

## 当前默认设置

- 左反应键：`q`
- 右反应键：`p`
- 页面继续键：`space`
- 退出键：`escape`
- 默认全屏
- 启动时会弹窗填写被试编号，若留空则自动按时间戳生成
- 练习最多 3 轮，前 2 轮需要达到 70%，第 3 轮结束后直接进入正式实验
- `Esc` 在任意时刻都可正常退出，不再作为报错中断

如果你后面要改成手柄、串口按钮盒或 EEG 触发版本，可以在这个脚本基础上继续改。
