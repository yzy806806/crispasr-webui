# CrispASR TTS Web UI

[CrispASR](https://github.com/CrispStrobe/CrispASR) TTS 服务器的 Web 界面——语音克隆、多角色合成、文本分割、一键更新。

**单二进制零依赖** — 用 Go 编写，无需 Python、pip、npm 或 Docker。

## 功能特性

- 🎙️ **多角色语音合成** — 9 种内置音色 + 自定义语音克隆
- 📝 **智能文本分割** — 自动分句，支持内联角色标签和标记语法
- 🔄 **断点续传** — 生成失败可从断点恢复，无需重新合成已完成片段
- 🔄 **一键安装/更新** — Web 界面直接安装或更新 CrispASR，自动检测平台架构
- 🧪 **试听预览** — 全量生成前可单独试听每个片段
- 📊 **批量合成 & 音色对比** — 多文本多音色一键生成
- 🔄 **模型切换** — 7 种后端：Qwen3-TTS、Kokoro、CosyVoice3、Chatterbox
- 📈 **系统监控** — CPU / 内存 / 磁盘 / 队列深度实时状态
- 🔒 **密码认证** — JWT + 频率限制，密钥自动持久化
- ⚡ **CrispASR 自动启停** — 有任务自动拉起，空闲自动停止，省内存
- 📱 **响应式界面** — 深色主题，支持移动端

## 快速开始

### 一键安装（Linux）

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | sudo bash
```

> ⚠️ **必须以 root 运行**（需要写 systemd 服务、安装到 /opt、写入 /etc 配置文件）。

安装脚本会自动：
1. 检测 CPU 架构和 GPU（CUDA / Vulkan / CPU）
2. 下载最新 CrispASR 二进制文件
3. 编译 Go 版 WebUI（需 Go 1.22+，脚本可自动安装）
4. 配置 systemd 服务（CrispASR + WebUI），开机自启
5. 交互式设置登录密码
6. 启动所有服务

### 密码说明

**没有默认密码。** 安装时密码设置流程如下：

1. 如果设置了环境变量 `TTS_PASSWORD`，直接使用该值
2. 否则交互式提示输入密码（输入时不显示字符）
3. 如果直接回车（空密码），脚本会自动生成一个 16 位随机密码并显示

安装完成后，终端会打印：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🎙️  CrispASR TTS Web UI is ready!

  URL:      http://10.0.0.25:8888
  Password: a3b5c7d9e1f2a4b6

  Services:  systemctl status crispasr crispasr-webui
  Logs:      journalctl -u crispasr-webui -f
  Uninstall: systemctl stop crispasr crispasr-webui && rm -rf /opt/crispasr /var/lib/crispasr-webui
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

密码保存在 `/etc/crispasr-webui.env`（权限 600，仅 root 可读）。

**修改密码：**

```bash
# 编辑密码文件
sudo nano /etc/crispasr-webui.env

# 重启 WebUI 服务使新密码生效
sudo systemctl restart crispasr-webui
```

**Web 界面修改密码：** 登录后点击右上角用户图标 → 修改密码。

### 兼容性

| 系统 | 支持 | 备注 |
|------|------|------|
| Ubuntu 20.04+ | ✅ | 完全支持 |
| Debian 11+ | ✅ | 完全支持，脚本零 Python 依赖 |
| CentOS / RHEL 8+ | ⚠️ | 需手动安装 curl、git；systemd 可用 |
| macOS | ⚠️ | 需手动启动（无 systemd），脚本可编译 |
| 其他 Linux | ⚠️ | 需 systemd + curl + git + bash |

> 💡 脚本不依赖 Python，仅使用 POSIX 标准工具（`grep -oE`、`od`、`sed`），Debian 最小安装即可运行。

### 自定义安装选项

```bash
# 自定义安装目录、使用 CUDA、指定模型
sudo INSTALL_DIR=/opt/my-tts GPU_BACKEND=cuda MODEL=qwen3-tts-customvoice-0.6b-q8 bash install.sh

# 通过环境变量设置密码（非交互式，适合自动化部署）
sudo TTS_PASSWORD=your_password bash install.sh
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
TTS_PASSWORD=your_password CRISPASR_DIR=/opt/crispasr \
  ./crispasr-webui
```

打开 http://localhost:8888

## 性能对比

| 指标 | Python (v0.9.3) | Go (v1.3.0) |
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
| `CRISPASR_AUTOSTART` | `1` | 自动启停 CrispASR（`1`=开，`0`=关） |
| `CRISPASR_IDLE_TIMEOUT` | `300` | 空闲多少秒后自动停止 CrispASR（最小60） |
| `CRISPASR_PORT` | `8080` | CrispASR 服务端口（健康检查用） |

## 支持平台

CrispASR 提供以下预编译二进制文件：

| 平台 | 文件名 | 备注 |
|------|--------|------|
| Linux x86_64 | `crispasr-linux-x86_64.tar.gz` | CPU only |
| Linux x86_64 + CUDA | `crispasr-linux-x86_64-cuda.tar.gz` | NVIDIA GPU |
| Linux x86_64 + Vulkan | `crispasr-linux-x86_64-vulkan.tar.gz` | AMD/Intel GPU |
| Linux ARM64 | `crispasr-linux-arm64.tar.gz` | Ampere Altra, Raspberry Pi 5 |
| macOS | `crispasr-macos.tar.gz` | Apple Silicon + Intel |

## 常见问题

<details>
<summary><strong>忘记密码怎么办？</strong></summary>

编辑 `/etc/crispasr-webui.env`，修改 `TTS_PASSWORD=新密码`，然后 `sudo systemctl restart crispasr-webui`。
</details>

<details>
<summary><strong>如何卸载？</strong></summary>

```bash
sudo systemctl stop crispasr crispasr-webui
sudo systemctl disable crispasr crispasr-webui
sudo rm /etc/systemd/system/crispasr.service /etc/systemd/system/crispasr-webui.service
sudo rm /etc/crispasr-webui.env
sudo rm -rf /opt/crispasr /var/lib/crispasr-webui
sudo systemctl daemon-reload
```
</details>

<details>
<summary><strong>如何查看日志？</strong></summary>

```bash
# WebUI 日志
journalctl -u crispasr-webui -f

# CrispASR 服务日志
journalctl -u crispasr -f
```
</details>

<details>
<summary><strong>Debian 上能用吗？</strong></summary>

可以。安装脚本零 Python 依赖，仅使用 POSIX 标准工具。Debian 11+ 最小安装只要有 `curl` 和 `git` 即可运行。如果缺少，先安装：

```bash
sudo apt update && sudo apt install -y curl git
```
</details>

<details>
<summary><strong>如何更新？</strong></summary>

重新运行安装脚本即可，会自动拉取最新代码并重新编译：

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | sudo bash
```

CrispASR 本体的安装和更新均可在 Web 界面中点击「安装/更新」按钮完成。未安装时按钮显示为"安装 CrispASR x.x.x"，已安装时显示"更新到 x.x.x"。
</details>

<details>
<summary><strong>CrispASR 自动启停是怎么工作的？</strong></summary>

v1.2.0 新增功能。默认开启（`CRISPASR_AUTOSTART=1`）：

1. **提交任务时**：WebUI 检测 CrispASR 是否在运行，没运行则自动 `systemctl start crispasr`，等待健康检查通过后才开始处理
2. **试听预览时**：同样自动拉起 CrispASR
3. **任务完成后**：如果队列为空，启动一个 5 分钟倒计时（`CRISPASR_IDLE_TIMEOUT=300`），到期后自动 `systemctl stop crispasr`
4. **倒计时期间有新任务**：自动取消倒计时

**前提条件**：WebUI 运行用户需要有 sudo 权限执行 `systemctl start/stop crispasr`。一键安装脚本会自动配置 sudoers。

**关闭自动启停**：在 `/etc/crispasr-webui.env` 中设置 `CRISPASR_AUTOSTART=0`，然后重启 WebUI。
</details>

## License

MIT
