# MyAgent

MyAgent 是一个基于 Python 的智能体（Agent）框架，支持多种推理与执行策略，并具备可扩展的技能管理机制。

## 核心特性

- **ReAct**: 支持推理（Reasoning）与行动（Acting）交替执行的经典范式。
- **Plan-and-Execute**: 支持先规划后执行的任务拆解模式。
- **上下文压缩**: 内置上下文管理机制，优化长上下文场景下的性能。
- **Skills**: 支持模块化技能扩展，增强智能体能力边界。

## 环境要求

由于智能体底层依赖 Bash 环境，目前仅支持 **Linux** 系统。

## 安装与运行

### 1. 安装 uv
本项目使用 `uv` 进行依赖管理与运行。若未安装，请参考官方文档进行安装：https://docs.astral.sh/uv/

### 2. 配置文件
在使用前，需要准备一个 JSON 格式的配置文件（例如 `config.json`），填入模型服务的相关信息：

```json
{
    "provider": "deepseek",
    "key": "你的 API Key",
    "url": "https://api.deepseek.com/v1/chat/completions",
    "model": "模型名称"
}
```

### 3. 启动运行
使用以下命令启动智能体：

```bash
uv run python -m myagent.main --config ${CONFIG} --log ${LOG} --query "查一下明天常州市的天气"
```

**参数说明：**
- `--config`: 指定配置文件的路径（例如 `config.json`）。
- `--log`: 指定日志文件的保存路径（例如 `log.jsonl`）。
- `--query`: 输入给智能体的自然语言指令。

### 4. 可视化监控

为了便于调试与追踪，项目支持将运行日志以可视化方式展示。

**操作步骤：**

1.  **启动本地服务**
    在项目根目录下运行以下命令以启动一个简单的 HTTP 服务器：
    ```bash
    uv run python -m http.server
    ```

2.  **查看日志**
    在浏览器中访问终端提示的地址（默认为 `http://0.0.0.0:8000`），在页面中找到并点击 `log.html` 文件即可查看智能体的实时运行轨迹。

> **注意**：请确保当前目录下已存在运行智能体时生成的 `log.jsonl` 文件。


## 技能管理 (Skills)

MyAgent 支持通过 Skill 扩展功能。技能包默认安装在用户目录下的 `~/.agents/skills` 路径中。