# CrispASR TTS Web UI

[CrispASR](https://github.com/CrispStrobe/CrispASR) TTS 服务器的 Web 界面——语音克隆、多角色合成、文本分割、一键更新。

**单二进制零依赖** — 用 Go 编写，无需 Python、pip、npm 或 Docker。

## 功能特性

- 🎙️ **多角色语音合成** — 9 种内置音色 + 自定义语音克隆
- 📝 **智能文本分割** — 自动分句，支持内联角色标签和标记语法
- 🔄 **断点续传** — 生成失败可从断点恢复，无需重新合成已完成片段
- 🔄 **一键更新** — 从 GitHub 下载最新 CrispASR，自动检测平台架构
- 🧪 **试听预览** — 全量生成前可单独试听每个片段
- 📊 **批量合成 & 音色对比** — 多文本多音色一键生成
- 🔄 **模型切换** — 7 种后端：Qwen3-TTS、Kokoro、CosyVoice3、Chatterbox
- 📈 **系统监控** — CPU / 内存 / 磁盘 / 队列深度实时状态
- 🔒 **密码认证** — JWT + 频率限制，密钥自动持久化
- 📱 **响应式界面** — 深色主题，支持移动端

## 快速开始

### 一键安装（Linux）

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | bash
```

安装脚本会自动：
1. 检测 CPU 架构和 GPU（CUDA / Vulkan / CPU）
2. 下载最新 CrispASR 二进制文件
3. 编译 Go 版 WebUI（需 Go 1.22+，脚本可自动安装）
4. 配置 systemd 服务（CrispASR + WebUI）
5. 交互式设置登录密码
6. 启动所有服务

### 自定义安装选项

```bash
# 自定义安装目录、使用 CUDA、指定模型
INSTALL_DIR=/opt/my-tts GPU_BACKEND=cuda MODEL=qwen3-tts-customvoice-0.6b-q8 bash install.sh

# 通过环境变量设置密码（非交互式）
TTS_PASSWORD=*** bash install.sh
```

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `INSTALL_DIR` | `/opt/crispasr` | 安装目录 |
| `DATA_DIR` | `/var/lib/crispasr-webui` | 数据目录（历史记录、音频） |
| `WEBUI_PORT` | `8888` | WebUI 监听端口 |
| `CRISPASR_PORT` | `8080` | CrispASR 服务端口 |
| `GPU_BACKEND` | `auto` | GPU 模式：`auto`、`cpu`、`cuda`、`vulkan` |
| `MODEL` | `qwen3-tts-customvoice-1.7b-f16` | 默认 TTS 模型 |
| `TTS_PASSWORD` | *（交互输入）* | 登录密码 |

### 手动安装

```bash
# 1. 编译
go build -o crispasr-webui .

# 2. 启动 CrispASR 服务
/opt/crispasr/bin/crispasr --server --backend qwen3-tts-customvoice \
  -m qwen3-tts-1.7b-customvoice --voice-dir /opt/crispasr/voices \
  --port 8080 &

# 3. 启动 WebUI
TTS_PASSWORD=*** CRISPASR_DIR=/opt/crispasr \
  ./crispasr-webui
```

打开 http://localhost:8888

## 性能对比

| 指标 | Python (v0.9.3) | Go (v1.1.0) |
|------|-----------------|-------------|
| 代码行数 | 3,895 | 1,486 |
| 后端文件 | 12 `.py` | 1 `.go` |
| 依赖 | Python 3.10+ | 无（静态二进制） |
| 二进制大小 | N/A（需 Python） | ~13 MB |
| 运行内存 | ~60 MB | **~10 MB** |
| 启动时间 | ~2s | **<100ms** |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TTS_PASSWORD` | *（必填）* | 登录密码 |
| `CRISPASR_DIR` | `.` | CrispASR 安装目录 |
| `CRISPASR_DATA_DIR` | `./tts_data` | 数据目录（数据库、音频、上传） |
| `TTS_PORT` | `8888` | HTTP 端口 |
| `JWT_SECRET` | *（自动生成并持久化）* | JWT 签名密钥 |

## 支持平台

CrispASR 提供以下预编译二进制文件：

| 平台 | 文件名 | 备注 |
|------|--------|------|
| Linux x86_64 | `crispasr-linux-x86_64.tar.gz` | CPU only |
| Linux x86_64 + CUDA | `crispasr-linux-x86_64-cuda.tar.gz` | NVIDIA GPU |
| Linux x86_64 + Vulkan | `crispasr-linux-x86_64-vulkan.tar.gz` | AMD/Intel GPU |
| Linux ARM64 | `crispasr-linux-arm64.tar.gz` | Ampere Altra, Raspberry Pi 5 |
| macOS | `crispasr-macos.tar.gz` | Apple Silicon + Intel |

## License

MIT
