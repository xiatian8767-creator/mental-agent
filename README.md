# 多模态情绪分析 Agent

本项目实现了技术文档要求的输入模块与单模态分析模块。文本、图片和音频 Agent 共用同一份分析 JSON，并分别把结果写回自己的字段。

## 已完成内容

- `Input`：读取 `data/samples/<id>.json`，校验输入并生成 `data/analysis/<id>.json`。
- `TextAnalysis`：分析文本内容，生成文本描述、分析过程和情绪标签。
- `VisualAnalysis`：读取本地图片，生成视觉描述、分析过程和情绪标签。
- `AudioAnalysis`：读取本地音频，生成音频描述、分析过程和情绪标签。
- 三个 Agent 均从根目录 `.env` 读取接口地址、API Key 和模型名称。
- 当某个模态输入为 `null` 时，对应 Agent 会直接跳过，不调用接口。
- 模型只返回分析内容，JSON 文件由 Python 程序负责更新。
- 根目录 `test.py` 提供三个模态 Agent 的最简调用示例。

当前验证情况：

- 输入模块已验证，可以生成共享分析文件。
- 文本 Agent 已使用实际接口运行成功。
- 图片 Agent 已使用 `media/images/1.jpg` 和实际接口运行成功。
- 音频 Agent 已验证空输入跳过逻辑；由于当前样例没有音频文件，尚未进行真实音频接口测试。

## 项目结构

```text
mental_agent/
├─ input.py
├─ test.py
├─ README.md
├─ requirement.txt
├─ .env
├─ .gitignore
├─ analysis/
│  ├─ text_analysis.py
│  ├─ visual_analysis.py
│  ├─ audio_analysis.py
│  └─ prompt.json
├─ data/
│  ├─ samples/
│  │  └─ 1.json
│  └─ analysis/
│     └─ 1.json
└─ media/
   └─ images/
      └─ 1.jpg
```

## 环境要求

- 建议使用 Python 3.10 或更高版本。
- 当前项目已在 Python 3.12 上测试。
- 代码仅使用 Python 标准库，不需要安装第三方 Python 包。

如需统一执行依赖安装命令，可以运行：

```powershell
$pythonExe = "C:\Users\15072\AppData\Local\Programs\Python\Python312\python.exe"
& $pythonExe -m pip install -r requirement.txt
```

如果项目复制到了另一台电脑，请把 `$pythonExe` 改成那台电脑上的 Python 可执行文件路径。

## 配置接口

在项目根目录创建 `.env`，填写以下配置：

```dotenv
OPENAI_API_KEY=<你的 API Key>
OPENAI_BASE_URL=<兼容 OpenAI 接口的基础地址>
OPENAI_TEXT_MODEL=<文本模型名称>
OPENAI_VISUAL_MODEL=<视觉模型名称>
OPENAI_AUDIO_MODEL=<音频模型名称>
```

`.env` 已加入 `.gitignore`，不要把真实 API Key 提交到 GitHub。

## 使用方法

### 1. 准备输入样本

在 `data/samples/1.json` 中填写文本、图片相对路径和音频相对路径。暂时没有的模态使用 `null`。

如果只想单独运行输入模块，可以执行：

```powershell
$pythonExe = "C:\Users\15072\AppData\Local\Programs\Python\Python312\python.exe"
& $pythonExe -c "from input import Input; Input('data/samples/1.json', 'data/analysis').run()"
```

数据流如下：

```text
data/samples/1.json
        ↓
      Input
        ↓
data/analysis/1.json
        ↓
TextAnalysis / VisualAnalysis / AudioAnalysis
        ↓
更新 data/analysis/1.json 中各自的分析字段
```

### 2. 运行完整示例

```powershell
$pythonExe = "C:\Users\15072\AppData\Local\Programs\Python\Python312\python.exe"
& $pythonExe test.py
```

`test.py` 会先调用 `Input` 初始化共享分析文件，再依次调用三个模态 Agent。当前完整调用方式为：

```python
from analysis.audio_analysis import AudioAnalysis
from analysis.text_analysis import TextAnalysis
from analysis.visual_analysis import VisualAnalysis
from input import Input

Input(
    samples_path="data/samples/1.json",
    output_dir="data/analysis/",
).run()

analysis_path = "data/analysis/1.json"

TextAnalysis(analysis_path=analysis_path).run()
VisualAnalysis(analysis_path=analysis_path).run()
AudioAnalysis(analysis_path=analysis_path).run()
```

运行完成后，在 `data/analysis/1.json` 查看分析结果。该目录中的运行结果默认不会提交到 Git。

