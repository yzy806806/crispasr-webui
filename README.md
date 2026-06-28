# CrispASR TTS Web UI

[CrispASR](https://github.com/CrispStrobe/CrispASR) TTS 服务器的 Web 界面——语音克隆、多角色合成、文本分割、模型管理。

**单二进制零依赖** — Go 编写，无需 Python、pip、npm 或 Docker。

## 功能特性

- 🎙️ **多角色语音合成** — 9 种内置音色 + 自定义语音克隆
- 📝 **智能文本分割** — 自动分句，支持内联角色标签和标记语法
- 🔄 **断点续传** — 生成失败可从断点恢复
- 🧪 **试听预览** — 全量生成前可单独试听每个片段
- 📊 **批量合成 & 音色对比** — 多文本多音色一键生成
- 🧠 **模型切换** — 支持量化级别选择，自动下载模型
- 📈 **系统监控** — CPU / 内存 / 磁盘实时状态
- 🔒 **密码认证** — JWT + bcrypt，密钥自动持久化
- ⚡ **自动启停** — 有任务自动拉起 CrispASR，空闲自动停止
- 📱 **响应式界面** — 深色主题，支持移动端

## 快速开始

### 一键安装（Linux）

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | sudo bash
```

> ⚠️ **必须以 root 运行**（需要写 systemd 服务、/opt、/etc）。

安装脚本会自动：
1. 检测 CPU 架构
2. 编译 Go 版 WebUI（需 Go 1.22+，脚本可自动安装）
3. 配置 systemd 服务，开机自启
4. 启动 WebUI（默认密码 `12345678`）

> 📌 **CrispASR 不包含在安装脚本中。** 请自行安装 [CrispASR](https://github.com/CrispStrobe/CrispASR)，然后在 WebUI 的「设置」页面配置二进制路径。

### 安装 CrispASR

CrispASR 提供预编译二进制：

| 平台 | 文件名 |
|------|--------|
| Linux x86_64 | `crispasr-linux-x86_64.tar.gz` |
| Linux x86_64 + CUDA | `crispasr-linux-x86_64-cuda.tar.gz` |
| Linux x86_64 + Vulkan | `crispasr-linux-x86_64-vulkan.tar.gz` |
| Linux ARM64 | `crispasr-linux-arm64.tar.gz` |
| macOS | `crispasr-macos.tar.gz` |

```bash
# 下载并解压
curl -fsSL -o /tmp/crispasr.tar.gz \
  https://github.com/CrispStrobe/CrispASR/releases/latest/download/crispasr-linux-x86_64.tar.gz
sudo mkdir -p /opt/crispasr/bin /opt/crispasr/lib
sudo tar xzf /tmp/crispasr.tar.gz -C /tmp/
sudo cp $(find /tmp -name crispasr -type f | head -1) /opt/crispasr/bin/crispasr
sudo find /tmp -name '*.so*' -type f -exec cp {} /opt/crispasr/lib/ \;
```

然后在 WebUI → ⚙️ 设置 → 配置路径为 `/opt/crispasr/bin/crispasr`。

### 密码说明

**默认密码：`12345678`**，首次启动时自动写入 SQLite 数据库。

修改密码：登录后点击 🔑 修改密码。忘记密码：

```bash
sudo systemctl stop crispasr-webui
sqlite3 /var/lib/crispasr-webui/tts.db "DELETE FROM settings WHERE key='password';"
sudo systemctl start crispasr-webui
```

### 自定义安装选项

```bash
sudo INSTALL_DIR=/opt/my-tts DATA_DIR=/data/tts WEBUI_PORT=9999 bash install.sh
```

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `INSTALL_DIR` | `/opt/crispasr` | 安装目录 |
| `DATA_DIR` | `/var/lib/crispasr-webui` | 数据目录（历史记录、音频） |
| `WEBUI_PORT` | `8888` | WebUI 监听端口 |
| `CRISPASR_PORT` | `8080` | CrispASR 服务端口 |

### 手动安装

```bash
# 1. 编译
go build -o crispasr-webui .

# 2. 启动 CrispASR（自行安装）
/opt/crispasr/bin/crispasr --server --backend qwen3-tts-customvoice \
  -m qwen3-tts-1.7b-customvoice --voice-dir /opt/crispasr/voices --port 8080 &

# 3. 启动 WebUI
CRISPASR_DIR=/opt/crispasr ./crispasr-webui
```

打开 http://localhost:8888

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CRISPASR_DIR` | `.` | CrispASR 安装目录 |
| `CRISPASR_DATA_DIR` | `./tts_data` | 数据目录（数据库、音频、上传） |
| `TTS_PORT` | `8888` | HTTP 端口 |
| `JWT_SECRET` | *（自动生成并持久化）* | JWT 签名密钥 |
| `CRISPASR_AUTOSTART` | `1` | 自动启停 CrispASR（`1`=开，`0`=关） |
| `CRISPASR_IDLE_TIMEOUT` | `300` | 空闲多少秒后自动停止 CrispASR（最小60） |
| `CRISPASR_PORT` | `8080` | CrispASR 服务端口（健康检查用） |

## 兼容性

| 系统 | 支持 | 备注 |
|------|------|------|
| Ubuntu 20.04+ | ✅ | 完全支持 |
| Debian 11+ | ✅ | 完全支持 |
| CentOS / RHEL 8+ | ⚠️ | 需手动安装 curl、git |
| macOS | ⚠️ | 需手动启动（无 systemd） |
| 其他 Linux | ⚠️ | 需 systemd + curl + git + bash |

## 常见问题

<details>
<summary><strong>忘记密码怎么办？</strong></summary>

```bash
sudo systemctl stop crispasr-webui
sqlite3 /var/lib/crispasr-webui/tts.db "DELETE FROM settings WHERE key='password';"
sudo systemctl start crispasr-webui
```

重启后恢复为默认密码 `12345678`。
</details>

<details>
<summary><strong>如何卸载？</strong></summary>

```bash
sudo systemctl stop crispasr-webui
sudo systemctl disable crispasr-webui
sudo rm /etc/systemd/system/crispasr-webui.service
sudo rm /etc/tts-webui.env
sudo rm -rf /opt/crispasr /var/lib/crispasr-webui
sudo systemctl daemon-reload
```
</details>

<details>
<summary><strong>如何查看日志？</strong></summary>

```bash
journalctl -u crispasr-webui -f
```
</details>

<details>
<summary><strong>如何更新 WebUI？</strong></summary>

重新运行安装脚本即可：

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | sudo bash
```
</details>

<details>
<summary><strong>如何更新 CrispASR？</strong></summary>

CrispASR 需手动更新。下载新版本预编译包，替换 `/opt/crispasr/bin/crispasr`，然后重启服务：

```bash
sudo systemctl restart crispasr
```

WebUI 的「设置」页面可检查当前版本和最新版本。
</details>

<details>
<summary><strong>自动启停是怎么工作的？</strong></summary>

默认开启（`CRISPASR_AUTOSTART=1`）：

1. **提交任务时** — 自动 `systemctl start crispasr`，等待健康检查通过
2. **任务完成后** — 空闲 5 分钟自动 `systemctl stop crispasr`
3. **空闲期间有新任务** — 自动取消倒计时

关闭：在 `/etc/tts-webui.env` 中设置 `CRISPASR_AUTOSTART=0`，重启 WebUI。
</details>

<details>
<summary><strong>预编译包跑不起来怎么办？</strong></summary>

某些 CPU（如 Neoverse-N1、老款 x86_64）可能不支持预编译包中的指令集扩展（SVE、AVX2 等），表现为 `Illegal instruction`。

此时需要从源码编译 CrispASR：

```bash
git clone --depth 1 --branch v0.8.5 https://github.com/CrispStrobe/CrispASR
cd CrispASR
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
sudo cp build/bin/crispasr /opt/crispasr/bin/crispasr
sudo find build -name '*.so*' -exec cp {} /opt/crispasr/lib/ \;
```
</details>

## License

MIT
