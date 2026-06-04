# MyAgent

MyAgent 是一个基于 Python 的智能体（Agent）框架，支持多种推理与执行策略，并具备可扩展的技能管理机制。

## 核心特性

- **ReAct**: 支持推理（Reasoning）与行动（Acting）交替执行的经典范式。
- **上下文压缩**: 内置上下文管理机制，优化长上下文场景下的性能。
- **Skills**: 支持模块化技能扩展，增强智能体能力边界。
- 多渠道消息接入与分发：当前已支持命令行接口（CLI）及 Discord 机器人两种交互方式。

## 环境要求

由于智能体底层依赖 Bash 环境，目前仅支持 **Linux** 系统。

## 安装与运行

### 1. 安装 uv
本项目使用 `uv` 进行依赖管理与运行。若未安装，请参考官方文档进行安装：https://docs.astral.sh/uv/

### 2. 配置文件
在使用前，需要准备一个 JSON 格式的配置文件（例如 `config.json`），填入模型服务的相关信息：

```json
{
    "llm": {
        "choice": "dsv4pro",
        "profiles": {
            "dsv4pro": {
                "provider": "deepseek",
                "key": "你的 API key",
                "url": "https://api.deepseek.com/v1/chat/completions",
                "model": "deepseek-v4-pro"
            }
        }
    },
    "channels": {
        "console": {
            "log": "logs"
        },
        "discord": {
            "token": "你的 Discord 机器人 Token",
            "log": "logs",
            "proxy": "你的代理地址"
        }
    }
}
```

### 3. 启动运行
使用以下命令启动智能体：

```bash
# 启动 CLI 渠道
uv run python -m myagent.channels.console --config ${CONFIG}
# 启动 Discord 渠道
uv run python -m myagent.channels.discord --config ${CONFIG}
```

**参数说明：**
- `--config`: 指定配置文件的路径（例如 `config.json`）。

## 技能管理 (Skills)

MyAgent 支持通过 Skill 扩展功能。技能包默认安装在用户目录下的 `~/.agents/skills` 路径中。