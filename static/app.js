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
  if (opts.body && !(opts.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }
  const resp = await fetch(url, { ...opts, headers });
  if (resp.status === 401) { doLogout(); throw new Error('登录已过期'); }
  return resp;
}

// ─── Shared Helpers ───────────────────

/** Toast notification system */
function toast(msg, type = 'info', timeout = 4000) {
  const container = document.getElementById('toastContainer');
  if (!container) { alert(msg); return; }
  const el = document.createElement('div');
  const colors = {
    info:    { bg: '#3b82f6', icon: 'ℹ️' },
    success: { bg: '#22c55e', icon: '✅' },
    warn:    { bg: '#f59e0b', icon: '⚠️' },
    error:   { bg: '#ef4444', icon: '❌' },
  };
  const c = colors[type] || colors.info;
  el.style.cssText = `background:${c.bg};color:#fff;padding:10px 16px;border-radius:8px;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.3);display:flex;align-items:center;gap:8px;pointer-events:auto;max-width:380px;word-break:break-word;animation:toastIn 0.2s ease`;
  el.innerHTML = `<span>${c.icon}</span><span>${escHtml(msg)}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity 0.3s, transform 0.3s';
    el.style.opacity = '0';
    el.style.transform = 'translateX(20px)';
    setTimeout(() => el.remove(), 300);
  }, timeout);
}

/** Append token to a URL for auth'd media access */
function authUrl(url) {
  const sep = url.includes('?') ? '&' : '?';
  return url + sep + 'token=' + encodeURIComponent(getToken());
}

/** Play audio URL and show result card */
function playAudioUrl(url, showCard = true) {
  const player = document.getElementById('audioPlayer');
  player.src = url;
  player.play().catch(() => {});
  if (showCard) document.getElementById('resultCard').classList.add('show');
}

/** Trigger a file download */
function triggerDownload(url, filename) {
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
}

/** Set active voice in the grid by name */
function selectVoiceByName(name) {
  selectedVoice = name;
  document.querySelectorAll('.voice-btn').forEach(b => {
    b.classList.toggle('active', b.textContent.replace('🎤 ', '') === name);
  });
}

/** Read current synthesis params from the UI */
function getSynthParams() {
  return {
    voice: selectedVoice,
    instruct: document.getElementById('instructInput').value.trim(),
    speed: parseFloat(document.getElementById('speedSelect').value),
    fmt: document.getElementById('formatSelect').value,
  };
}

/** Apply synthesis params to the UI */
function setSynthParams({instruct, speed, fmt}) {
  if (instruct) document.getElementById('instructInput').value = instruct;
  if (speed) document.getElementById('speedSelect').value = speed;
  if (fmt) document.getElementById('formatSelect').value = fmt;
}

/** Reset the generate button to idle state */
function resetGenerateBtn() {
  const btn = document.getElementById('generateBtn');
  btn.disabled = false;
  btn.textContent = '生成语音';
}

/** Generic task poller — resolves when done/error/timeout */
async function pollTask(taskId, { onDone, onError, onProgress, maxAttempts = 300, interval = 2000 } = {}) {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, interval));
    try {
      const resp = await apiFetch(`/api/task/${encodeURIComponent(taskId)}`);
      const d = await resp.json();
      if (d.status === 'done') return onDone?.(d);
      if (d.status === 'error') return onError?.(d);
      onProgress?.(d);
    } catch (e) { /* network hiccup, retry */ }
  }
  return onError?.({ error: '超时' });
}

// ─── Login ────────────────────────────
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

function showChangePassword() {
  document.getElementById('cpOldPw').value = '';
  document.getElementById('cpNewPw').value = '';
  document.getElementById('cpConfirmPw').value = '';
  const err = document.getElementById('cpError');
  err.style.display = 'none';
  err.textContent = '';
  document.getElementById('changePasswordModal').classList.add('active');
}

function closeChangePassword() {
  document.getElementById('changePasswordModal').classList.remove('active');
}

async function submitChangePassword() {
  const oldPw = document.getElementById('cpOldPw').value;
  const newPw = document.getElementById('cpNewPw').value;
  const confirmPw = document.getElementById('cpConfirmPw').value;
  const err = document.getElementById('cpError');

  if (!oldPw || !newPw || !confirmPw) {
    err.textContent = '请填写所有字段'; err.style.display = 'block'; return;
  }
  if (newPw !== confirmPw) {
    err.textContent = '两次新密码不一致'; err.style.display = 'block'; return;
  }
  if (newPw.length < 4) {
    err.textContent = '新密码至少4位'; err.style.display = 'block'; return;
  }

  const btn = document.getElementById('cpSubmitBtn');
  btn.disabled = true; btn.textContent = '修改中...';
  try {
    const resp = await apiFetch('/api/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPw, new_password: newPw })
    });
    const data = await resp.json();
    if (resp.ok) {
      closeChangePassword();
      alert('密码已修改，请重新登录');
      doLogout();
    } else {
      err.textContent = data.error || '修改失败'; err.style.display = 'block';
    }
  } catch (e) {
    err.textContent = '网络错误'; err.style.display = 'block';
  }
  btn.disabled = false; btn.textContent = '确认修改';
}

async function checkAuth() {
  if (!getToken()) return false;
  try { return (await apiFetch('/api/check')).ok; } catch { return false; }
}

function showApp() {
  document.getElementById('loginPage').style.display = 'none';
  document.getElementById('appPage').style.display = 'block';
  loadModelInfo();
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
    btn.className = 'voice-btn' + (v === selectedVoice ? ' active' : '');
    btn.textContent = v;
    btn.onclick = () => selectVoiceByName(v);
    grid.appendChild(btn);
  });
  
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
    const btn = document.getElementById('updateBtn');
    if (!data.installed) {
      el.textContent = `未安装 | 最新: ${data.latest || '未知'}`;
      btn.disabled = false;
      btn.textContent = `安装 CrispASR ${data.latest || ''}`;
      btn.className = 'btn-warn';
    } else if (data.latest && data.latest !== data.current) {
      el.textContent = `当前: ${data.current} | 最新: ${data.latest}`;
      btn.disabled = false;
      btn.textContent = `更新到 ${data.latest}`;
      btn.className = 'btn-warn';
    } else {
      el.textContent = `当前: ${data.current} | 已是最新`;
      btn.disabled = true;
      btn.textContent = '已是最新';
      btn.className = 'btn-secondary';
    }
  } catch(e) { el.textContent = '检查失败'; }
}

async function doUpdate() {
  const btn = document.getElementById('updateBtn');
  const statusEl = document.getElementById('updateStatus');
  const logEl = document.getElementById('updateLog');
  const isInstall = btn.textContent.includes('安装');
  btn.disabled = true;
  statusEl.innerHTML = `<span class="spinner"></span>${isInstall ? '下载安装中' : '更新中'}...`;
  logEl.style.display = 'block';
  logEl.textContent = isInstall ? '正在下载 CrispASR...' : '开始更新...';
  
  try {
    const resp = await apiFetch('/api/crispasr/update', { method: 'POST' });
    const data = await resp.json();
    logEl.textContent = data.log || data.message;
    if (data.success) {
      statusEl.textContent = '✅ ' + data.message;
      loadModelInfo();
      checkUpdate();
    } else {
      statusEl.textContent = '❌ ' + data.message;
    }
  } catch(e) {
    statusEl.textContent = '❌ 请求失败';
    logEl.textContent = e.message;
  }
  btn.disabled = false;
}

// ─── Init ─────────────────────────────
async function init() {
  if (await checkAuth()) showApp();
  document.getElementById('textInput').addEventListener('input', function(){
    document.getElementById('charCount').textContent = this.value.length + '字';
    chunksConfig = [];
    document.getElementById('chunkPreview').classList.remove('show');
  });
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
  checkResumable();
  loadPresets();
  restoreBatch();
}

// ─── Markup Hint ──────────────────────
function toggleMarkupHint() {
  document.getElementById('markupHint').classList.toggle('show');
}

// ─── Chunk Preview ────────────────────
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
  document.querySelector(`.chunk-item[data-index="${i}"]`).classList.toggle('expanded');
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
    playAudioUrl(URL.createObjectURL(blob));
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

  const params = getSynthParams();
  currentFmt = params.fmt;

  const body = {
    text,
    voice: params.voice,
    instruct: params.instruct,
    speed: params.speed,
    fmt: params.fmt,
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
    
    if (data.queue_pos > 0) {
      document.getElementById('queueInfo').style.display = 'block';
      document.getElementById('queueInfo').textContent = `队列中第 ${data.queue_pos} 位`;
    } else {
      document.getElementById('queueInfo').style.display = 'none';
    }
    
    pollProgress();
  } catch(e) {
    document.getElementById('progressText').textContent = '❌ ' + e.message;
    resetGenerateBtn();
  }
}

function pollProgress() {
  if (pollTimer) clearInterval(pollTimer);
  let attempts = 0;
  pollTimer = setInterval(async () => {
    attempts++;
    if (attempts > 300) {
      clearInterval(pollTimer);
      document.getElementById('progressText').textContent = '⏰ 生成超时，请重试';
      resetGenerateBtn();
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
        resetGenerateBtn();
        document.getElementById('queueInfo').style.display = 'none';
        loadHistory();
      } else if (data.status === 'error') {
        clearInterval(pollTimer);
        ptxt.textContent = '❌ ' + (data.error || '生成失败');
        resetGenerateBtn();
        document.getElementById('queueInfo').style.display = 'none';
      }
    } catch(e) { console.error(e); }
  }, 2000);
}

function showResult(audioUrl, duration) {
  currentAudioUrl = authUrl(audioUrl);
  playAudioUrl(currentAudioUrl);
  const dur = duration ? duration.toFixed(1) + '秒' : '';
  document.getElementById('resultMeta').textContent = dur ? `时长: ${dur}` : '';
}

function downloadAudio() {
  if (!currentAudioUrl) return;
  triggerDownload(currentAudioUrl, `tts_${selectedVoice}_${Date.now()}.${currentFmt}`);
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
    const resp = await apiFetch('/api/voices', { method: 'POST', body: form });
    const data = await resp.json();
    if (data.name) {
      uploadedVoice = data.name;
      const grid = document.getElementById('voiceGrid');
      const btn = document.createElement('div');
      btn.className = 'voice-btn active';
      btn.textContent = '🎤 ' + data.name;
      btn.onclick = () => selectVoiceByName(data.name);
      grid.prepend(btn);
      selectVoiceByName(data.name);
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
  const a = new Audio(authUrl('/uploads/' + encodeURIComponent(filename)));
  a.play().catch(e => alert('播放失败: ' + e.message));
}

function selectVoice(name) {
  selectVoiceByName(name);
}

async function deleteVoice(name) {
  if (!confirm(`确定删除参考音频 "${name}"？`)) return;
  try {
    await apiFetch(`/api/voices/${encodeURIComponent(name)}`, {method:'DELETE'});
    document.querySelectorAll('.voice-btn').forEach(b => {
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
        const resp = await apiFetch('/api/voices', {method:'POST', body:form});
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
    const params = getSynthParams();
    const resp = await apiFetch('/api/compare', {
      method: 'POST',
      body: JSON.stringify({
        voice_a: voiceA, voice_b: voiceB, text,
        speed: params.speed, fmt: params.fmt, instruct: params.instruct,
      }),
    });
    const data = await resp.json();
    if (data.error) { alert(data.error); return; }
    await pollCompareTasks(data.task_a, data.task_b);
  } catch(e) {
    alert('对比请求失败: ' + e.message);
    document.getElementById('compareBtn').disabled = false;
  }
}

async function pollCompareTasks(taskIdA, taskIdB) {
  const statusEl = document.getElementById('compareStatus');
  let cnt = 0;

  const pollOne = async (id, audioElId, label) => {
    await pollTask(id, {
      onDone: d => {
        cnt++;
        if (d.audio_url) document.getElementById(audioElId).src = authUrl(d.audio_url);
      },
      onError: d => {
        cnt++;
        statusEl.textContent = `${label} 合成失败: ${d.error || '未知错误'}`;
      },
      onProgress: () => { statusEl.textContent = `合成中... ${cnt}/2 完成`; },
      maxAttempts: 150,
    });
  };

  await Promise.all([pollOne(taskIdA, 'compareAudioA', 'A'), pollOne(taskIdB, 'compareAudioB', 'B')]);
  statusEl.textContent = cnt >= 2 ? '对比完成！点击播放试听' : '⏰ 对比超时';
  document.getElementById('compareBtn').disabled = false;
}

// ─── Batch Synthesize ─────────────────
let batchTaskIds = [];
let batchPollTimer = null;
let batchPollAttempts = 0;
let currentBatchId = null;

document.getElementById('batchText').addEventListener('input', function() {
  const lines = this.value.split('\n').filter(l => l.trim());
  document.getElementById('batchCount').textContent = lines.length ? `${lines.length} 条` : '';
});

function saveBatchToStorage(batchId, taskIds, texts) {
  try {
    localStorage.setItem('crispasr_batch', JSON.stringify({ batch_id: batchId, task_ids: taskIds, texts: texts, ts: Date.now() }));
  } catch(e) {}
}

function clearBatchFromStorage() {
  try { localStorage.removeItem('crispasr_batch'); } catch(e) {}
}

function getBatchFromStorage() {
  try {
    const raw = localStorage.getItem('crispasr_batch');
    if (!raw) return null;
    return JSON.parse(raw);
  } catch(e) { return null; }
}

// Called on page load — if there's an unfinished batch in localStorage, restore the UI.
async function restoreBatch() {
  const saved = getBatchFromStorage();
  if (!saved || !saved.batch_id || !saved.task_ids) return;

  try {
    const r = await apiFetch(`/api/batch/${encodeURIComponent(saved.batch_id)}`);
    if (!r.ok) { clearBatchFromStorage(); return; }
    const data = await r.json();
    if (!data.items || data.items.length === 0) { clearBatchFromStorage(); return; }

    currentBatchId = saved.batch_id;
    batchTaskIds = saved.task_ids;
    const texts = saved.texts || data.items.map(i => i.text || '');

    document.getElementById('batchBtn').disabled = true;
    document.getElementById('batchProgress').style.display = '';
    document.getElementById('batchMergeArea').style.display = 'none';
    document.getElementById('batchMergePlayer').style.display = 'none';
    document.getElementById('batchMergeBtn').textContent = '合并下载';
    document.getElementById('batchMergeBtn').disabled = false;

    const el = document.getElementById('batchItems');
    el.innerHTML = batchTaskIds.map((id, i) =>
      `<div class="batch-item" data-batch-id="${escAttr(id)}">
        <span class="batch-item-text">${escHtml(texts[i] || '')}</span>
        <span class="batch-item-status" data-batch-id="${escAttr(id)}">⏳</span>
      </div>`
    ).join('');

    if (data.all_done) {
      document.getElementById('batchFill').style.width = '100%';
      document.getElementById('batchCount').textContent = `全部完成 ${data.done}/${data.total}`;
      document.getElementById('batchBtn').disabled = false;
      document.getElementById('batchMergeArea').style.display = '';
      batchTaskIds.forEach(id => {
        const statusEl = document.querySelector(`.batch-item-status[data-batch-id="${CSS.escape(id)}"]`);
        if (statusEl) { statusEl.textContent = '✅'; statusEl.dataset.done = '1'; }
      });
    } else {
      batchPollAttempts = 0;
      for (const item of data.items) {
        const statusEl = document.querySelector(`.batch-item-status[data-batch-id="${CSS.escape(item.id)}"]`);
        if (!statusEl) continue;
        if (item.status === 'done') { statusEl.textContent = '✅'; statusEl.dataset.done = '1'; }
        else if (item.status === 'error') { statusEl.textContent = '❌'; statusEl.dataset.done = '1'; }
        else if (item.status === 'generating') { statusEl.textContent = '🔄'; }
        else { statusEl.textContent = '⏳'; }
      }
      pollBatchTasks();
    }
  } catch(e) {
    clearBatchFromStorage();
  }
}

async function startBatch() {
  const text = document.getElementById('batchText').value;
  const lines = text.split('\n').map(l => l.trim()).filter(l => l);
  if (!lines.length) { toast('请输入至少一段文本', 'warn'); return; }
  if (lines.length > 20) { toast('最多20条', 'warn'); return; }

  document.getElementById('batchBtn').disabled = true;
  document.getElementById('batchProgress').style.display = '';
  document.getElementById('batchMergeArea').style.display = 'none';
  document.getElementById('batchMergePlayer').style.display = 'none';
  document.getElementById('batchMergeBtn').textContent = '合并下载';
  document.getElementById('batchMergeBtn').disabled = false;

  try {
    const params = getSynthParams();
    const resp = await apiFetch('/api/batch', {
      method: 'POST',
      body: JSON.stringify({
        texts: lines,
        voice: params.voice,
        speed: params.speed,
        fmt: params.fmt,
        instruct: params.instruct,
      }),
    });
    const data = await resp.json();
    if (data.error) { toast(data.error, 'error'); return; }
    batchTaskIds = data.task_ids;
    currentBatchId = data.batch_id || null;
    batchPollAttempts = 0;
    if (currentBatchId) {
      saveBatchToStorage(currentBatchId, batchTaskIds, lines);
    }
    // Clear textarea after successful submit
    document.getElementById('batchText').value = '';
    document.getElementById('batchCount').textContent = '';
    const el = document.getElementById('batchItems');
    el.innerHTML = batchTaskIds.map((id, i) =>
      `<div class="batch-item" data-batch-id="${escAttr(id)}">
        <span class="batch-item-text">${escHtml(lines[i])}</span>
        <span class="batch-item-status" data-batch-id="${escAttr(id)}">⏳</span>
      </div>`
    ).join('');
    pollBatchTasks();
  } catch(e) {
    toast('批量提交失败: ' + e.message, 'error');
    document.getElementById('batchBtn').disabled = false;
  }
}

async function pollBatchTasks() {
  let done = 0;
  const total = batchTaskIds.length;

  batchPollAttempts++;
  if (batchPollAttempts > 300) {
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
  document.getElementById('batchCount').textContent = `生成中 ${done}/${total}`;

  if (done < total) {
    batchPollTimer = setTimeout(pollBatchTasks, 2000);
  } else {
    document.getElementById('batchCount').textContent = `全部完成 ${done}/${total}`;
    document.getElementById('batchBtn').disabled = false;
    // Show merge area when all tasks are done
    document.getElementById('batchMergeArea').style.display = '';
    // All done — clear storage (batch complete, no need to restore)
    clearBatchFromStorage();
    // Notify user
    toast(`批量合成完成！${done}/${total} 条`, 'success');
  }
}

// Merge all batch audio files into one and download
async function mergeBatchAudio() {
  const btn = document.getElementById('batchMergeBtn');
  const fmt = document.getElementById('batchMergeFmt').value;
  btn.disabled = true;
  btn.textContent = '合并中...';

  try {
    const resp = await apiFetch('/api/batch/merge', {
      method: 'POST',
      body: JSON.stringify({ task_ids: batchTaskIds, fmt: fmt }),
    });
    const data = await resp.json();
    if (data.error) { toast(data.error, 'error'); return; }

    // Show merged audio player
    const player = document.getElementById('batchMergePlayer');
    player.src = authUrl(data.audio_url);
    player.style.display = '';

    // Trigger download
    triggerDownload(authUrl(data.audio_url), `batch_merged_${Date.now()}.${fmt}`);

    btn.textContent = '✅ 已合并下载';
    btn.disabled = false;
    toast(`已合并 ${data.count} 条音频 (${data.duration.toFixed(1)}s)`, 'success');
  } catch(e) {
    toast('合并失败: ' + e.message, 'error');
    btn.textContent = '合并下载';
    btn.disabled = false;
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
    updateHistoryActionBar();
  } catch(e) { console.error(e); }
}

function onHistoryCheck() {
  const checks = document.querySelectorAll('.history-check');
  checks.forEach(c => {
    if (c.checked) { historyChecked.add(c.dataset.id); }
    else { historyChecked.delete(c.dataset.id); }
  });
  updateHistoryActionBar();
  updateCheckAllState();
}

function updateHistoryActionBar() {
  const n = historyChecked.size;
  document.getElementById('batchDeleteBtn').disabled = n === 0;
  document.getElementById('mergeSelectedBtn').disabled = n < 2;
  // Show count badge
  const badge = document.getElementById('historySelectedCount');
  if (badge) badge.textContent = n > 0 ? `已选 ${n} 条` : '';
}

function updateCheckAllState() {
  const checks = document.querySelectorAll('.history-check');
  const allChecked = checks.length > 0 && [...checks].every(c => c.checked);
  document.getElementById('historyCheckAll').checked = allChecked;
}

function toggleCheckAll(checked) {
  const checks = document.querySelectorAll('.history-check');
  checks.forEach(c => {
    c.checked = checked;
    if (checked) historyChecked.add(c.dataset.id);
    else historyChecked.delete(c.dataset.id);
  });
  updateHistoryActionBar();
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

// Merge selected history items into one audio file.
// Order: by created_at ascending (oldest first) — the natural audio sequence.
async function mergeSelectedHistory() {
  const ids = [...historyChecked];
  if (ids.length < 2) { toast('请至少选择 2 条记录', 'warn'); return; }

  // Fetch full item info for all selected IDs to sort by created_at
  const items = [];
  for (const id of ids) {
    try {
      const r = await apiFetch(`/api/history/${encodeURIComponent(id)}`);
      if (r.ok) {
        const item = await r.json();
        if (item.audio_file && item.status === 'done') {
          items.push(item);
        }
      }
    } catch(e) {}
  }

  if (items.length < 2) {
    toast('选中的记录中只有 ' + items.length + ' 条有可用音频，无法合并', 'warn');
    return;
  }

  // Sort by created_at ascending
  items.sort((a, b) => a.created_at - b.created_at);
  const sortedIds = items.map(i => i.id);

  // Show a merge dialog for format selection
  const fmt = confirm('合并 ' + items.length + ' 条音频（按创建时间排序）\n\n确定 = MP3 (压缩，推荐)\n取消 = WAV (无损)') ? 'mp3' : 'wav';

  toast('正在合并 ' + items.length + ' 条音频...', 'info');

  try {
    const resp = await apiFetch('/api/batch/merge', {
      method: 'POST',
      body: JSON.stringify({ task_ids: sortedIds, fmt: fmt }),
    });
    const data = await resp.json();
    if (data.error) { toast(data.error, 'error'); return; }

    const filename = `merged_${items.length}items_${Date.now()}.${fmt}`;
    triggerDownload(authUrl(data.audio_url), filename);
    toast(`✅ 已合并 ${items.length} 条音频 (${data.duration.toFixed(1)}s)`, 'success');
    // Refresh history to show the merged entry (if backend saved it)
    loadHistory();
  } catch(e) {
    toast('合并失败: ' + e.message, 'error');
  }
}

async function regenerateFromHistory(id) {
  try {
    const resp = await apiFetch(`/api/history/${encodeURIComponent(id)}`);
    if (!resp.ok) { alert('记录不存在'); return; }
    const item = await resp.json();
    switchNav('synthesize');
    document.getElementById('textInput').value = item.text;
    document.getElementById('charCount').textContent = item.text.length + '字';
    selectVoiceByName(item.voice);
    setSynthParams({instruct: item.instruct, speed: item.speed});
  } catch(e) { alert('加载失败: ' + e.message); }
}

function downloadHistoryAudio(audioFile, id) {
  triggerDownload(authUrl(`/api/audio/${audioFile}`), `tts_${id}.wav`);
}

async function playHistory(audioFile) {
  currentAudioUrl = authUrl(`/api/audio/${audioFile}`);
  playAudioUrl(currentAudioUrl);
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

    const el = document.getElementById('statusCrispasr');
    el.textContent = s.crispasr.active ? '运行中' : '已停止';
    el.className = 'status-value ' + (s.crispasr.active ? 'status-on' : 'status-off');
    document.getElementById('statusCrispasrDetail').textContent = s.crispasr.pid ? `PID ${s.crispasr.pid}` : '';

    const qd = s.queue.depth;
    document.getElementById('statusQueue').textContent = qd;
    document.getElementById('statusQueueDetail').textContent = s.queue.active ? '处理中...' : '空闲';

    const cpuPct = s.cpu.percent;
    document.getElementById('statusCpu').textContent = cpuPct + '%';
    document.getElementById('statusCpuBar').style.width = cpuPct + '%';
    document.getElementById('statusCpuBar').style.background = cpuPct > 80 ? '#ef4444' : cpuPct > 50 ? '#f59e0b' : 'var(--accent)';

    const memPct = s.memory.percent;
    document.getElementById('statusMem').textContent = memPct + '%';
    document.getElementById('statusMemBar').style.width = memPct + '%';
    document.getElementById('statusMemBar').style.background = memPct > 85 ? '#ef4444' : '#f59e0b';
    document.getElementById('statusMemDetail').textContent = `${s.memory.used_mb} / ${s.memory.total_mb} MB`;

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
let _presetsCache = [];

async function loadPresets() {
  try {
    const resp = await apiFetch('/api/presets');
    _presetsCache = await resp.json();
    const sel = document.getElementById('presetSelect');
    const current = sel.value;
    sel.innerHTML = '<option value="">— 选择预设 —</option>';
    _presetsCache.forEach(p => {
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
  const p = _presetsCache.find(x => x.name === name);
  if (!p) return;
  selectVoiceByName(p.voice);
  setSynthParams({instruct: p.instruct, speed: p.speed, fmt: p.fmt});
}

async function saveCurrentPreset() {
  const name = prompt('输入预设名称:');
  if (!name || !name.trim()) return;
  try {
    const params = getSynthParams();
    await apiFetch('/api/presets', {
      method: 'POST',
      body: JSON.stringify({ name: name.trim(), ...params }),
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
const _panelLoaded = new Set(['synthesize']);
function switchNav(name) {
  const oldPanel = document.getElementById('panel' + _currentPanel.charAt(0).toUpperCase() + _currentPanel.slice(1));
  if (oldPanel) oldPanel.classList.remove('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  if (_currentPanel === 'status') stopStatusRefresh();
  if (_currentPanel === 'logs') stopLogsRefresh();

  const newPanel = document.getElementById('panel' + name.charAt(0).toUpperCase() + name.slice(1));
  if (!newPanel) { console.warn('Panel not found:', name); return; }
  newPanel.classList.add('active');
  const navItem = document.querySelector(`.nav-item[data-panel="${name}"]`);
  if (navItem) navItem.classList.add('active');
  _currentPanel = name;

  if (!_panelLoaded.has(name)) {
    _panelLoaded.add(name);
    if (name === 'history') loadHistory();
    if (name === 'update') checkUpdate();
    if (name === 'clone') loadVoiceList();
    if (name === 'compare') loadCompareVoices();
  }
  if (name === 'status') startStatusRefresh();
  if (name === 'logs') startLogsRefresh();
  if (name === 'history' && _panelLoaded.has(name)) loadHistory();
}

// ─── Boot ─────────────────────────────
init();
