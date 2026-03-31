# DESK Course 学习进度助手

一个常驻系统托盘的课程学习进度小组件。

支持从 .ics 课表一键导入，自动统计每门课截至当天总课时，并通过手动加减维护已上课数。

## 使用手册

本程序按“只转发 exe 文件”交付，用户运行只需要 exe 文件和课程 .ics 文件在同一个文件夹。

### 1. 准备文件

1. 新建任意文件夹（建议非系统受限目录，如桌面或 D 盘目录）。
2. 放入以下文件：
- DESKCourseAssistant.exe
- 你的课程表 .ics 文件（任意文件名，推荐 schedule.ics）
- ## 如何得到.ics?: 使用【wakeup课程表】软件，根据提示导入课表，点击右上角箭头选择【导出为日历文件】即可。
![9628041eb9cf9f1931d893de8219779d](https://github.com/user-attachments/assets/84c5b792-831a-40c3-bfa8-c53a1898a0b4)

### 2. 首次运行

1. 双击 DESKCourseAssistant.exe。
2. 程序启动后会常驻托盘，主窗口可通过托盘恢复。
3. 如果尚未导入课表，界面会提示 未检测到课程表。

### 3. 导入课表

1. 在系统托盘找到本程序图标并右键。
2. 点击 导入课表。
3. 若已存在课表数据，会弹出覆盖确认，点击 是 后继续。
4. 导入成功后会自动刷新课程列表。

### 4. 日常使用

1. 在课程项上右键可执行：
- 进度 +1
- 进度 -1
2. 在设置中可调整：
- 开机自启动
- 课程显示/隐藏
- 启动时侧边吸附隐藏

### 5. 数据文件说明

程序运行后会在 exe 同目录自动生成或更新以下文件：

1. 课表相关
- schedule_summary.txt
- summary_schedule.txt
- schedule_summary_ansi.txt

2. 用户数据
- data/settings.json
- data/learned_progress.json

说明：
- settings.json 保存窗口与功能设置。
- learned_progress.json 保存你手动维护的已上课数。

### 6. 常见问题

1. 只有 exe + .ics 能运行吗？
- 可以。放在同一文件夹后，运行 exe 并从托盘点击 导入课表 即可。

2. 导入后为什么提示覆盖？
- 程序检测到已有课表时会要求确认，防止误操作覆盖。

3. 已上课数会不会被自动改掉？
- 不会。自动更新的是总课时（截至当天），已上课数仅由你手动修改。

4. 为什么没有任务栏图标？
- 这是产品设计行为，开发者希望任务栏干净简洁一点，遂程序使用托盘常驻，不在任务栏显示图标。

## 功能介绍

1. 课表导入
- 在系统托盘右键菜单点击 导入课表，即可自动读取 exe 同目录下的 .ics 文件并转换为课表数据。

2. 课表覆盖确认
- 如果当前已有课表，导入前会弹窗确认，避免误覆盖旧数据。

3. 同名课程自动合并
- 同名课程固定按课程名合并为一门课显示与统计。

4. 自动更新总课时
- 每天自动更新的是总课时（截至当天），不是已上课数。

5. 已上课数手动维护
- 已上课数仅支持手动 +1 / -1 修改，且会长期持久化保存。

6. 完成率与进度条
- 根据已上课数与截至当天总课时自动计算完成率并展示。

7. 常驻托盘与侧边吸附
- 支持显示主界面、侧边吸附隐藏、退出。
- 应用不在任务栏显示图标。

8. 设置功能
- 支持开机自启动。
- 支持课程显示/隐藏。
- 支持启动时侧边吸附隐藏。


## 开发者打包命令

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

打包输出目录：dist

## 开发者构建与调试说明

### 1. 环境准备

1. Python 版本：3.11（建议与打包环境一致）。
2. 在项目根目录安装依赖：

```powershell
python -m pip install -r requirements.txt
```

3. 若你使用 conda，可先激活环境再安装依赖：

```powershell
conda activate tableschedule
python -m pip install -r requirements.txt
```

### 2. 源码运行（开发调试）

在项目根目录执行：

```powershell
python app/main.py
```

说明：
1. 程序会以项目根目录作为运行根目录。
2. 运行后会读取根目录的课表摘要文件，优先顺序如下：
- schedule_summary.txt
- summary_schedule.txt
3. 若以上文件都不存在，程序不会退出，会在界面提示未检测到课程表。

### 3. 课表导入链路（关键逻辑）

1. 用户在托盘菜单点击 导入课表。
2. 程序在 exe/运行目录中查找 .ics 文件（优先 schedule.ics、schedule_ansi.ics，其次任意 .ics）。
3. 若已有课表数据，先弹窗确认是否覆盖。
4. 调用 Export-IcsSchedule.ps1 生成：
- schedule_summary.txt
- schedule_summary_ansi.txt
5. 程序同步生成 summary_schedule.txt（兼容别名）。
6. 重新加载课程并刷新 UI。

### 4. 代码框架

核心目录：

```text
app/
	main.py              # 启动入口，解析运行目录/打包目录
	ui_main.py           # 主窗口、托盘菜单、导入课表流程
	ui_course_item.py    # 单课程卡片与右键 +1/-1
	parser.py            # 解析 schedule_summary.txt
	progress_engine.py   # 进度计算（截至当天总课时、完成率）
	settings.py          # 本地设置与已上课数持久化
	autostart.py         # Windows 开机自启动注册

Export-IcsSchedule.ps1 # .ics -> schedule_summary.txt 转换脚本
build_exe.ps1          # 一键打包脚本
DESKCourseAssistant.spec
```

### 5. 数据流与状态持久化

```text
.ics --(Export-IcsSchedule.ps1)--> schedule_summary.txt
schedule_summary.txt --(parser.py)--> Course[]
Course[] + learned_progress.json --(progress_engine.py)--> CourseProgress[]
CourseProgress[] --(ui_main.py/ui_course_item.py)--> Widget UI
```

持久化文件：
1. data/settings.json：窗口尺寸、课程显隐、启动偏好、最近刷新日期。
2. data/learned_progress.json：用户手动维护的已上课数。

### 6. 打包流程与交付要点

1. 打包脚本会将以下文件打入单文件 exe：
- schedule_summary.txt
- Export-IcsSchedule.ps1
2. 打包完成后会输出 dist/DESKCourseAssistant.exe。
3. 最终交付给用户时，用户仅需：
- DESKCourseAssistant.exe
- 课程 .ics 文件（同目录）

## License

This project is licensed under the DESK Course Assistant Non-Commercial License v1.0.

1. Non-commercial use, modification, and redistribution are allowed under the license terms.
2. Commercial use requires prior written permission from the copyright holder.
3. The software is provided AS IS, without warranty, and with limitation of liability.

See [LICENSE](LICENSE) for the full text.
