# Codex Image

生成和修改图片的 Codex skill。

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

自动读取本机 Codex 配置中的接口地址。API Key 需通过启动器进程可读取的 `OPENAI_API_KEY` 环境变量提供；不会自动读取 Codex 登录凭据。

## 平台支持

支持以下系统，均附带预编译程序，无需自行编译或安装 Python 包：

| 系统 | 架构 | 启动入口 |
| --- | --- | --- |
| macOS | Apple Silicon / Intel | `scripts/run.sh` |
| Windows | x64 / ARM64 | `scripts/run.cmd` |

需要 Python 3.11+；macOS 启动脚本也会尝试使用本机 Codex 附带的 Python。Windows 需要可通过 `py -3`、`python` 或 `python3` 调用的 Python 3.11+。也可以直接用 Python 3.11+ 运行 `scripts/run.py`。

所有入口都会按本机系统和架构选择程序，并读取 `CODEX_HOME/config.toml`（默认 `~/.codex/config.toml`，Windows 为用户目录下的 `.codex\config.toml`）中的服务地址；没有配置地址时依次使用 `OPENAI_BASE_URL`、`OPENAI_API_BASE`。API 服务需要支持所选图片模型。

更新已安装版本时，可让 Codex 重新安装本仓库中的 skill。

[MIT License](LICENSE)
