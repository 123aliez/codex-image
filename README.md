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

自动读取本机 Codex 配置，复用 `OPENAI_API_KEY`。当前启动器支持 macOS Apple Silicon 和 Intel。

[MIT License](LICENSE)
