# Codex Image

通过第三方兼容图片接口生成和修改图片的 Codex skill。

## 安装

向 Codex 发送：

```text
请安装 https://github.com/123aliez/codex-image 中的 skill，技能位于仓库根目录，安装名称为 codex-image。
```

## 使用

```text
$codex-image 画一幅雪山插画。
$codex-image 用闪焰，2K，生成一张海边日出。
$codex-image 修改这张图片，只替换背景，保留人物和服装。
```

默认使用 Image 2.5、1K、auto 质量。支持 Image 2、Image 2.5、闪焰、日耀和 Grok，可在对话中切换模型及 1K / 2K / 4K。

支持多张参考图、局部编辑和批量生成。修改结果另存，保留原图。

自动读取本机 Codex 配置中的第三方接口地址，API Key 从环境变量读取。

## 平台支持

支持以下系统，均附带预编译程序，无需自行编译或安装 Python 包：

| 系统 | 架构 | 启动入口 |
| --- | --- | --- |
| macOS | Apple Silicon / Intel | `scripts/run.sh` |
| Windows | x64 / ARM64 | `scripts/run.cmd` |

需要 Python 3.11+；macOS 启动脚本也会尝试使用本机 Codex 附带的 Python。Windows 需要可通过 `py -3`、`python` 或 `python3` 调用的 Python 3.11+。也可以直接用 Python 3.11+ 运行 `scripts/run.py`。

所有入口都会按本机系统和架构选择程序，并读取 `CODEX_HOME/config.toml`（默认 `~/.codex/config.toml`，Windows 为用户目录下的 `.codex\config.toml`）。接口地址只使用所选 `model_provider` 的 `base_url`，尊重默认 `profile`；未配置地址会报错。

密钥使用该服务商 `env_key` 指定的环境变量，未指定时默认 `OPENAI_API_KEY`。优先读取当前进程；如果进程没有继承变量，Windows 会依次读取用户、系统环境变量，macOS 会读取当前登录会话的 launchd 环境变量。每次运行都会重新读取，无需修改 skill。

Windows 可在系统设置中配置用户或系统环境变量。macOS 从桌面打开的应用通常不会读取 `.zshrc`，应通过本机 `launchctl setenv` 设置当前登录会话的变量，或从已设置变量的终端启动 Codex；launchd 变量不保证重启后保留。仅在另一个对话里临时设置的变量不会自动共享。

密钥只来自环境变量，不读取 `auth.json`、登录令牌或配置中的明文密钥。API 服务需要支持所选图片模型。

更新已安装版本时，可让 Codex 重新安装本仓库中的 skill。

[MIT License](LICENSE)
