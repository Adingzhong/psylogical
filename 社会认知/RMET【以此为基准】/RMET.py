# ==========================================
# 模块 1：导入必要的外部库
# ==========================================
from psychopy import visual, core, event, gui, data
import pandas as pd
import os
import sys
import csv

# ==========================================
# 模块 2：实验初始化
# ==========================================
# 1. 收集被试信息
exp_info = {'被试编号': '001'}
dlg = gui.DlgFromDict(dictionary=exp_info, title='RMET 实验')
if not dlg.OK:
    core.quit()

# 2. 获取当前脚本所在文件夹的路径
current_dir = os.path.dirname(os.path.abspath(__file__))

# 3. 基于当前路径加载素材和结果文件夹 
material_dir = os.path.join(current_dir, "marterial")
image_dir = os.path.join(material_dir, "image")
excel_path = os.path.join(material_dir, "options_new.xlsx")
result_dir = os.path.join(current_dir, "result")

# 确保结果文件夹存在
if not os.path.exists(result_dir):
    os.makedirs(result_dir)

# 数据保存路径
filename = os.path.join(result_dir, f"RMET_{exp_info['被试编号']}.csv")

# ==========================================
# 模块 3：屏幕与刺激组件创建
# ==========================================
# 自动使用电脑屏幕分辨率
win = visual.Window(fullscr=True, color='white', units='pix')
mouse = event.Mouse(win=win)

# 预设刺激组件
fixation = visual.TextStim(win, text='+', color='black', height=100)
stim_image = visual.ImageStim(win, pos=(0, 200))
# 3. 选项按钮 (文字放大至 60，并添加矩形边框)
# 按钮尺寸与位置参数
btn_size = (380, 120)  # 按钮框的大小
text_h = 60           # 文字大小
# 定义三个按钮的中心坐标
pos_list = [(-450, -200), (0, -200), (450, -200)]

# 创建矩形边框 (边框颜色为灰色，模拟按键)
buttons = [visual.Rect(win, width=btn_size[0], height=btn_size[1], 
                       pos=p, lineColor='black', lineWidth=3, fillColor='#E0E0E0') for p in pos_list]
# 创建选项文字
opt_stims = [visual.TextStim(win, text='', pos=p, color='black', height=text_h) for p in pos_list]

#反馈与指导语
feedback_text = visual.TextStim(win, text='', color='black', height=80)
instruction_text = visual.TextStim(win, text='', color='black', height=60, wrapWidth=1400)

# ==========================================
# 模块 4：核心功能函数定义 
# ==========================================

def show_instruction(text_content):
    instruction_text.text = text_content
    instruction_text.draw()
    win.flip()
    keys = event.waitKeys(keyList=['space', 'escape'])
    if 'escape' in keys:
        win.close()
        core.quit()

def run_trial(trial_data, is_practice=False):
    if 'escape' in event.getKeys(keyList=['escape']):
        return "QUIT"

    # 1. 注视点 (2s)
    fixation.draw()
    win.flip()
    core.wait(2.0)
    
    # 2. 呈现刺激与选项
    # 图片路径拼接
    img_name = str(trial_data['stimulation']) + ".jpg"
    stim_image.image = os.path.join(image_dir, img_name)

    opts_content = [trial_data['option1'], trial_data['option2'], 
                    trial_data['option3']]
    
    correct_answer = trial_data['answer']

    for i in range(3):
        opt_stims[i].text = opts_content[i]

    stim_image.draw()
    for btn in buttons: btn.draw()
    for txt in opt_stims: txt.draw()
    win.flip()



    # 3. 反应阶段 (改为不限时)
    mouse.clickReset()
    timer = core.Clock()
    response, rt, is_correct = None, None, 0
    feedback_msg = ""

    while True:
        if 'escape' in event.getKeys(keyList=['escape']):
            return "QUIT"
            
        if mouse.getPressed()[0]:
            for i in range(3):
                # 检查是否点击在矩形框内
                if mouse.isPressedIn(buttons[i]):
                    response = opt_stims[i].text
                    rt = timer.getTime()
                    break
            if response: break
    
    if response == correct_answer:
        is_correct = 1
        feedback_msg = "正确" 
    elif response:
        is_correct = 0
        feedback_msg = "错误" 

    # 4. 反馈阶段 (仅练习试次) 
    if is_practice:
        feedback_text.text = feedback_msg
        feedback_text.draw()
        win.flip()
        core.wait(2.0)
        
    # 5. ITI (1s)
    win.flip()
    core.wait(1.0)
    
    return {'response': response, 'rt': rt, 'is_correct': is_correct}

# ==========================================
# 模块 5：实验主流程
# ==========================================
# 读取 Excel 
df = pd.read_excel(excel_path).reset_index(drop=True)
practice_data = df[df['order'] == 'practice'].to_dict('records')
formal_data = df[df['order'] != 'practice'].to_dict('records')

# 创建表头并预初始化文件
sample_trial = {**formal_data[0], 'response': None, 'rt': None, 'is_correct': None}
header = list(sample_trial.keys())
with open(filename, 'w', newline='', encoding='utf_8_sig') as f:
    writer = csv.DictWriter(f, fieldnames=header)
    writer.writeheader()

# 总指导语
show_instruction("接下来，您将看到一系列人的眼睛部分图片。\n"
                 "每张图片下面会出现 3 个词语，\n"
                 "描述其可能的想法或感受。\n"
                 "请根据直觉，又快又准地点击最符合的一项。\n\n"
                 "（按空格键继续）")

# 练习环节
show_instruction("现在先做 1 道练习题。\n"
                 "请尽可能按照第一直觉作答。\n\n"
                 "（按空格键开始）")

for t in practice_data:
    res = run_trial(t, is_practice=True)
    if res == "QUIT":
        win.close()
        core.quit()


# 正式环节
show_instruction("现在进入正式游戏环节！请又快又准地作答。\n\n（按空格键开始）")
for t in formal_data:
    res = run_trial(t, is_practice=False)
    
    if res == "QUIT":
        break # 遇到退出信号，跳出循环进入结束语
    
    # 实时写入数据
    combined_info = {**t, **res}
    with open(filename, 'a', newline='', encoding='utf_8_sig') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writerow(combined_info)

# ==========================================
# 模块 6：保存与退出
# ==========================================
instruction_text.text = "游戏结束，感谢参与！"
instruction_text.draw()
win.flip()
core.wait(2.0) # 等待3秒后自动关闭

win.close()
core.quit()