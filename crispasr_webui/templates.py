"""HTML templates for CrispASR TTS Web UI."""

HTML_PAGE = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CrispASR TTS</title>
<style>
:root{--bg:#0f1117;--card:#1a1d27;--border:#2a2d3a;--text:#e4e4e7;--muted:#71717a;--accent:#6366f1;--accent2:#818cf8;--success:#22c55e;--error:#ef4444;--warn:#f59e0b;--sidebar-w:200px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
a{color:var(--accent2);text-decoration:none}

.login-wrap{display:flex;justify-content:center;align-items:center;min-height:100vh}
.login-box{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:40px;width:360px}
.login-box h2{text-align:center;margin-bottom:24px;font-size:22px}
.login-box input[type=password]{width:100%;padding:12px 14px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);font-size:15px;outline:none;margin-bottom:16px}
.login-box input[type=password]:focus{border-color:var(--accent)}
.login-box button{width:100%;padding:12px;border:none;border-radius:8px;background:var(--accent);color:#fff;font-size:15px;font-weight:600;cursor:pointer;transition:.2s}
.login-box button:hover{background:var(--accent2)}
.login-error{color:var(--error);font-size:13px;margin-bottom:12px;display:none}

.app{display:none}

/* ─── Sidebar Layout ─── */
.app-layout{display:flex;min-height:100vh}
.sidebar{width:var(--sidebar-w);background:var(--card);border-right:1px solid var(--border);display:flex;flex-direction:column;position:fixed;top:0;left:0;bottom:0;z-index:10;overflow-y:auto}
.sidebar-brand{padding:20px 16px 16px;font-size:16px;font-weight:700;border-bottom:1px solid var(--border);white-space:nowrap}
.sidebar-nav{flex:1;padding:8px 0}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 16px;cursor:pointer;transition:.2s;color:var(--muted);font-size:14px;border-left:3px solid transparent;user-select:none}
.nav-item:hover{color:var(--text);background:rgba(99,102,241,.05)}
.nav-item.active{color:var(--accent2);background:rgba(99,102,241,.1);border-left-color:var(--accent)}
.nav-item .nav-icon{font-size:16px;width:20px;text-align:center}
.sidebar-footer{padding:12px 16px;border-top:1px solid var(--border)}
.sidebar-footer .nav-item{padding:8px 0;border-left:none;font-size:13px;color:var(--muted)}
.sidebar-footer .nav-item:hover{color:var(--error)}

.main-content{margin-left:var(--sidebar-w);flex:1;padding:28px 32px;max-width:calc(100% - var(--sidebar-w))}
.main-content h2{font-size:20px;font-weight:700;margin-bottom:16px;display:flex;align-items:center;gap:8px}

/* Panel visibility */
.panel{display:none}
.panel.active{display:block}

.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:16px}
label{display:block;font-weight:600;margin-bottom:6px;font-size:13px}
.hint{font-size:11px;color:var(--muted);margin-top:3px}
textarea{width:100%;padding:12px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);font-size:15px;font-family:inherit;resize:vertical;min-height:120px;outline:none;transition:border-color .2s}
textarea:focus{border-color:var(--accent)}
input[type=text],select{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);font-size:14px;outline:none}
input[type=text]:focus,select:focus{border-color:var(--accent)}
select{cursor:pointer;appearance:auto}

.row{display:flex;gap:12px;align-items:flex-end}
.row>*{flex:1}

.voice-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px}
.voice-btn{padding:8px 6px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);cursor:pointer;text-align:center;font-size:12px;transition:all .2s;user-select:none}
.voice-btn:hover{border-color:var(--accent);transform:translateY(-1px)}
.voice-btn.active{border-color:var(--accent);background:rgba(99,102,241,.15);color:var(--accent2)}

