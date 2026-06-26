"""HTML templates for CrispASR TTS Web UI."""

HTML_PAGE = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CrispASR TTS</title>
<style>
:root{--bg:#0f1117;--card:#1a1d27;--border:#2a2d3a;--text:#e4e4e7;--muted:#71717a;--accent:#6366f1;--accent2:#818cf8;--success:#22c55e;--error:#ef4444;--warn:#f59e0b}
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
.container{max-width:920px;margin:0 auto;padding:30px 20px}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px}
.header h1{font-size:24px}
.header-right{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.btn-sm{padding:6px 14px;font-size:13px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);cursor:pointer;transition:.2s;white-space:nowrap}
.btn-sm:hover{border-color:var(--accent)}
.btn-sm.active{background:var(--accent);color:#fff;border-color:var(--accent)}

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
.history-section{display:none}
.history-section.show{display:block}
.history-item{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;background:var(--card)}
.history-item:hover{border-color:var(--accent)}
.history-text{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-right:12px;font-size:13px}
.history-meta{font-size:11px;color:var(--muted);white-space:nowrap}
.history-actions{display:flex;gap:6px}
.history-actions button{padding:4px 10px;font-size:12px;border-radius:4px}

/* Clone */
.clone-section{display:none}
.clone-section.show{display:block}
.upload-zone{border:2px dashed var(--border);border-radius:8px;padding:24px;text-align:center;cursor:pointer;transition:.2s}
.upload-zone:hover{border-color:var(--accent)}
.upload-zone.has-file{border-color:var(--success);border-style:solid}

/* Model section */
.model-section{display:none}
.model-section.show{display:block}
.model-card{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;background:var(--bg);cursor:pointer;transition:.2s}
.model-card:hover{border-color:var(--accent)}
.model-card.active{border-color:var(--success);background:rgba(34,197,94,.05)}
.model-card.active::before{content:'✓ ';color:var(--success);font-weight:700}
.model-name{font-weight:600;font-size:14px}
.model-desc{font-size:11px;color:var(--muted);margin-top:2px}

/* Update section */
.update-section{display:none}
.update-section.show{display:block}
.update-log{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:12px;font-family:monospace;font-size:12px;max-height:200px;overflow-y:auto;white-space:pre-wrap;color:var(--muted);margin-top:8px}

.spinner{display:inline-block;width:14px;height:14px;border:2px solid var(--muted);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;vertical-align:middle;margin-right:6px}
@keyframes spin{to{transform:rotate(360deg)}}

/* Markup hint banner */
.markup-hint{background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.2);border-radius:8px;padding:10px 14px;font-size:12px;color:var(--accent2);margin-top:8px;display:none}
.markup-hint.show{display:block}
.markup-hint code{background:var(--bg);padding:2px 6px;border-radius:4px;font-size:11px}

@media(max-width:600px){
  .container{padding:16px 12px}
  .header h1{font-size:20px}
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
  <div class="container">
    <div class="header">
      <h1>🎙️ CrispASR TTS</h1>
      <div class="header-right">
        <button class="btn-sm" onclick="toggleSection('model')">模型</button>
        <button class="btn-sm" onclick="toggleSection('history')">历史</button>
        <button class="btn-sm" onclick="toggleSection('clone')">语音克隆</button>
        <button class="btn-sm" onclick="toggleSection('update')">更新</button>
        <button class="btn-sm" onclick="doLogout()">退出</button>
      </div>
    </div>

    <!-- Model Selection -->
    <div class="model-section" id="modelSection">
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <label style="margin:0">模型选择</label>
          <span class="hint" id="currentModelName">当前: --</span>
        </div>
        <div id="modelList"></div>
        <div class="hint" style="margin-top:8px">切换模型会重启CrispASR服务，约10-20秒不可用</div>
      </div>
    </div>

    <!-- Voice Clone -->
    <div class="clone-section" id="cloneSection">
      <div class="card">
        <label>语音克隆 · 上传参考音频</label>
        <div class="upload-zone" id="uploadZone" onclick="document.getElementById('refAudio').click()">
          <div id="uploadText">📎 点击或拖拽上传参考音频（WAV/MP3，10-15秒）</div>
        </div>
        <input type="file" id="refAudio" accept="audio/*" style="display:none" onchange="uploadRefAudio()">
        <div class="hint">上传干净的人声录音，用于克隆音色。需配合支持克隆的模型使用。</div>
      </div>
    </div>

    <!-- Update -->
    <div class="update-section" id="updateSection">
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <label style="margin:0">CrispASR 更新</label>
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

    <!-- History -->
    <div class="history-section" id="historySection">
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <label style="margin:0">生成历史</label>
          <button class="btn-sm" onclick="clearHistory()">清空</button>
        </div>
        <div id="historyList"></div>
      </div>
    </div>
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
  headers['Content-Type'] = headers['Content-Type'] || 'application/json';
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
  loadHistory();
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
      div.innerHTML = `<div><div class="model-name">${m.key}</div><div class="model-desc">${m.description}</div></div>`;
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
function escAttr(s) { return s.replace(/"/g,'&quot;').replace(/</g,'&lt;'); }

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
  pollTimer = setInterval(async () => {
    try {
      const resp = await apiFetch(`/api/task/${taskId}`);
      const data = await resp.json();
      const fill = document.getElementById('progressFill');
      const ptxt = document.getElementById('progressText');

      fill.style.width = (data.progress || 0) + '%';

      if (data.status === 'queued') {
        ptxt.innerHTML = `<span class="spinner"></span>队列中第 ${data.queue_pos || '?'} 位...`;
      } else if (data.status === 'generating') {
        ptxt.innerHTML = `<span class="spinner"></span>正在生成 ${data.current}/${data.total} 段... (${data.progress}%)`;
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
}

// ─── History ──────────────────────────
async function loadHistory() {
  try {
    const resp = await apiFetch('/api/history');
    const items = await resp.json();
    const list = document.getElementById('historyList');
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
      const textDiv = document.createElement('div');
      textDiv.className = 'history-text';
      textDiv.title = item.text;
      textDiv.textContent = statusIcon + ' ' + item.text.slice(0,60);
      const metaDiv = document.createElement('div');
      metaDiv.className = 'history-meta';
      metaDiv.textContent = item.voice + ' · ' + dur + ' · ' + time;
      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'history-actions';
      if (item.audio_file) {
        const playBtn = document.createElement('button');
        playBtn.className = 'btn-sm';
        playBtn.textContent = '播放';
        playBtn.onclick = () => playHistory(item.audio_file);
        actionsDiv.appendChild(playBtn);
      }
      div.appendChild(textDiv);
      div.appendChild(metaDiv);
      div.appendChild(actionsDiv);
      list.appendChild(div);
    });
  } catch(e) { console.error(e); }
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
  loadHistory();
}

// ─── Section Toggle ───────────────────
function toggleSection(name) {
  const el = document.getElementById(name+'Section');
  el.classList.toggle('show');
  if (name === 'history' && el.classList.contains('show')) loadHistory();
  if (name === 'update' && el.classList.contains('show')) checkUpdate();
}

// ─── Boot ─────────────────────────────
init();
</script>
</body>
</html>
"""
