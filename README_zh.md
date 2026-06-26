# CrispASR TTS Web UI

[CrispASR](https://github.com/CrispStrobe/CrispASR) TTS 服务器的 Web 界面——语音克隆、多角色合成、文本分割、一键更新。

**零外部依赖** — 仅需 Python 3.10+ 标准库，无需 pip、npm 或 Docker。

## 功能特性

- 🎙️ **多角色语音合成** — 9 种内置音色 + 自定义语音克隆
- 📝 **智能文本分割** — 自动分句，支持内联角色标签和标记语法
- 🔄 **断点续传** — 生成失败可从断点恢复，无需重新合成已完成片段
- 🔄 **一键更新** — 从 GitHub 下载最新 CrispASR，自动检测平台架构
- 🧪 **试听预览** — 全量生成前可单独试听每个片段
- 🌐 **OpenAI 兼容代理** — `/v1/audio/speech` 端点，可对接外部工具
- 🔒 **密码认证** — JWT 令牌 + 请求频率限制
- 📱 **响应式界面** — 深色主题，支持移动端

## 快速开始

### 一键安装（Linux）

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | bash
```

安装脚本会自动：
1. 检测 CPU 架构和 GPU（CUDA/Vulkan/CPU）
2. 下载最新 CrispASR 二进制文件
3. 从 GitHub 安装 WebUI
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

### 手动安装（macOS / 无 systemd 的 Linux）

```bash
# 1. 下载对应平台的 CrispASR
#    查看：https://github.com/CrispStrobe/CrispASR/releases
curl -L -o crispasr.tar.gz https://github.com/CrispStrobe/CrispASR/releases/latest/download/crispasr-macos.tar.gz
mkdir -p /opt/crispasr/bin && tar xzf crispasr.tar.gz -C /opt/crispasr/bin --strip-components=1

# 2. 克隆 WebUI
git clone https://github.com/yzy806806/crispasr-webui.git /opt/crispasr/crispasr_webui

# 3. 启动 CrispASR 服务
/opt/crispasr/bin/crispasr --server --backend qwen3-tts-customvoice \
  -m qwen3-tts-1.7b-customvoice --voice-dir /opt/crispasr/voices \
  --port 8080 &

# 4. 启动 WebUI
TTS_PASSWORD=*** CRISPASR_DIR=/opt/crispasr \
  python3 -m crispasr_webui --port 8888 --api http://localhost:8080
```

## 支持平台

CrispASR 提供以下预编译二进制文件：

| 平台 | 文件名 | 备注 |
|------|--------|------|
| Linux ARM64 | `crispasr-linux-arm64.tar.gz` | 树莓派 4/5、Oracle Cloud Ampere |
| Linux x86_64 | `crispasr-linux-x86_64.tar.gz` | 通用 CPU（AVX2） |
| Linux x86_64 + CUDA | `crispasr-linux-x86_64-cuda.tar.gz` | NVIDIA GPU |
| Linux x86_64 + Vulkan | `crispasr-linux-x86_64-vulkan.tar.gz` | AMD/Intel GPU |
| macOS | `crispasr-macos.tar.gz` | Apple Silicon + Intel |
| Windows x86_64 | `crispasr-windows-x86_64-cpu.zip` | 仅 CPU |

WebUI 为纯 Python 实现，可在任何 Python 3.10+ 环境运行。

## 命令行参数

```
python3 -m crispasr_webui [选项]

  --listen ADDR       监听地址（默认：0.0.0.0）
  --port PORT         监听端口（默认：8888）
  --api URL           CrispASR API 地址（默认：http://localhost:8080）
  --password PASS     登录密码（或设置 TTS_PASSWORD 环境变量）
  --data-dir PATH     数据目录（历史记录、音频、上传文件）
  --crispasr-dir PATH CrispASR 安装目录
```

## 项目结构

```
crispasr_webui/
├── __init__.py         # 包初始化
├── __main__.py         # python -m 入口
├── config.py           # 路径、常量、模型注册表
├── auth.py             # JWT 编解码
├── database.py         # SQLite 初始化与连接
├── text_split.py       # 分句与内联标记解析
├── audio_utils.py      # WAV 时长、格式转换
├── task_queue.py       # 任务队列、生成工作线程
├── crispasr_mgmt.py    # 版本检测、更新、模型切换
├── templates.py        # HTML/CSS/JS 前端
├── handlers.py         # HTTP 请求处理
└── server.py           # 入口与命令行参数
```

## 服务管理

```bash
# 查看状态
systemctl status crispasr crispasr-webui

# 查看日志
journalctl -u crispasr-webui -f

# 重启
sudo systemctl restart crispasr-webui

# 停止
sudo systemctl stop crispasr crispasr-webui

# 卸载
sudo systemctl stop crispasr crispasr-webui
sudo systemctl disable crispasr crispasr-webui
sudo rm -rf /opt/crispasr /var/lib/crispasr-webui /etc/crispasr-webui.env
sudo rm /etc/systemd/system/crispasr.service /etc/systemd/system/crispasr-webui.service
sudo systemctl daemon-reload
```

## 许可证

MIT

---

**[English](README.md)**