.btn-row{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap}
button{padding:10px 24px;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;transition:.2s}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent2)}
.btn-primary:disabled{opacity:.5;cursor:not-allowed}
.btn-secondary{background:var(--card);color:var(--text);border:1px solid var(--border)}
.btn-secondary:hover{border-color:var(--accent)}
.btn-warn{background:var(--warn);color:#fff}
.btn-warn:hover{opacity:.9}
.btn-warn:disabled{opacity:.5;cursor:not-allowed}
.btn-sm{padding:6px 14px;font-size:13px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);cursor:pointer;transition:.2s;white-space:nowrap}
.btn-sm:hover{border-color:var(--accent)}
.btn-sm.active{background:var(--accent);color:#fff;border-color:var(--accent)}

/* Chunk preview with per-chunk controls */
.chunk-preview{display:none;margin-top:12px}
.chunk-preview.show{display:block}
.chunk-list{max-height:400px;overflow-y:auto;font-size:13px}
.chunk-item{padding:8px 12px;border-left:3px solid var(--accent);margin-bottom:6px;background:rgba(99,102,241,.05);border-radius:0 6px 6px 0;position:relative}
.chunk-item:hover{background:rgba(99,102,241,.1)}
.chunk-text{margin-bottom:4px;line-height:1.5}
.chunk-controls{display:none;gap:8px;align-items:center;flex-wrap:wrap;padding-top:4px;border-top:1px solid var(--border)}
.chunk-item.expanded .chunk-controls{display:flex}
.chunk-controls select,.chunk-controls input{padding:4px 8px;font-size:12px;width:auto;min-width:80px}
.chunk-controls input{flex:1;min-width:120px}
.chunk-expand{position:absolute;right:8px;top:8px;background:none;border:none;color:var(--muted);cursor:pointer;font-size:16px;padding:2px 6px}
.chunk-expand:hover{color:var(--accent)}
.chunk-audition{background:var(--success);color:#fff;border:none;padding:3px 8px;border-radius:4px;font-size:11px;cursor:pointer}
.chunk-audition:hover{opacity:.9}
.chunk-num{color:var(--accent2);font-weight:600;margin-right:4px}

/* Queue status */
.queue-badge{display:inline-block;background:var(--warn);color:#fff;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px}

/* Progress */
.progress-bar{height:4px;background:var(--border);border-radius:2px;margin:12px 0;overflow:hidden}
.progress-fill{height:100%;background:var(--accent);transition:width .3s;width:0%}
.progress-text{font-size:12px;color:var(--muted)}

/* Result */
.result-card{display:none}
.result-card.show{display:block}
.audio-player{width:100%;margin:8px 0;border-radius:8px}
.result-meta{font-size:12px;color:var(--muted);margin-top:4px}

/* History */
.history-toolbar{display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.history-search{flex:1;min-width:180px;padding:6px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px}
.history-search:focus{outline:none;border-color:var(--accent)}
.history-checkall{margin-right:4px;cursor:pointer}
.history-item{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;background:var(--card);gap:8px}
.history-item:hover{border-color:var(--accent)}
.history-check{flex-shrink:0;cursor:pointer}
.history-body{flex:1;overflow:hidden;display:flex;flex-direction:column;gap:2px}
.history-text{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;cursor:pointer}
.history-text:hover{color:var(--accent)}
.history-meta{font-size:11px;color:var(--muted);white-space:nowrap}
.history-actions{display:flex;gap:4px;flex-shrink:0}
.history-actions button{padding:4px 8px;font-size:11px;border-radius:4px}
.history-footer{display:flex;justify-content:space-between;align-items:center;margin-top:10px;font-size:12px;color:var(--muted)}
.history-footer button{padding:4px 10px;font-size:12px;border-radius:4px}

/* Status */
.status-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px}
.status-card{padding:14px;border:1px solid var(--border);border-radius:8px;background:var(--card)}
.status-card h4{margin:0 0 8px;font-size:13px;color:var(--muted);font-weight:normal}
.status-value{font-size:22px;font-weight:700;color:var(--text)}
.status-detail{font-size:11px;color:var(--muted);margin-top:4px}
.status-bar{height:4px;background:var(--border);border-radius:2px;margin-top:6px;overflow:hidden}
.status-bar-fill{height:100%;border-radius:2px;transition:width .5s}
.status-on{color:#22c55e}
.status-off{color:#ef4444}

/* Logs */
.logs-toolbar{display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap}
.logs-search{flex:1;min-width:180px;padding:6px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px}
.logs-search:focus{outline:none;border-color:var(--accent)}
.logs-terminal{background:#0d1117;color:#c9d1d9;font-family:'Courier New',monospace;font-size:12px;line-height:1.5;padding:12px;border-radius:8px;max-height:400px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.logs-terminal::-webkit-scrollbar{width:6px}
.logs-terminal::-webkit-scrollbar-thumb{background:#30363d;border-radius:3px}

/* Clone / Voice management */
.voice-item{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border:1px solid var(--border);border-radius:6px;margin-bottom:4px;background:var(--card)}
.voice-item:hover{border-color:var(--accent)}
.voice-name{font-size:13px;font-weight:500}
.voice-meta{font-size:11px;color:var(--muted)}
.voice-item-actions{display:flex;gap:4px}
.voice-item-actions button{padding:2px 8px;font-size:11px;border-radius:4px}

/* Compare */
.compare-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:8px}
.compare-col{text-align:center}
.compare-col h4{margin:0 0 6px;font-size:13px}
.compare-col audio{width:100%;margin-top:4px}
.compare-status{font-size:12px;color:var(--muted);text-align:center;padding:12px}

/* Batch */
.batch-item{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)}
.batch-item:last-child{border-bottom:none}
.batch-item-text{flex:1;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.batch-item-status{font-size:11px;min-width:60px;text-align:center}
.batch-progress{margin-top:8px}
.batch-progress-bar{height:4px;background:var(--border);border-radius:2px;overflow:hidden}
.batch-progress-fill{height:100%;background:var(--accent);transition:width .3s}
.upload-zone{border:2px dashed var(--border);border-radius:8px;padding:24px;text-align:center;cursor:pointer;transition:.2s}
.upload-zone:hover{border-color:var(--accent)}
.upload-zone.has-file{border-color:var(--success);border-style:solid}

/* Model section */
.model-card{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;background:var(--bg);cursor:pointer;transition:.2s}
.model-card:hover{border-color:var(--accent)}
.model-card.active{border-color:var(--success);background:rgba(34,197,94,.05)}
.model-card.active::before{content:'✓ ';color:var(--success);font-weight:700}
.model-name{font-weight:600;font-size:14px}
.model-desc{font-size:11px;color:var(--muted);margin-top:2px}

/* Update section */
.update-log{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:12px;font-family:monospace;font-size:12px;max-height:200px;overflow-y:auto;white-space:pre-wrap;color:var(--muted);margin-top:8px}

.spinner{display:inline-block;width:14px;height:14px;border:2px solid var(--muted);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;vertical-align:middle;margin-right:6px}
@keyframes spin{to{transform:rotate(360deg)}}

/* Markup hint banner */
.markup-hint{background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.2);border-radius:8px;padding:10px 14px;font-size:12px;color:var(--accent2);margin-top:8px;display:none}
.markup-hint.show{display:block}
.markup-hint code{background:var(--bg);padding:2px 6px;border-radius:4px;font-size:11px}

/* Mobile: sidebar collapses to bottom tab bar */
@media(max-width:768px){
  .app-layout{flex-direction:column}
  .sidebar{position:fixed;bottom:0;top:auto;left:0;right:0;width:100%;height:auto;flex-direction:row;border-right:none;border-top:1px solid var(--border);overflow-x:auto;overflow-y:hidden}
  .sidebar-brand,.sidebar-footer{display:none}
  .sidebar-nav{display:flex;flex-direction:row;padding:0;width:100%}
  .nav-item{flex-direction:column;gap:2px;padding:8px 12px;font-size:10px;border-left:none;border-bottom:2px solid transparent;justify-content:center;min-width:56px}
  .nav-item.active{border-left:none;border-bottom-color:var(--accent)}
  .main-content{margin-left:0;padding:16px 12px;padding-bottom:72px;max-width:100%}
  .row{flex-direction:column}
  .voice-grid{grid-template-columns:repeat(auto-fill,minmax(80px,1fr))}
  .chunk-controls{flex-direction:column;align-items:stretch}
}

::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--muted)}
</style>
</head>
<body>

<!-- Login -->
<div class="login-wrap" id="loginPage">
  <div class="login-box">
    <h2>🎙️ CrispASR TTS</h2>
    <div class="login-error" id="loginError">密码错误</div>
    <input type="password" id="loginPassword" placeholder="请输入密码" autofocus
           onkeydown="if(event.key==='Enter')doLogin()">
    <button onclick="doLogin()">登 录</button>
  </div>
</div>

<!-- App -->
<div class="app" id="appPage">
  <div class="app-layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-brand">🎙️ CrispASR TTS</div>
      <nav class="sidebar-nav">
        <div class="nav-item active" data-panel="synthesize" onclick="switchNav('synthesize')">
          <span class="nav-icon">🎤</span> 合成
        </div>
        <div class="nav-item" data-panel="history" onclick="switchNav('history')">
          <span class="nav-icon">📋</span> 历史
        </div>
        <div class="nav-item" data-panel="clone" onclick="switchNav('clone')">
          <span class="nav-icon">🎭</span> 语音克隆
        </div>
        <div class="nav-item" data-panel="compare" onclick="switchNav('compare')">
          <span class="nav-icon">⚖️</span> 对比
        </div>
        <div class="nav-item" data-panel="batch" onclick="switchNav('batch')">
          <span class="nav-icon">📦</span> 批量
        </div>
        <div class="nav-item" data-panel="status" onclick="switchNav('status')">
          <span class="nav-icon">📊</span> 状态
        </div>
        <div class="nav-item" data-panel="logs" onclick="switchNav('logs')">
          <span class="nav-icon">📄</span> 日志
        </div>
        <div class="nav-item" data-panel="model" onclick="switchNav('model')">
          <span class="nav-icon">🧠</span> 模型
        </div>
        <div class="nav-item" data-panel="update" onclick="switchNav('update')">
          <span class="nav-icon">🔄</span> 更新
        </div>
      </nav>
      <div class="sidebar-footer">
        <div class="nav-item" onclick="doLogout()">🚪 退出登录</div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content">

      <!-- Panel: Synthesize (default) -->
      <div class="panel active" id="panelSynthesize">
        <h2>🎤 语音合成</h2>

        <!-- Input -->
        <div class="card">
          <label>输入文本</label>
          <textarea id="textInput" placeholder="输入要转换的文字，长文本会自动分句生成...&#10;&#10;内联标记语法: [音色名]{语气指令}文字&#10;示例: [vivian]{温柔}你好啊 [ryan]{平静}嗯，好久不见"></textarea>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px">
            <span class="hint" id="charCount">0字</span>
            <div style="display:flex;gap:8px">
              <button class="btn-sm" onclick="toggleMarkupHint()">标记语法</button>
              <button class="btn-sm" onclick="previewChunks()">预览分句</button>
            </div>
          </div>
          <div class="markup-hint" id="markupHint">
            在文本中使用内联标记控制每句的音色和语气：<br>
            <code>[vivian]{温柔}你好啊</code> — 用vivian音色、温柔语气说"你好啊"<br>
            <code>[ryan]{平静}嗯</code> — 用ryan音色、平静语气说"嗯"<br>
            <code>{激动}太棒了</code> — 只改语气，音色继承全局<br>
            <code>[aiden]好的</code> — 只改音色，语气继承全局<br>
            标记优先级：内联标记 > 逐句配置 > 全局配置
          </div>
          <div class="chunk-preview" id="chunkPreview">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
              <span class="hint" id="chunkCount">0段</span>
              <button class="btn-sm" onclick="expandAllChunks()">全部展开</button>
            </div>
            <div class="chunk-list" id="chunkList"></div>
          </div>
        </div>

        <!-- Parameters -->
        <div class="card">
          <div class="row" style="margin-bottom:10px">
            <div style="display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap">
              <div style="flex:1;min-width:150px">
                <label>预设</label>
                <select id="presetSelect" onchange="loadPreset()" style="width:100%">
                  <option value="">— 选择预设 —</option>
                </select>
              </div>
              <button class="btn-sm" onclick="saveCurrentPreset()">保存预设</button>
              <button class="btn-sm" onclick="deleteCurrentPreset()">删除</button>
            </div>
          </div>
          <div class="row">
            <div>
              <label>音色 <span style="color:var(--muted);font-weight:400">(全局)</span></label>
              <div class="voice-grid" id="voiceGrid"></div>
            </div>
          </div>
          <div class="row" style="margin-top:12px">
            <div>
              <label>语气指令 <span style="color:var(--muted);font-weight:400">(全局，可选)</span></label>
              <input type="text" id="instructInput" placeholder="用温柔的语气说 / 讲故事的自然语气">
            </div>
          </div>
          <div class="row" style="margin-top:12px">
            <div>
              <label>速度</label>
              <select id="speedSelect">
                <option value="0.7">0.7x 慢速</option>
                <option value="0.85">0.85x 较慢</option>
                <option value="1.0" selected>1.0x 正常</option>
                <option value="1.2">1.2x 较快</option>
                <option value="1.5">1.5x 快速</option>
              </select>
            </div>
            <div>
              <label>格式</label>
              <select id="formatSelect">
                <option value="wav">WAV (无损)</option>
                <option value="mp3">MP3 (压缩)</option>
                <option value="ogg">OGG (压缩)</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Generate -->
        <div class="btn-row">
          <button class="btn-primary" id="generateBtn" onclick="generate()">生成语音</button>
          <button class="btn-secondary" id="resumeBtn" onclick="resumeGeneration()" style="display:none">恢复生成</button>
        </div>

        <!-- Queue -->
        <div id="queueInfo" style="display:none;margin-top:8px;font-size:13px;color:var(--warn)"></div>

        <!-- Progress -->
        <div class="card" id="progressCard" style="display:none">
          <label>生成进度</label>
          <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
          <div class="progress-text" id="progressText">准备中...</div>
        </div>

        <!-- Result -->
        <div class="result-card card" id="resultCard">
          <label>生成结果</label>
          <audio id="audioPlayer" class="audio-player" controls></audio>
          <div class="result-meta" id="resultMeta"></div>
          <div class="btn-row">
            <button class="btn-secondary" onclick="downloadAudio()">下载音频</button>
          </div>
        </div>
      </div>

      <!-- Panel: History -->
      <div class="panel" id="panelHistory">
        <h2>📋 历史记录</h2>
        <div class="card">
          <div class="history-toolbar">
            <input type="text" class="history-search" id="historySearch" placeholder="搜索历史记录..." oninput="debounceSearchHistory()">
            <label class="history-checkall"><input type="checkbox" id="historyCheckAll" onchange="toggleCheckAll(this.checked)"> 全选</label>
            <button class="btn-sm" onclick="batchDeleteHistory()" id="batchDeleteBtn" disabled>删除选中</button>
            <button class="btn-sm" onclick="clearHistory()">清空全部</button>
          </div>
          <div id="historyList"></div>
          <div class="history-footer">
            <span id="historyCount"></span>
            <div>
              <button class="btn-sm" id="historyPrev" onclick="historyPrevPage()" disabled>上一页</button>
              <span id="historyPageInfo"></span>
              <button class="btn-sm" id="historyNext" onclick="historyNextPage()" disabled>下一页</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Panel: Clone -->
      <div class="panel" id="panelClone">
        <h2>🎭 语音克隆</h2>
        <div class="card">
          <label>参考音频管理</label>
          <div id="voiceList" style="margin-bottom:12px"></div>
          <div class="upload-zone" id="uploadZone" onclick="document.getElementById('refAudio').click()">
            <div id="uploadText">📎 点击或拖拽上传参考音频（WAV/MP3，10-15秒）</div>
          </div>
          <input type="file" id="refAudio" accept="audio/*" style="display:none" onchange="uploadRefAudio()">
          <div style="display:flex;gap:8px;margin-top:8px;align-items:center">
            <button class="btn-sm" onclick="startRecording()" id="recordBtn">🎤 录制</button>
            <button class="btn-sm" onclick="stopRecording()" id="stopRecordBtn" style="display:none">⏹ 停止</button>
            <span id="recordStatus" style="font-size:12px;color:var(--muted)"></span>
          </div>
          <div class="hint">上传干净的人声录音，用于克隆音色。需配合支持克隆的模型使用。</div>
        </div>
      </div>

      <!-- Panel: Compare -->
      <div class="panel" id="panelCompare">
        <h2>⚖️ 克隆效果对比</h2>
        <div class="card">
          <div style="display:flex;gap:8px;margin:8px 0;flex-wrap:wrap;align-items:center">
            <div style="flex:1;min-width:120px">
              <label style="font-size:12px">音色 A</label>
              <select id="compareVoiceA" style="width:100%"></select>
            </div>
            <div style="flex:1;min-width:120px">
              <label style="font-size:12px">音色 B</label>
              <select id="compareVoiceB" style="width:100%"></select>
            </div>
          </div>
          <div style="margin:8px 0">
            <textarea id="compareText" rows="2" placeholder="输入对比文本（简短即可，如'你好，今天天气真不错'）" style="width:100%;resize:vertical"></textarea>
          </div>
          <button class="btn-primary" onclick="startCompare()" id="compareBtn">开始对比</button>
          <div id="compareResult" style="display:none;margin-top:12px">
            <div class="compare-row">
              <div class="compare-col">
                <h4>🔊 A: <span id="compareNameA"></span></h4>
                <audio id="compareAudioA" controls></audio>
              </div>
              <div class="compare-col">
                <h4>🔊 B: <span id="compareNameB"></span></h4>
                <audio id="compareAudioB" controls></audio>
              </div>
            </div>
            <div class="compare-status" id="compareStatus"></div>
          </div>
        </div>
      </div>

      <!-- Panel: Batch -->
      <div class="panel" id="panelBatch">
        <h2>📦 批量合成</h2>
        <div class="card">
          <div class="hint" style="margin-bottom:8px">每行一段文本，点击提交自动逐条合成。最多20条。</div>
          <textarea id="batchText" rows="8" placeholder="第一段文字&#10;第二段文字&#10;第三段文字&#10;..." style="width:100%;resize:vertical;font-size:13px"></textarea>
          <div style="display:flex;gap:8px;margin-top:8px;align-items:center">
            <button class="btn-primary" onclick="startBatch()" id="batchBtn">提交批量</button>
            <span id="batchCount" style="font-size:12px;color:var(--muted)"></span>
          </div>
          <div id="batchProgress" style="display:none;margin-top:12px">
            <div class="batch-progress">
              <div class="batch-progress-bar"><div class="batch-progress-fill" id="batchFill" style="width:0%"></div></div>
            </div>
            <div id="batchItems"></div>
          </div>
        </div>
      </div>

      <!-- Panel: Status -->
      <div class="panel" id="panelStatus">
        <h2>📊 服务状态</h2>
        <div class="card">
          <div class="status-grid" id="statusGrid">
            <div class="status-card">
              <h4>CrispASR</h4>
              <div class="status-value" id="statusCrispasr">—</div>
              <div class="status-detail" id="statusCrispasrDetail"></div>
            </div>
            <div class="status-card">
              <h4>任务队列</h4>
              <div class="status-value" id="statusQueue">0</div>
              <div class="status-detail" id="statusQueueDetail"></div>
            </div>
            <div class="status-card">
              <h4>CPU</h4>
              <div class="status-value" id="statusCpu">—</div>
              <div class="status-bar"><div class="status-bar-fill" id="statusCpuBar" style="width:0;background:var(--accent)"></div></div>
            </div>
            <div class="status-card">
              <h4>内存</h4>
              <div class="status-value" id="statusMem">—</div>
              <div class="status-bar"><div class="status-bar-fill" id="statusMemBar" style="width:0;background:#f59e0b"></div></div>
              <div class="status-detail" id="statusMemDetail"></div>
            </div>
            <div class="status-card" style="grid-column:1/-1">
              <h4>磁盘</h4>
              <div class="status-value" id="statusDisk">—</div>
              <div class="status-bar"><div class="status-bar-fill" id="statusDiskBar" style="width:0;background:#22c55e"></div></div>
              <div class="status-detail" id="statusDiskDetail"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Panel: Logs -->
      <div class="panel" id="panelLogs">
        <h2>📄 日志</h2>
        <div class="card">
          <div class="logs-toolbar">
            <input type="text" class="logs-search" id="logsSearch" placeholder="过滤日志..." oninput="debounceFilterLogs()">
            <button class="btn-sm" onclick="loadLogs()">刷新</button>
            <button class="btn-sm" onclick="toggleLogAutoRefresh()" id="logsAutoBtn">自动刷新: 关</button>
          </div>
          <div class="logs-terminal" id="logsTerminal">点击"日志"标签加载...</div>
        </div>
      </div>

      <!-- Panel: Model -->
      <div class="panel" id="panelModel">
        <h2>🧠 模型选择</h2>
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <label style="margin:0">当前模型</label>
            <span class="hint" id="currentModelName">当前: --</span>
          </div>
          <div id="modelList"></div>
          <div class="hint" style="margin-top:8px">切换模型会重启CrispASR服务，约10-20秒不可用</div>
        </div>
      </div>

      <!-- Panel: Update -->
      <div class="panel" id="panelUpdate">
        <h2>🔄 CrispASR 更新</h2>
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <label style="margin:0">版本信息</label>
            <span id="versionInfo" class="hint">当前版本: 检测中...</span>
          </div>
          <div style="display:flex;gap:10px;align-items:center">
            <button class="btn-secondary" onclick="checkUpdate()">检查更新</button>
            <button class="btn-warn" id="updateBtn" onclick="doUpdate()" disabled>更新并编译</button>
            <span id="updateStatus"></span>
          </div>
          <div class="update-log" id="updateLog" style="display:none"></div>
        </div>
      </div>

    </main>
  </div>
</div>

<script>
// ─── State ────────────────────────────
let modelInfo = null;  // {key, voices, has_instruct, has_clone, ...}
let selectedVoice = 'serena';
let currentAudioUrl = null;
let currentFmt = 'wav';
let taskId = null;
let pollTimer = null;
let uploadedVoice = null;
let chunksConfig = [];  // [{text, voice, instruct}, ...]

// ─── Auth ─────────────────────────────
function getToken() { return localStorage.getItem('tts_token') }
function setToken(t) { localStorage.setItem('tts_token', t) }
function clearToken() { localStorage.removeItem('tts_token') }

async function apiFetch(url, opts = {}) {
  const token = getToken();
  const headers = opts.headers || {};
  if (token) headers['Authorization'] = 'Bearer ' + token;
  // Only set Content-Type for non-FormData bodies (browser sets multipart boundary automatically)
  if (opts.body && !(opts.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }
  const resp = await fetch(url, { ...opts, headers });
  if (resp.status === 401) { doLogout(); throw new Error('登录已过期'); }
  return resp;
}

async function doLogin() {
  const pwd = document.getElementById('loginPassword').value;
  const errEl = document.getElementById('loginError');
  try {
    const resp = await fetch('/api/login', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({password: pwd}),
    });
    const data = await resp.json();
    if (data.token) {
      setToken(data.token);
      showApp();
    } else {
      errEl.style.display = 'block';
      errEl.textContent = data.error || '登录失败';
    }
  } catch(e) {
    errEl.style.display = 'block';
    errEl.textContent = '网络错误';
  }
}

function doLogout() {
  clearToken();
  document.getElementById('loginPage').style.display = 'flex';
  document.getElementById('appPage').style.display = 'none';
}

async function checkAuth() {
  const token = getToken();
  if (!token) return false;
  try {
    const resp = await fetch('/api/check', {headers:{'Authorization':'Bearer '+token}});
    return resp.ok;
  } catch { return false; }
}

function showApp() {
  document.getElementById('loginPage').style.display = 'none';
  document.getElementById('appPage').style.display = 'block';
  loadModelInfo();
  // History/Status/Logs loaded on-demand when user navigates to those panels
}

// ─── Model ────────────────────────────
async function loadModelInfo() {
  try {
    const resp = await apiFetch('/api/model');
    modelInfo = await resp.json();
    document.getElementById('currentModelName').textContent = '当前: ' + (modelInfo.description || modelInfo.key);
    renderVoices();
    loadModelList();
  } catch(e) { console.error(e); }
}

function renderVoices() {
  const grid = document.getElementById('voiceGrid');
  grid.innerHTML = '';
  const voices = modelInfo ? modelInfo.voices || [] : [];
  
  if (!voices.length) {
    grid.innerHTML = '<div class="hint">当前模型无内置音色</div>';
    return;
  }
  
  voices.forEach(v => {
    const btn = document.createElement('div');
    btn.className = 'voice-btn' + (v===selectedVoice?' active':'');
    btn.textContent = v;
    btn.onclick = () => {
      grid.querySelectorAll('.voice-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      selectedVoice = v;
    };
    grid.appendChild(btn);
  });
  
  // If selected voice not in list, reset to first
  if (!voices.includes(selectedVoice) && voices.length) {
    selectedVoice = voices[0];
    grid.querySelector('.voice-btn').classList.add('active');
  }
}

async function loadModelList() {
  try {
    const resp = await apiFetch('/api/models');
    const models = await resp.json();
    const list = document.getElementById('modelList');
    list.innerHTML = '';
    models.forEach(m => {
      const div = document.createElement('div');
      div.className = 'model-card' + (m.key === (modelInfo?.key) ? ' active' : '');
      const nameSpan = document.createElement('div');
      nameSpan.className = 'model-name';
      nameSpan.textContent = m.key;
      const descSpan = document.createElement('div');
      descSpan.className = 'model-desc';
      descSpan.textContent = m.description || '';
      const wrapper = document.createElement('div');
      wrapper.appendChild(nameSpan);
      wrapper.appendChild(descSpan);
      div.appendChild(wrapper);
      div.onclick = () => switchModel(m.key);
      list.appendChild(div);
    });
  } catch(e) { console.error(e); }
}

async function switchModel(key) {
  if (!confirm(`切换到 ${key}？CrispASR服务将重启约10-20秒。`)) return;
  try {
    const resp = await apiFetch('/api/model/switch', {
      method: 'POST',
      body: JSON.stringify({model: key}),
    });
    const data = await resp.json();
    alert(data.message);
    if (data.success) loadModelInfo();
  } catch(e) { alert('切换失败: ' + e.message); }
}

// ─── CrispASR Update ──────────────────
async function checkUpdate() {
  const el = document.getElementById('versionInfo');
  el.textContent = '检查中...';
  try {
    const resp = await apiFetch('/api/crispasr/version');
    const data = await resp.json();
    el.textContent = `当前: ${data.current} | 最新: ${data.latest || '检查失败'}`;
    const btn = document.getElementById('updateBtn');
    if (data.latest && data.latest !== data.current) {
      btn.disabled = false;
      btn.textContent = `更新到 ${data.latest}`;
    } else if (data.latest === data.current) {
      btn.disabled = true;
      btn.textContent = '已是最新';
    }
  } catch(e) { el.textContent = '检查失败'; }
}

async function doUpdate() {
  const btn = document.getElementById('updateBtn');
  const statusEl = document.getElementById('updateStatus');
  const logEl = document.getElementById('updateLog');
  btn.disabled = true;
  statusEl.innerHTML = '<span class="spinner"></span>更新中...';
  logEl.style.display = 'block';
  logEl.textContent = '开始更新...';
  
  try {
    const resp = await apiFetch('/api/crispasr/update', { method: 'POST' });
    const data = await resp.json();
    logEl.textContent = data.log || data.message;
    if (data.success) {
      statusEl.textContent = '✅ ' + data.message;
      loadModelInfo();
      checkUpdate();  // Refresh version info after update
    } else {
      statusEl.textContent = '❌ ' + data.message;
    }
  } catch(e) {
    statusEl.textContent = '❌ 请求失败';
    logEl.textContent = e.message;
  }
  btn.disabled = false;
  btn.textContent = '更新并编译';
}

// ─── Init ─────────────────────────────
async function init() {
  if (await checkAuth()) showApp();
  document.getElementById('textInput').addEventListener('input', function(){
    document.getElementById('charCount').textContent = this.value.length + '字';
    // Invalidate chunk preview when text changes
    chunksConfig = [];
    document.getElementById('chunkPreview').classList.remove('show');
  });
  // Drag & drop upload
  const zone = document.getElementById('uploadZone');
  zone.ondragover = e => { e.preventDefault(); zone.style.borderColor='var(--accent)'; };
  zone.ondragleave = () => { zone.style.borderColor=''; };
  zone.ondrop = e => {
    e.preventDefault(); zone.style.borderColor='';
    if (e.dataTransfer.files.length) {
      document.getElementById('refAudio').files = e.dataTransfer.files;
      uploadRefAudio();
    }
  };
  // Check for resumable tasks
  checkResumable();
  // Load presets
  loadPresets();
}

// ─── Markup Hint ──────────────────────
function toggleMarkupHint() {
  document.getElementById('markupHint').classList.toggle('show');
}

// ─── Chunk Preview with Per-Chunk Controls ────
async function previewChunks() {
  const text = document.getElementById('textInput').value.trim();
  if (!text) return;
  try {
    const resp = await apiFetch('/api/split', {
      method: 'POST',
      body: JSON.stringify({text}),
    });
    const data = await resp.json();
    chunksConfig = data.chunks;
    renderChunks();
  } catch(e) { console.error(e); }
}

function renderChunks() {
  const list = document.getElementById('chunkList');
  list.innerHTML = '';
  const globalVoice = selectedVoice;
  const globalInstruct = document.getElementById('instructInput').value.trim();
  const voices = modelInfo ? modelInfo.voices || [] : [];
  const hasInstruct = modelInfo ? modelInfo.has_instruct : true;
  
  chunksConfig.forEach((c, i) => {
    const div = document.createElement('div');
    div.className = 'chunk-item';
    div.dataset.index = i;
    
    const effectiveVoice = c.voice || globalVoice;
    const effectiveInstruct = c.instruct || globalInstruct;
    
    // Voice badge
    let voiceBadge = '';
    if (c.voice && c.voice !== globalVoice) {
      voiceBadge = `<span style="color:var(--accent2);font-size:11px;background:rgba(99,102,241,.15);padding:1px 6px;border-radius:4px;margin-left:4px">🎤 ${c.voice}</span>`;
    }
    let instructBadge = '';
    if (c.instruct && c.instruct !== globalInstruct) {
      instructBadge = `<span style="color:var(--warn);font-size:11px;background:rgba(245,158,11,.1);padding:1px 6px;border-radius:4px;margin-left:4px">💭 ${c.instruct}</span>`;
    }
    
    div.innerHTML = `
      <span class="chunk-num">${i+1}.</span>
      <span class="chunk-text">${escHtml(c.text)}</span>
      ${voiceBadge}${instructBadge}
      <button class="chunk-expand" onclick="toggleChunkExpand(${i})" title="配置">⚙️</button>
      <div class="chunk-controls">
        ${voices.length ? `<select onchange="setChunkVoice(${i},this.value)" data-field="voice">
          <option value="">继承全局(${globalVoice})</option>
          ${voices.map(v=>`<option value="${v}"${c.voice===v?' selected':''}>${v}</option>`).join('')}
        </select>` : ''}
        ${hasInstruct ? `<input type="text" placeholder="语气指令(继承全局)" value="${escAttr(c.instruct)}" onchange="setChunkInstruct(${i},this.value)">` : ''}
        <button class="chunk-audition" onclick="auditionChunk(${i})" title="试听此句">▶ 试听</button>
      </div>
    `;
    list.appendChild(div);
  });
  
  document.getElementById('chunkCount').textContent = `${chunksConfig.length}段`;
  document.getElementById('chunkPreview').classList.add('show');
}

function escHtml(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function escAttr(s) { return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function toggleChunkExpand(i) {
  const item = document.querySelector(`.chunk-item[data-index="${i}"]`);
  item.classList.toggle('expanded');
}

function expandAllChunks() {
  document.querySelectorAll('.chunk-item').forEach(el => el.classList.add('expanded'));
}

function setChunkVoice(i, voice) {
  if (chunksConfig[i]) chunksConfig[i].voice = voice;
}

function setChunkInstruct(i, instruct) {
  if (chunksConfig[i]) chunksConfig[i].instruct = instruct;
}

// ─── Single Chunk Audition ────────────
async function auditionChunk(i) {
  const chunk = chunksConfig[i];
  if (!chunk) return;
  const voice = chunk.voice || selectedVoice;
  const instruct = chunk.instruct || document.getElementById('instructInput').value.trim();
  const speed = parseFloat(document.getElementById('speedSelect').value);
  
  try {
    const resp = await apiFetch('/api/audition', {
      method: 'POST',
      body: JSON.stringify({text: chunk.text, voice, instruct, speed}),
    });
    if (!resp.ok) throw new Error('试听失败');
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const player = document.getElementById('audioPlayer');
    player.src = url;
    player.play().catch(()=>{});
    document.getElementById('resultCard').classList.add('show');
  } catch(e) { alert('试听失败: ' + e.message); }
}

// ─── Resume ───────────────────────────
async function checkResumable() {
  try {
    const resp = await apiFetch('/api/resumable');
    const data = await resp.json();
    const btn = document.getElementById('resumeBtn');
    if (data.task_id) {
      btn.style.display = 'inline-block';
      btn.textContent = `恢复生成 (${data.completed}/${data.total}段已完成)`;
    }
  } catch(e) {}
}

async function resumeGeneration() {
  try {
    const resp = await apiFetch('/api/resume', { method: 'POST' });
    const data = await resp.json();
    if (data.task_id) {
      taskId = data.task_id;
      document.getElementById('resumeBtn').style.display = 'none';
      document.getElementById('generateBtn').disabled = true;
      document.getElementById('progressCard').style.display = 'block';
      pollProgress();
    }
  } catch(e) { alert('恢复失败: ' + e.message); }
}

// ─── Generate ─────────────────────────
async function generate() {
  const text = document.getElementById('textInput').value.trim();
  if (!text) { alert('请输入文本'); return; }

  const btn = document.getElementById('generateBtn');
  const progressCard = document.getElementById('progressCard');

  btn.disabled = true;
  btn.textContent = '生成中...';
  progressCard.style.display = 'block';
  document.getElementById('resultCard').classList.remove('show');
  document.getElementById('progressFill').style.width = '0%';
  document.getElementById('progressText').textContent = '提交任务...';

  const instruct = document.getElementById('instructInput').value.trim();
  const speed = parseFloat(document.getElementById('speedSelect').value);
  const fmt = document.getElementById('formatSelect').value;
  currentFmt = fmt;

  // Use chunksConfig if available, otherwise let backend split
  const body = {
    text,
    voice: selectedVoice,
    instruct,
    speed,
    fmt,
    chunks_config: chunksConfig.length ? chunksConfig : null,
  };

  try {
    const resp = await apiFetch('/api/generate', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!data.task_id) throw new Error(data.error || '创建任务失败');
    taskId = data.task_id;
    
    // Show queue info
    if (data.queue_pos > 0) {
      document.getElementById('queueInfo').style.display = 'block';
      document.getElementById('queueInfo').textContent = `队列中第 ${data.queue_pos} 位`;
    } else {
      document.getElementById('queueInfo').style.display = 'none';
    }
    
    pollProgress();
  } catch(e) {
    document.getElementById('progressText').textContent = '❌ ' + e.message;
    btn.disabled = false;
    btn.textContent = '生成语音';
  }
}

function pollProgress() {
  if (pollTimer) clearInterval(pollTimer);
  let pollAttempts = 0;
  const maxAttempts = 300; // 300 * 2s = 10 min timeout
  pollTimer = setInterval(async () => {
    pollAttempts++;
    if (pollAttempts > maxAttempts) {
      clearInterval(pollTimer);
      document.getElementById('progressText').textContent = '⏰ 生成超时，请重试';
      document.getElementById('generateBtn').disabled = false;
      document.getElementById('generateBtn').textContent = '生成语音';
      return;
    }
    try {
      const resp = await apiFetch(`/api/task/${taskId}`);
      const data = await resp.json();
      const fill = document.getElementById('progressFill');
      const ptxt = document.getElementById('progressText');

      fill.style.width = (data.progress || 0) + '%';

      if (data.status === 'queued') {
        ptxt.innerHTML = `<span class="spinner"></span>队列中第 ${escHtml(String(data.queue_pos || '?'))} 位...`;
      } else if (data.status === 'generating') {
        ptxt.innerHTML = `<span class="spinner"></span>正在生成 ${escHtml(String(data.current))}/${escHtml(String(data.total))} 段... (${escHtml(String(data.progress))}%)`;
      } else if (data.status === 'done') {
        clearInterval(pollTimer);
        fill.style.width = '100%';
        ptxt.textContent = '✅ 生成完成';
        showResult(data.audio_url, data.duration);
        document.getElementById('generateBtn').disabled = false;
        document.getElementById('generateBtn').textContent = '生成语音';
        document.getElementById('queueInfo').style.display = 'none';
        loadHistory();
      } else if (data.status === 'error') {
        clearInterval(pollTimer);
        ptxt.textContent = '❌ ' + (data.error || '生成失败');
        document.getElementById('generateBtn').disabled = false;
        document.getElementById('generateBtn').textContent = '生成语音';
        document.getElementById('queueInfo').style.display = 'none';
      }
    } catch(e) { console.error(e); }
  }, 2000);
}

function showResult(audioUrl, duration) {
  const token = getToken();
  const sep = audioUrl.includes('?') ? '&' : '?';
  currentAudioUrl = audioUrl + sep + 'token=' + encodeURIComponent(token);
  const player = document.getElementById('audioPlayer');
  player.src = currentAudioUrl;
  player.play().catch(()=>{});
  const dur = duration ? duration.toFixed(1) + '秒' : '';
  document.getElementById('resultMeta').textContent = dur ? `时长: ${dur}` : '';
  document.getElementById('resultCard').classList.add('show');
}

function downloadAudio() {
  if (!currentAudioUrl) return;
  const a = document.createElement('a');
  a.href = currentAudioUrl;
  a.download = `tts_${selectedVoice}_${Date.now()}.${currentFmt}`;
  a.click();
}

// ─── Voice Clone ──────────────────────
async function uploadRefAudio() {
  const file = document.getElementById('refAudio').files[0];
  if (!file) return;
  const zone = document.getElementById('uploadZone');
  zone.classList.add('has-file');
  document.getElementById('uploadText').textContent = '📁 ' + file.name;

  const form = new FormData();
  form.append('audio', file);
  form.append('name', file.name.replace(/\.[^.]+$/, ''));

  try {
    const token = getToken();
    const resp = await fetch('/api/voices', {
      method: 'POST',
      headers: {'Authorization': 'Bearer '+token},
      body: form,
    });
    const data = await resp.json();
    if (data.name) {
      uploadedVoice = data.name;
      const grid = document.getElementById('voiceGrid');
      const btn = document.createElement('div');
      btn.className = 'voice-btn active';
      btn.textContent = '🎤 ' + data.name;
      grid.querySelectorAll('.voice-btn').forEach(b=>b.classList.remove('active'));
      btn.onclick = () => {
        grid.querySelectorAll('.voice-btn').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        selectedVoice = data.name;
      };
      grid.prepend(btn);
      selectedVoice = data.name;
    }
  } catch(e) {
    alert('上传失败: ' + e.message);
    zone.classList.remove('has-file');
    document.getElementById('uploadText').textContent = '📎 点击或拖拽上传参考音频';
  }
  loadVoiceList();
}

// ─── Voice Management ─────────────────
async function loadVoiceList() {
  try {
    const resp = await apiFetch('/api/voices');
    const voices = await resp.json();
    const el = document.getElementById('voiceList');
    if (!voices.length) { el.innerHTML = '<div style="color:var(--muted);font-size:12px;padding:4px 0">暂无参考音频</div>'; return; }
    el.innerHTML = voices.map(v => `
      <div class="voice-item">
        <div>
          <span class="voice-name">${escHtml(v.name)}</span>
          <span class="voice-meta">${v.duration ? v.duration+'s' : ''} · ${v.filename}</span>
        </div>
        <div class="voice-item-actions">
          <button onclick="playVoice('${escAttr(v.filename)}')">▶</button>
          <button onclick="selectVoice('${escAttr(v.name)}')">选</button>
          <button onclick="deleteVoice('${escAttr(v.name)}')">✕</button>
        </div>
      </div>
    `).join('');
  } catch(e) { console.error(e); }
}

function playVoice(filename) {
  const token = getToken();
  const a = new Audio('/uploads/' + encodeURIComponent(filename) + '?token=' + token);
  a.play().catch(e => alert('播放失败: ' + e.message));
}

function selectVoice(name) {
  selectedVoice = name;
  const grid = document.getElementById('voiceGrid');
  grid.querySelectorAll('.voice-btn').forEach(b => {
    b.classList.remove('active');
    if (b.textContent.replace('🎤 ','') === name) b.classList.add('active');
  });
}

async function deleteVoice(name) {
  if (!confirm(`确定删除参考音频 "${name}"？`)) return;
  try {
    await apiFetch(`/api/voices/${encodeURIComponent(name)}`, {method:'DELETE'});
    // Remove from voice grid
    const grid = document.getElementById('voiceGrid');
    grid.querySelectorAll('.voice-btn').forEach(b => {
      if (b.textContent.replace('🎤 ','') === name) b.remove();
    });
    if (selectedVoice === name) selectedVoice = 'serena';
    loadVoiceList();
  } catch(e) { alert('删除失败: ' + e.message); }
}

// ─── Microphone Recording ──────────────
let mediaRecorder = null;
let recordedChunks = [];

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    mediaRecorder = new MediaRecorder(stream);
    recordedChunks = [];
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) recordedChunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(recordedChunks, {type: 'audio/webm'});
      const form = new FormData();
      const ts = new Date().toISOString().slice(0,19).replace(/[:-]/g,'');
      form.append('audio', blob, `rec_${ts}.webm`);
      form.append('name', `rec_${ts}`);
      try {
        const token = getToken();
        const resp = await fetch('/api/voices', {method:'POST', headers:{'Authorization':'Bearer '+token}, body:form});
        const data = await resp.json();
        if (data.name) {
          uploadedVoice = data.name;
          selectedVoice = data.name;
          loadVoiceList();
        }
      } catch(e) { alert('录制上传失败: ' + e.message); }
      document.getElementById('recordBtn').style.display = '';
      document.getElementById('stopRecordBtn').style.display = 'none';
      document.getElementById('recordStatus').textContent = '';
    };
    mediaRecorder.start();
    document.getElementById('recordBtn').style.display = 'none';
    document.getElementById('stopRecordBtn').style.display = '';
    document.getElementById('recordStatus').textContent = '🔴 录音中...';
  } catch(e) { alert('无法访问麦克风: ' + e.message); }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
}

// ─── Voice Compare ────────────────────
async function loadCompareVoices() {
  try {
    const resp = await apiFetch('/api/voices');
    const customVoices = await resp.json();
    const builtIn = (modelInfo && modelInfo.voices ? modelInfo.voices : ['serena'])
      .map(v => `<option value="${escAttr(v)}">${escHtml(v)}</option>`).join('');
    const custom = customVoices.map(v => `<option value="${escAttr(v.name)}">${escHtml(v.name)}</option>`).join('');
    document.getElementById('compareVoiceA').innerHTML = builtIn + custom;
    document.getElementById('compareVoiceB').innerHTML = builtIn + custom;
  } catch(e) { console.error(e); }
}

async function startCompare() {
  const voiceA = document.getElementById('compareVoiceA').value;
  const voiceB = document.getElementById('compareVoiceB').value;
  const text = document.getElementById('compareText').value.trim();
  if (!text) { alert('请输入对比文本'); return; }
  if (!voiceA || !voiceB) { alert('请选择两个音色'); return; }

  document.getElementById('compareBtn').disabled = true;
  document.getElementById('compareResult').style.display = '';
  document.getElementById('compareNameA').textContent = voiceA;
  document.getElementById('compareNameB').textContent = voiceB;
  document.getElementById('compareAudioA').src = '';
  document.getElementById('compareAudioB').src = '';
  document.getElementById('compareStatus').textContent = '正在合成...';

  try {
    const resp = await apiFetch('/api/compare', {
      method: 'POST',
      body: JSON.stringify({
        voice_a: voiceA, voice_b: voiceB, text: text,
        speed: parseFloat(document.getElementById('speedSelect').value),
        fmt: document.getElementById('formatSelect').value,
        instruct: document.getElementById('instructInput').value.trim(),
      }),
    });
    const data = await resp.json();
    if (data.error) { alert(data.error); return; }
    // Poll both tasks (await so button stays disabled during polling)
    await pollCompareTasks(data.task_a, data.task_b);
  } catch(e) {
    alert('对比请求失败: ' + e.message);
    document.getElementById('compareBtn').disabled = false;
  }
}

async function pollCompareTasks(taskIdA, taskIdB) {
  const statusEl = document.getElementById('compareStatus');
  let doneA = false, doneB = false;
  const maxAttempts = 150; // 150 * 2s = 5 min timeout
  let attempts = 0;

  while ((!doneA || !doneB) && attempts < maxAttempts) {
    await new Promise(r => setTimeout(r, 2000));
    attempts++;
    if (!doneA) {
      try {
        const r = await apiFetch(`/api/task/${taskIdA}`);
        const d = await r.json();
        if (d.status === 'done' && d.audio_url) {
          doneA = true;
          const token = getToken();
          document.getElementById('compareAudioA').src = d.audio_url + (d.audio_url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(token);
        } else if (d.status === 'error') {
          doneA = true;
          statusEl.textContent = 'A 合成失败: ' + (d.error || '未知错误');
        }
      } catch(e) {}
    }
    if (!doneB) {
      try {
        const r = await apiFetch(`/api/task/${taskIdB}`);
        const d = await r.json();
        if (d.status === 'done' && d.audio_url) {
          doneB = true;
          const token = getToken();
          document.getElementById('compareAudioB').src = d.audio_url + (d.audio_url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(token);
        } else if (d.status === 'error') {
          doneB = true;
          statusEl.textContent = 'B 合成失败: ' + (d.error || '未知错误');
        }
      } catch(e) {}
    }
    const cnt = (doneA ? 1 : 0) + (doneB ? 1 : 0);
    statusEl.textContent = `合成中... ${cnt}/2 完成`;
  }
  if (attempts >= maxAttempts && (!doneA || !doneB)) {
    statusEl.textContent = '⏰ 对比超时，请重试';
  } else {
    statusEl.textContent = '对比完成！点击播放试听';
  }
  document.getElementById('compareBtn').disabled = false;
}

// ─── Batch Synthesize ─────────────────
let batchTaskIds = [];
let batchPollTimer = null;
let batchPollAttempts = 0;

document.getElementById('batchText').addEventListener('input', function() {
  const lines = this.value.split('\n').filter(l => l.trim());
  document.getElementById('batchCount').textContent = lines.length ? `${lines.length} 条` : '';
});

async function startBatch() {
  const text = document.getElementById('batchText').value;
  const lines = text.split('\n').map(l => l.trim()).filter(l => l);
  if (!lines.length) { alert('请输入至少一段文本'); return; }
  if (lines.length > 20) { alert('最多20条'); return; }

  document.getElementById('batchBtn').disabled = true;
  document.getElementById('batchProgress').style.display = '';

  try {
    const resp = await apiFetch('/api/batch', {
      method: 'POST',
      body: JSON.stringify({
        texts: lines,
        voice: selectedVoice,
        speed: parseFloat(document.getElementById('speedSelect').value),
        fmt: document.getElementById('formatSelect').value,
        instruct: document.getElementById('instructInput').value.trim(),
      }),
    });
    const data = await resp.json();
    if (data.error) { alert(data.error); return; }
    batchTaskIds = data.task_ids;
    batchPollAttempts = 0;
    // Render items
    const el = document.getElementById('batchItems');
    el.innerHTML = batchTaskIds.map((id, i) =>
      `<div class="batch-item" data-batch-id="${escAttr(id)}">
        <span class="batch-item-text">${escHtml(lines[i])}</span>
        <span class="batch-item-status" data-batch-id="${escAttr(id)}">⏳</span>
      </div>`
    ).join('');
    // Start polling
    pollBatchTasks();  // async timer-based, button re-enabled when all done
  } catch(e) {
    alert('批量提交失败: ' + e.message);
    document.getElementById('batchBtn').disabled = false;
  }
}

async function pollBatchTasks() {
  let done = 0;
  const total = batchTaskIds.length;

  batchPollAttempts++;
  if (batchPollAttempts > 300) { // 300 * 2s = 10 min
    document.getElementById('batchCount').textContent = '⏰ 批量超时';
    document.getElementById('batchBtn').disabled = false;
    return;
  }

  for (const id of batchTaskIds) {
    const statusEl = document.querySelector(`.batch-item-status[data-batch-id="${CSS.escape(id)}"]`);
    if (!statusEl) continue;
    if (statusEl.dataset.done) { done++; continue; }

    try {
      const r = await apiFetch(`/api/task/${encodeURIComponent(id)}`);
      const d = await r.json();
      if (d.status === 'done') {
        statusEl.textContent = '✅';
        statusEl.dataset.done = '1';
        done++;
      } else if (d.status === 'error') {
        statusEl.textContent = '❌';
        statusEl.dataset.done = '1';
        done++;
      } else if (d.status === 'generating') {
        statusEl.textContent = '🔄';
      } else {
        statusEl.textContent = '⏳';
      }
    } catch(e) {}
  }

  document.getElementById('batchFill').style.width = `${(done/total)*100}%`;

  if (done < total) {
    batchPollTimer = setTimeout(pollBatchTasks, 2000);
  } else {
    document.getElementById('batchCount').textContent = `全部完成 ${done}/${total}`;
    document.getElementById('batchBtn').disabled = false;
  }
}

// ─── History ──────────────────────────
let historyPage = 1;
let historyPages = 1;
let historySearchQ = '';
let historySearchTimer = null;
let historyChecked = new Set();

function debounceSearchHistory() {
  clearTimeout(historySearchTimer);
  historySearchTimer = setTimeout(() => {
    historySearchQ = document.getElementById('historySearch').value.trim();
    historyPage = 1;
    loadHistory();
  }, 300);
}

function historyPrevPage() {
  if (historyPage > 1) { historyPage--; loadHistory(); }
}

function historyNextPage() {
  if (historyPage < historyPages) { historyPage++; loadHistory(); }
}

async function loadHistory() {
  try {
    const q = encodeURIComponent(historySearchQ);
    const resp = await apiFetch(`/api/history?page=${historyPage}&per_page=20&q=${q}`);
    const data = await resp.json();
    const items = data.items || [];
    historyPages = data.pages || 1;
    const total = data.total || 0;
    const list = document.getElementById('historyList');

    // Update footer
    document.getElementById('historyCount').textContent = `共 ${total} 条`;
    document.getElementById('historyPageInfo').textContent = `${data.page}/${historyPages}`;
    document.getElementById('historyPrev').disabled = data.page <= 1;
    document.getElementById('historyNext').disabled = data.page >= historyPages;

    if (!items.length) {
      list.innerHTML = '<div style="color:var(--muted);font-size:13px;text-align:center;padding:16px">暂无记录</div>';
      return;
    }
    list.innerHTML = '';
    items.forEach(item => {
      const div = document.createElement('div');
      div.className = 'history-item';
      const time = new Date(item.created_at*1000).toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'});
      const dur = item.duration ? item.duration.toFixed(1)+'s' : '';
      const statusIcon = item.status==='done'?'✅':item.status==='error'?'❌':'⏳';
      const checked = historyChecked.has(item.id) ? 'checked' : '';

      div.innerHTML = `
        <input type="checkbox" class="history-check" data-id="${item.id}" ${checked} onchange="onHistoryCheck()">
        <div class="history-body">
          <div class="history-text" title="${escAttr(item.text)}" onclick="regenerateFromHistory('${item.id}')">${statusIcon} ${escHtml(item.text.slice(0,80))}</div>
          <div class="history-meta">${escHtml(item.voice)} · ${dur} · ${time}</div>
        </div>
        <div class="history-actions">
          ${item.audio_file ? `<button class="btn-sm" onclick="playHistory('${item.audio_file}')">▶</button>` : ''}
          ${item.audio_file ? `<button class="btn-sm" onclick="downloadHistoryAudio('${item.audio_file}','${item.id}')">⬇</button>` : ''}
          <button class="btn-sm" onclick="regenerateFromHistory('${item.id}')" title="重新生成">🔄</button>
          <button class="btn-sm" onclick="deleteHistoryItem('${item.id}')" title="删除">🗑</button>
        </div>
      `;
      list.appendChild(div);
    });
    updateCheckAllState();
  } catch(e) { console.error(e); }
}

function onHistoryCheck() {
  const checks = document.querySelectorAll('.history-check');
  historyChecked.clear();
  checks.forEach(c => { if (c.checked) historyChecked.add(c.dataset.id); });
  document.getElementById('batchDeleteBtn').disabled = historyChecked.size === 0;
  updateCheckAllState();
}

function updateCheckAllState() {
  const checks = document.querySelectorAll('.history-check');
  const allChecked = checks.length > 0 && [...checks].every(c => c.checked);
  document.getElementById('historyCheckAll').checked = allChecked;
}

function toggleCheckAll(checked) {
  const checks = document.querySelectorAll('.history-check');
  historyChecked.clear();
  checks.forEach(c => {
    c.checked = checked;
    if (checked) historyChecked.add(c.dataset.id);
  });
  document.getElementById('batchDeleteBtn').disabled = historyChecked.size === 0;
}

async function deleteHistoryItem(id) {
  if (!confirm('确定删除此记录？')) return;
  await apiFetch(`/api/history/${id}`, {method:'DELETE'});
  historyChecked.delete(id);
  loadHistory();
}

async function batchDeleteHistory() {
  if (!confirm(`确定删除选中的 ${historyChecked.size} 条记录？`)) return;
  await apiFetch('/api/history/batch', {
    method:'POST',
    body: JSON.stringify({ids: [...historyChecked]}),
  });
  historyChecked.clear();
  loadHistory();
}

async function regenerateFromHistory(id) {
  try {
    const resp = await apiFetch(`/api/history/${encodeURIComponent(id)}`);
    if (!resp.ok) { alert('记录不存在'); return; }
    const item = await resp.json();
    // Switch to synthesize panel and fill in
    switchNav('synthesize');
    document.getElementById('textInput').value = item.text;
    document.getElementById('charCount').textContent = item.text.length + '字';
    // Set voice
    const voiceBtns = document.querySelectorAll('.voice-btn');
    voiceBtns.forEach(b => {
      b.classList.remove('active');
      if (b.textContent.replace('🎤 ','') === item.voice) {
        b.classList.add('active');
        selectedVoice = item.voice;
      }
    });
    if (item.instruct) document.getElementById('instructInput').value = item.instruct;
    if (item.speed) document.getElementById('speedSelect').value = item.speed;
  } catch(e) { alert('加载失败: ' + e.message); }
}

function downloadHistoryAudio(audioFile, id) {
  const token = getToken();
  const url = `/api/audio/${audioFile}?token=${encodeURIComponent(token)}`;
  const a = document.createElement('a');
  a.href = url;
  a.download = `tts_${id}.wav`;
  a.click();
}

async function playHistory(audioFile) {
  const token = getToken();
  currentAudioUrl = `/api/audio/${audioFile}?token=${encodeURIComponent(token)}`;
  document.getElementById('audioPlayer').src = currentAudioUrl;
  document.getElementById('audioPlayer').play().catch(()=>{});
  document.getElementById('resultCard').classList.add('show');
}

async function clearHistory() {
  if (!confirm('确定清空所有历史记录？')) return;
  await apiFetch('/api/history', {method:'DELETE'});
  historyChecked.clear();
  loadHistory();
}

// ─── Status ───────────────────────────
let statusTimer = null;

async function loadStatus() {
  try {
    const resp = await apiFetch('/api/status');
    const s = await resp.json();

    // CrispASR
    const el = document.getElementById('statusCrispasr');
    el.textContent = s.crispasr.active ? '运行中' : '已停止';
    el.className = 'status-value ' + (s.crispasr.active ? 'status-on' : 'status-off');
    document.getElementById('statusCrispasrDetail').textContent = s.crispasr.pid ? `PID ${s.crispasr.pid}` : '';

    // Queue
    const qd = s.queue.depth;
    document.getElementById('statusQueue').textContent = qd;
    document.getElementById('statusQueueDetail').textContent = s.queue.active ? '处理中...' : '空闲';

    // CPU
    const cpuPct = s.cpu.percent;
    document.getElementById('statusCpu').textContent = cpuPct + '%';
    document.getElementById('statusCpuBar').style.width = cpuPct + '%';
    document.getElementById('statusCpuBar').style.background = cpuPct > 80 ? '#ef4444' : cpuPct > 50 ? '#f59e0b' : 'var(--accent)';

    // Memory
    const memPct = s.memory.percent;
    document.getElementById('statusMem').textContent = memPct + '%';
    document.getElementById('statusMemBar').style.width = memPct + '%';
    document.getElementById('statusMemBar').style.background = memPct > 85 ? '#ef4444' : '#f59e0b';
    document.getElementById('statusMemDetail').textContent = `${s.memory.used_mb} / ${s.memory.total_mb} MB`;

    // Disk
    const dskPct = s.disk.disk_percent;
    document.getElementById('statusDisk').textContent = `${s.disk.disk_used_gb} / ${s.disk.disk_total_gb} GB (${dskPct}%)`;
    document.getElementById('statusDiskBar').style.width = dskPct + '%';
    document.getElementById('statusDiskBar').style.background = dskPct > 90 ? '#ef4444' : '#22c55e';
    document.getElementById('statusDiskDetail').textContent = `音频 ${s.disk.audio_files} 个, ${s.disk.audio_size_mb} MB | 剩余 ${s.disk.disk_free_gb} GB`;
  } catch(e) { console.error('Status error:', e); }
}

function startStatusRefresh() {
  loadStatus();
  if (!statusTimer) statusTimer = setInterval(loadStatus, 5000);
}

function stopStatusRefresh() {
  if (statusTimer) { clearInterval(statusTimer); statusTimer = null; }
}

// ─── Logs ─────────────────────────────
let logsAutoRefresh = false;
let logsTimer = null;
let logsFilterTimer = null;
let lastLogsRaw = '';

async function loadLogs() {
  try {
    const q = document.getElementById('logsSearch').value.trim();
    const resp = await apiFetch(`/api/logs?lines=200&q=${encodeURIComponent(q)}`);
    const data = await resp.json();
    const term = document.getElementById('logsTerminal');
    lastLogsRaw = data.logs || '';
    term.textContent = lastLogsRaw || '(无日志)';
    term.scrollTop = term.scrollHeight;
  } catch(e) { console.error('Logs error:', e); }
}

function debounceFilterLogs() {
  clearTimeout(logsFilterTimer);
  logsFilterTimer = setTimeout(loadLogs, 500);
}

function toggleLogAutoRefresh() {
  logsAutoRefresh = !logsAutoRefresh;
  document.getElementById('logsAutoBtn').textContent = '自动刷新: ' + (logsAutoRefresh ? '开' : '关');
  if (logsAutoRefresh) {
    loadLogs();
    if (!logsTimer) logsTimer = setInterval(loadLogs, 3000);
  } else {
    if (logsTimer) { clearInterval(logsTimer); logsTimer = null; }
  }
}

function startLogsRefresh() {
  loadLogs();
  if (logsAutoRefresh && !logsTimer) logsTimer = setInterval(loadLogs, 3000);
}

function stopLogsRefresh() {
  if (logsTimer) { clearInterval(logsTimer); logsTimer = null; }
}

// ─── Presets ──────────────────────────
async function loadPresets() {
  try {
    const resp = await apiFetch('/api/presets');
    const presets = await resp.json();
    const sel = document.getElementById('presetSelect');
    const current = sel.value;
    sel.innerHTML = '<option value="">— 选择预设 —</option>';
    presets.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.name;
      opt.textContent = p.name + ' (' + p.voice + ')';
      sel.appendChild(opt);
    });
    if (current) sel.value = current;
  } catch(e) { console.error(e); }
}

async function loadPreset() {
  const name = document.getElementById('presetSelect').value;
  if (!name) return;
  try {
    const resp = await apiFetch('/api/presets');
    const presets = await resp.json();
    const p = presets.find(x => x.name === name);
    if (!p) return;
    // Apply voice
    const voiceBtns = document.querySelectorAll('.voice-btn');
    voiceBtns.forEach(b => {
      b.classList.remove('active');
      if (b.textContent.replace('🎤 ','') === p.voice) {
        b.classList.add('active');
        selectedVoice = p.voice;
      }
    });
    if (p.instruct) document.getElementById('instructInput').value = p.instruct;
    if (p.speed) document.getElementById('speedSelect').value = p.speed;
    if (p.fmt) document.getElementById('formatSelect').value = p.fmt;
  } catch(e) { alert('加载预设失败: ' + e.message); }
}

async function saveCurrentPreset() {
  const name = prompt('输入预设名称:');
  if (!name || !name.trim()) return;
  try {
    await apiFetch('/api/presets', {
      method: 'POST',
      body: JSON.stringify({
        name: name.trim(),
        voice: selectedVoice,
        instruct: document.getElementById('instructInput').value.trim(),
        speed: parseFloat(document.getElementById('speedSelect').value),
        fmt: document.getElementById('formatSelect').value,
      }),
    });
    await loadPresets();
    document.getElementById('presetSelect').value = name.trim();
  } catch(e) { alert('保存失败: ' + e.message); }
}

async function deleteCurrentPreset() {
  const name = document.getElementById('presetSelect').value;
  if (!name) { alert('请先选择预设'); return; }
  if (!confirm(`确定删除预设 "${name}"？`)) return;
  try {
    await apiFetch(`/api/presets/${encodeURIComponent(name)}`, {method:'DELETE'});
    document.getElementById('presetSelect').value = '';
    await loadPresets();
  } catch(e) { alert('删除失败: ' + e.message); }
}

// ─── Navigation ───────────────────────
let _currentPanel = 'synthesize';
const _panelLoaded = new Set(['synthesize']);  // synthesize loads on showApp
function switchNav(name) {
  // Deactivate old panel + nav item
  const oldPanel = document.getElementById('panel' + _currentPanel.charAt(0).toUpperCase() + _currentPanel.slice(1));
  if (oldPanel) oldPanel.classList.remove('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  // Stop refreshers for old panel
  if (_currentPanel === 'status') stopStatusRefresh();
  if (_currentPanel === 'logs') stopLogsRefresh();

  // Activate new panel + nav item
  const newPanel = document.getElementById('panel' + name.charAt(0).toUpperCase() + name.slice(1));
  if (!newPanel) { console.warn('Panel not found:', name); return; }
  newPanel.classList.add('active');
  const navItem = document.querySelector(`.nav-item[data-panel="${name}"]`);
  if (navItem) navItem.classList.add('active');
  _currentPanel = name;

  // Load data on first visit only
  if (!_panelLoaded.has(name)) {
    _panelLoaded.add(name);
    if (name === 'history') loadHistory();
    if (name === 'update') checkUpdate();
    if (name === 'clone') loadVoiceList();
    if (name === 'compare') loadCompareVoices();
  }
  // Always start refreshers for real-time panels
  if (name === 'status') startStatusRefresh();
  if (name === 'logs') startLogsRefresh();
  // History refresh on revisit (data may have changed)
  if (name === 'history' && _panelLoaded.has(name)) loadHistory();
}

// Backward compat: toggleSection redirects to switchNav
function toggleSection(name) { switchNav(name); }

// ─── Boot ─────────────────────────────
init();
</script>
</body>
</html>
"""
