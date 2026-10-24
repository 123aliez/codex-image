# Codex Image

通过本机 Codex 的 API 配置生成和编辑图片的 Skill，调用名为 `$codex-image`。

每次启动时自动读取 `$CODEX_HOME/config.toml`（默认 `~/.codex/config.toml`），使用当前 `model_provider` 对应的 `base_url`；配置了默认 `profile` 时，采用该 profile 选择的服务商。密钥复用环境变量 `OPENAI_API_KEY`，无需另设 `CODEX_API_URL` 或 `CODEX_API_KEY`。修改本机配置后，下次调用自动生效。

当前配置启动器支持 macOS Apple Silicon 和 Intel，使用 Python 3.11+ 标准库，或 Codex 自带的 Python 运行时，无需额外安装 Python 包。

## 安装

向 Codex 发送：

```text
请安装 https://github.com/123aliez/codex-image 中的 Skill，技能位于仓库根目录，安装名称为 codex-image。
```

也可使用 Codex 自带的安装脚本：

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo 123aliez/codex-image --path . --name codex-image
chmod +x ~/.codex/skills/codex-image/scripts/run.sh \
  ~/.codex/skills/codex-image/bin/codex-image2-5-darwin-*
```

安装后在下一轮对话中使用 `$codex-image`。

## 使用

```text
$codex-image 用 Image 2，1K，画一幅雪山插画。
$codex-image 用闪焰，2K，生成一张海边日出。
$codex-image 修改这张图片，只替换背景，保留人物和服装。
```

默认模型为 `gpt-image-2.5`，尺寸为 1K，质量为 auto。可以在对话中切换模型、1K/2K/4K 和质量；模型是否可用以本机 API 服务的权限为准。支持单张生成、多图编辑、PNG mask 和 JSONL 批量生成，不支持视频。实际输出尺寸由上游决定，返回后会检查实际像素。

命令行示例（离线校验，不调用 API）：

```bash
~/.codex/skills/codex-image/scripts/run.sh generate \
  --prompt 'A quiet snowy mountain' \
  --model gpt-image-2 --size 1K --quality auto --dry-run
```

移除 `--dry-run`，并添加 `--out output/imagegen/mountain.png` 即可生成图片。

### 修改已有图片

```bash
~/.codex/skills/codex-image/scripts/run.sh edit \
  --image input/original.png \
  --prompt '只将蓝色杯子改成红色，保持杯形、把手、背景和构图不变。' \
  --model gpt-image-2.5 --size 1K --quality auto \
  --out output/imagegen/edited.png
```

改图使用 `POST /v1/images/edits`，以 `multipart/form-data` 上传参考图；可重复传 `--image`，局部修改可加 `--mask mask.png`。程序按文件实际内容设置每张图片及蒙版的 MIME 类型（如 `image/png`、`image/jpeg`），避免默认的 `application/octet-stream` 被接口拒绝。此类上传格式错误不代表模型不支持改图。原图保留，结果另存。

## 配置读取

API 地址优先读取本机配置的 `[model_providers.<provider>].base_url`，仅当当前服务商未配置地址时，才依次尝试 `OPENAI_BASE_URL`、`OPENAI_API_BASE`。均未设置时直接报错，不使用固定中转站地址。密钥仅从运行环境传入子进程，不写入文件。

原生程序内部保留上游的 `CODEX_API_*` 变量及 `codex-image2-5-*` 文件名；启动器负责适配，日常使用统一调用 `scripts/run.sh`。

## 来源与许可

基于 [daifei-0/codex-image2-5-skill](https://github.com/daifei-0/codex-image2-5-skill)，保留上游 Go 源码和原生程序。本仓库将 Skill 改名为 `codex-image`，新增读取本机 Codex 配置并复用 `OPENAI_API_KEY` 的启动器。

遵循 [MIT License](LICENSE)，保留原作者 daifei-0 的版权声明。
