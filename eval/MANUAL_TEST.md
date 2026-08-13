# 人工测试清单（BB Boom 劝学系统 · 学习/娱乐分类优化）

目标：在自动化评测（旧 54.2% → 新 100%，48 个代表性场景）之后，由人工用真实/拟真场景再验一遍。

## 一、快速验证（无需启动完整客户端）

用 `cli_test.py` 输入窗口标题即可看判定与明细，并自动对照旧分类器：

```bash
cd D:\LearningApp
python eval/cli_test.py --title "微信" --process weixin.exe
python eval/cli_test.py --title "B站 考研数学 网课" --process chrome.exe
python eval/cli_test.py --title "英雄联盟 赛事直播" --process chrome.exe
python eval/cli_test.py --title "LeetCode 两数之和" --process pycharm64.exe
python eval/cli_test.py --title "" --process explorer.exe
```

多个进程用逗号：`--process "chrome.exe,idea64.exe"`

## 二、必测场景清单

| # | 场景 | 命令（--title / --process） | 期望新判定 |
|---|------|------------------------------|-----------|
| 1 | 浏览器-网课 | `--title "微积分 网课 bilibili" --process chrome.exe` | study |
| 2 | 浏览器-知乎学习 | `--title "知乎 高考数学解题思路" --process chrome.exe` | study |
| 3 | 浏览器-抖音娱乐 | `--title "抖音 搞笑视频" --process chrome.exe` | entertainment |
| 4 | 浏览器-编程刷题 | `--title "LeetCode 两数之和" --process chrome.exe` | study |
| 5 | IDE 写代码 | `--title "main.py - Visual Studio Code" --process code.exe` | study |
| 6 | IDEA 写代码 | `--title "MyProject - IntelliJ IDEA" --process idea64.exe` | study |
| 7 | 游戏客户端 | `--title "League of Legends" --process leagueclient.exe` | entertainment |
| 8 | Steam | `--title "Steam" --process steam.exe` | entertainment |
| 9 | 微信聊天 | `--title "微信" --process weixin.exe` | entertainment |
| 10 | 桌面空闲 | `--title "" --process explorer.exe` | idle |
| 11 | YouTube 学习视频 | `--title "YouTube 机器学习教程" --process chrome.exe` | study |
| 12 | YouTube 娱乐视频 | `--title "YouTube 搞笑视频" --process chrome.exe` | entertainment |
| 13 | B站 游戏直播 | `--title "bilibili 游戏直播" --process bilibili.exe` | entertainment |
| 14 | 文件名含 game 但写代码 | `--title "game_utils.py - Visual Studio Code" --process code.exe` | study |

> 重点观察：第 1/2/11 这类“浏览器+学习”场景，旧分类器会误判为娱乐或空闲，新分类器应判 study；
> 第 14 这类“标题含娱乐词但前台是 IDE”的场景，新分类器应判 study（进程信号优先）。

## 三、真实端到端人工测试（运行完整客户端）

```bash
pip install -r requirements.txt   # 含 pyautogui / opencv / onnxruntime / psutil / cryptography
python main.py
```
观察：
- 打开网课/文档/IDE → 连续 3 次一致后是否**不**误弹“娱乐”警告（旧版会误弹）。
- 打开游戏/视频 → 是否如期弹警告。
- 看 `client_activity_logs.db` 与控制台日志的融合明细。

## 四、开启视觉/语言模型做真实多模态测试（可选）

默认关闭。要测真实 VLM/文本LLM 兜底：

1. 本机安装 Ollama：`https://ollama.com`，并拉取模型：
   ```bash
   ollama pull moondream        # 端侧 VLM（轻量，优先）
   ollama pull qwen2.5:1.5b     # 本地文本 LLM
   ```
2. 改 `config.json`：
   - `"enable_text_llm": true`（文本 LLM 判级）
   - `"enable_vlm": true`（仅“不确定”样本截屏交给 VLM；截图不出本机）
3. 重启 `python main.py`，对边界/模糊场景（如全屏应用、标题无信息）观察是否触发 VLM 兜底并给出更准判定。
4. 若本机无 GPU/算力弱：保持 `enable_vlm=false`，仅用文本信号路径（本次评测已覆盖）。

## 五、反馈闭环

误报/漏报时客户端弹窗可选“误报/漏报”，结果写入服务端 `feedback` 表
（`detected_activity` vs `actual_activity`）。后续可把这些真实标注沉淀为评测集，
持续扩充 `eval/samples.json` 做回归。
