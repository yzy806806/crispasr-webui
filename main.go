package main

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

// ─── Constants ──────────────────────────────────────────

const (
	appVersion    = "1.1.0"
	wavHeaderSize = 44
	splitThreshold = 800
	maxTruncateLen = 2000
	envFilePath   = "/etc/tts-webui.env"
	loginRateLimit = 10
	loginRateWindow = 5 * time.Minute
	maxBatchItems = 20
	minPasswordLen = 4
	httpClientTimeout = 120 * time.Second
	maxAudioSize = 100 << 20 // 100MB safety cap for single TTS response
)

// ─── Pre-compiled regexes ───────────────────────────────

var (
	reExecStart  = regexp.MustCompile(`ExecStart=.*`)
	reSemVer     = regexp.MustCompile(`(\d+\.\d+\.\d+)`)
	reSafeName   = regexp.MustCompile(`[^\w]`)
	reSafeNameHy = regexp.MustCompile(`[^\w-]`)
)

// ─── HTTP client with timeout ───────────────────────────

var httpClient = &http.Client{Timeout: httpClientTimeout}

// ─── Config ──────────────────────────────────────────────

type Config struct {
	DataDir     string
	CrispASRDir string
	JWTSecret   string
	JWTExpiry   int
	Port        int
	Password    string
	MaxBody     int64
	MaxUpload   int64
}

var cfg Config

func initConfig() {
	cfg = Config{
		DataDir:     envOr("CRISPASR_DATA_DIR", filepath.Join(".", "tts_data")),
		CrispASRDir: envOr("CRISPASR_DIR", "."),
		JWTSecret:   envOr("JWT_SECRET", ""),
		JWTExpiry:   604800,
		Port:        8888,
		Password:    envOr("TTS_PASSWORD", ""),
		MaxBody:     10 << 20,
		MaxUpload:   10 << 20,
	}
	if p := envOr("TTS_PORT", ""); p != "" {
		cfg.Port, _ = strconv.Atoi(p)
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ─── Model Registry ─────────────────────────────────────

type ModelInfo struct {
	Backend     string   `json:"backend"`
	ModelFlag   string   `json:"model_flag"`
	Voices      []string `json:"voices"`
	HasInstruct bool     `json:"has_instruct"`
	HasClone    bool     `json:"has_clone"`
	HasStream   bool     `json:"has_streaming"`
	Desc        string   `json:"description"`
	AutoDL      bool     `json:"auto_dl"`
}

var models = map[string]ModelInfo{
	"qwen3-tts-customvoice-1.7b-f16": {"qwen3-tts-customvoice", "qwen3-tts-1.7b-customvoice",
		[]string{"serena", "vivian", "sohee", "ono_anna", "aiden", "dylan", "eric", "ryan", "uncle_fu"},
		true, true, false, "1.7B CustomVoice — 9 speakers + style + clone", true},
	"qwen3-tts-customvoice-0.6b-q8": {"qwen3-tts-customvoice", "qwen3-tts-0.6b-customvoice",
		[]string{"serena", "vivian", "sohee", "ono_anna", "aiden", "dylan", "eric", "ryan", "uncle_fu"},
		true, true, false, "0.6B CustomVoice Q8 — lighter, same 9 speakers", true},
	"qwen3-tts-base-1.7b": {"qwen3-tts", "qwen3-tts-1.7b-base",
		[]string{}, false, true, true, "1.7B Base — streaming output, WAV clone", true},
	"qwen3-tts-voicedesign-1.7b": {"qwen3-tts-customvoice", "qwen3-tts-1.7b-voicedesign",
		[]string{}, true, false, false, "1.7B VoiceDesign — describe voice via instruct", true},
	"kokoro": {"kokoro", "kokoro",
		[]string{"af_bella", "af_nicole", "af_sarah", "af_sky", "am_adam", "am_michael"},
		false, false, false, "Kokoro 82M — lightweight multilingual", true},
	"cosyvoice3-tts": {"cosyvoice3-tts", "cosyvoice3-tts",
		[]string{"zero_shot", "fleurs-en", "fleurs-de", "fleurs-zh", "fleurs-ja", "fleurs-fr", "fleurs-es", "fleurs-ko"},
		false, true, false, "CosyVoice3 0.5B — 9 languages + clone", true},
	"chatterbox": {"chatterbox", "chatterbox",
		[]string{"default"}, false, true, false, "Chatterbox — 23 languages, emotion tags", true},
}

// ─── JSON helpers ────────────────────────────────────────

func sendJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}

func readJSON(r *http.Request, v any) error {
	dec := json.NewDecoder(io.LimitReader(r.Body, cfg.MaxBody))
	return dec.Decode(v)
}

// ─── Auth (HMAC-based JWT) ───────────────────────────────

var b64enc = base64.RawURLEncoding

func jwtSign(claims map[string]any) string {
	header := `{"alg":"HS256","typ":"JWT"}`
	payload, _ := json.Marshal(claims)
	h := hmac.New(sha256.New, []byte(cfg.JWTSecret))
	h.Write([]byte(b64enc.EncodeToString([]byte(header))))
	h.Write([]byte("."))
	h.Write([]byte(b64enc.EncodeToString(payload)))
	sig := h.Sum(nil)
	return b64enc.EncodeToString([]byte(header)) + "." + b64enc.EncodeToString(payload) + "." + b64enc.EncodeToString(sig)
}

func jwtVerify(token string) map[string]any {
	parts := strings.SplitN(token, ".", 3)
	if len(parts) != 3 {
		return nil
	}
	h := hmac.New(sha256.New, []byte(cfg.JWTSecret))
	h.Write([]byte(parts[0] + "." + parts[1]))
	if !hmac.Equal([]byte(parts[2]), []byte(b64enc.EncodeToString(h.Sum(nil)))) {
		return nil
	}
	dec, err := b64enc.DecodeString(parts[1])
	if err != nil {
		return nil
	}
	var claims map[string]any
	if json.Unmarshal(dec, &claims) != nil {
		return nil
	}
	if exp, ok := claims["exp"].(float64); ok && time.Now().Unix() > int64(exp) {
		return nil
	}
	return claims
}

func getClaims(r *http.Request) map[string]any {
	if hdr := r.Header.Get("Authorization"); strings.HasPrefix(hdr, "Bearer ") {
		return jwtVerify(hdr[7:])
	}
	return nil
}

func authed(r *http.Request) bool {
	if getClaims(r) != nil {
		return true
	}
	if t := r.URL.Query().Get("token"); t != "" {
		return jwtVerify(t) != nil
	}
	return false
}

func requireAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !authed(r) {
			sendJSON(w, 401, map[string]string{"error": "未登录"})
			return
		}
		next(w, r)
	}
}

// ─── Login rate limit ────────────────────────────────────

var (
	loginMu  sync.Mutex
	loginLog = map[string][]time.Time{}
)

func cleanupLoginLog() {
	loginMu.Lock()
	defer loginMu.Unlock()
	cutoff := time.Now().Add(-loginRateWindow)
	for ip, times := range loginLog {
		var recent []time.Time
		for _, t := range times {
			if t.After(cutoff) {
				recent = append(recent, t)
			}
		}
		if len(recent) == 0 {
			delete(loginLog, ip)
		} else {
			loginLog[ip] = recent
		}
	}
}

func handleChangePassword(w http.ResponseWriter, r *http.Request) {
	var body struct {
		OldPassword string `json:"old_password"`
		NewPassword string `json:"new_password"`
	}
	if readJSON(r, &body) != nil {
		sendJSON(w, 400, map[string]string{"error": "无效请求"})
		return
	}
	if !hmac.Equal([]byte(body.OldPassword), []byte(cfg.Password)) {
		sendJSON(w, 401, map[string]string{"error": "原密码错误"})
		return
	}
	if len(body.NewPassword) < minPasswordLen {
		sendJSON(w, 400, map[string]string{"error": "新密码至少4位"})
		return
	}
	cfg.Password = body.NewPassword
	envPath := envOr("TTS_ENV_FILE", envFilePath)
	if err := writeEnvPassword(envPath, body.NewPassword); err != nil {
		log.Printf("WARN: failed to persist password: %v", err)
	}
	sendJSON(w, 200, map[string]string{"message": "密码已修改"})
}

// writeEnvPassword atomically writes the password to the env file
func writeEnvPassword(path, password string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		// Create new file atomically
		tmp := path + ".tmp"
		if err := os.WriteFile(tmp, []byte("TTS_PASSWORD="+password+"\n"), 0644); err != nil {
			return err
		}
		return os.Rename(tmp, path)
	}
	lines := strings.Split(string(data), "\n")
	found := false
	for i, line := range lines {
		if strings.HasPrefix(line, "TTS_PASSWORD=") {
			lines[i] = "TTS_PASSWORD=" + password
			found = true
			break
		}
	}
	if !found {
		lines = append(lines, "TTS_PASSWORD="+password)
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, []byte(strings.Join(lines, "\n")), 0644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func handleLogin(w http.ResponseWriter, r *http.Request) {
	ip := strings.Split(r.RemoteAddr, ":")[0]
	loginMu.Lock()
	now := time.Now()
	cutoff := now.Add(-loginRateWindow)
	recent := []time.Time{}
	for _, t := range loginLog[ip] {
		if t.After(cutoff) {
			recent = append(recent, t)
		}
	}
	if len(recent) >= loginRateLimit {
		loginMu.Unlock()
		sendJSON(w, 429, map[string]string{"error": "尝试次数过多"})
		return
	}
	loginLog[ip] = append(recent, now)
	loginMu.Unlock()

	var body struct{ Password string `json:"password"` }
	if readJSON(r, &body) != nil {
		sendJSON(w, 400, map[string]string{"error": "无效请求"})
		return
	}
	if !hmac.Equal([]byte(body.Password), []byte(cfg.Password)) {
		sendJSON(w, 401, map[string]string{"error": "密码错误"})
		return
	}
	token := jwtSign(map[string]any{"sub": "user", "exp": time.Now().Unix() + int64(cfg.JWTExpiry)})
	sendJSON(w, 200, map[string]string{"token": token})
}

// ─── Database ────────────────────────────────────────────

var db *sql.DB

func initDB() error {
	os.MkdirAll(cfg.DataDir, 0755)
	path := filepath.Join(cfg.DataDir, "history.db")
	var err error
	db, err = sql.Open("sqlite3", path+"?_journal_mode=WAL&_busy_timeout=5000")
	if err != nil {
		return err
	}
	schema := `
	CREATE TABLE IF NOT EXISTS history (
		id TEXT PRIMARY KEY, text TEXT, voice TEXT, instruct TEXT,
		speed REAL DEFAULT 1.0, fmt TEXT DEFAULT 'wav',
		audio_file TEXT, duration REAL DEFAULT 0,
		status TEXT DEFAULT 'pending', chunks_config TEXT,
		created_at REAL
	);
	CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
	CREATE TABLE IF NOT EXISTS voices (name TEXT PRIMARY KEY, filename TEXT, created_at REAL);
	CREATE INDEX IF NOT EXISTS idx_history_status ON history(status);
	CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at);
	`
	_, err = db.Exec(schema)
	return err
}

func dbSetting(key string) string {
	var val string
	if err := db.QueryRow("SELECT value FROM settings WHERE key=?", key).Scan(&val); err != nil {
		return ""
	}
	return val
}

func dbSetSetting(key, val string) {
	if _, err := db.Exec("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", key, val); err != nil {
		log.Printf("WARN: dbSetSetting %s: %v", key, err)
	}
}

// ─── Task Queue ──────────────────────────────────────────

type Task struct {
	ID         string  `json:"id"`
	Status     string  `json:"status"`
	Progress   float64 `json:"progress"`
	Current    int     `json:"current"`
	Total      int     `json:"total"`
	AudioURL   string  `json:"audio_url"`
	Error      string  `json:"error"`
	Duration   float64 `json:"duration"`
	QueuePos   int     `json:"queue_pos"`
	Voice      string  `json:"voice,omitempty"`
	Instruct   string  `json:"instruct,omitempty"`
	Speed      float64 `json:"speed,omitempty"`
	Fmt        string  `json:"fmt,omitempty"`
	ChunksJSON string  `json:"-"`
	APBase     string  `json:"-"`
}

var (
	queueMu  sync.Mutex
	queue    []*Task
	active   *Task
	taskMap  = map[string]*Task{}
	taskCond = sync.NewCond(&queueMu)
)

func enqueue(t *Task) int {
	queueMu.Lock()
	defer queueMu.Unlock()
	t.QueuePos = len(queue)
	queue = append(queue, t)
	taskMap[t.ID] = t
	taskCond.Signal()
	return t.QueuePos
}

func queueLoop() {
	for {
		queueMu.Lock()
		for len(queue) == 0 {
			taskCond.Wait()
		}
		active = queue[0]
		queue = queue[1:]
		for i, t := range queue {
			t.QueuePos = i
		}
		queueMu.Unlock()

		processTask(active)

		queueMu.Lock()
		active = nil
		queueMu.Unlock()
	}
}

func processTask(t *Task) {
	var chunks []map[string]string
	if err := json.Unmarshal([]byte(t.ChunksJSON), &chunks); err != nil {
		t.Status = "error"
		t.Error = "无效的分句数据"
		dbExec("UPDATE history SET status='error' WHERE id=?", t.ID)
		return
	}

	t.Status = "generating"
	dbExec("UPDATE history SET status='generating' WHERE id=?", t.ID)

	var combined [][]byte
	for i, chunk := range chunks {
		t.Current = i + 1
		t.Progress = float64(t.Current) / float64(t.Total) * 100

		voice := chunk["voice"]
		if voice == "" {
			voice = t.Voice
		}
		instruct := chunk["instruct"]
		text := chunk["text"]

		payload, _ := json.Marshal(map[string]any{
			"model": "tts-1", "input": text, "voice": voice,
			"speed": t.Speed, "consent_attestation": "test", "spoken_disclaimer": false,
		})
		if instruct != "" {
			var p map[string]any
			json.Unmarshal(payload, &p)
			p["instruct"] = instruct
			payload, _ = json.Marshal(p)
		}

		req, _ := http.NewRequest("POST", t.APBase+"/v1/audio/speech", strings.NewReader(string(payload)))
		req.Header.Set("Content-Type", "application/json")
		resp, err := httpClient.Do(req)
		if err != nil {
			t.Status = "error"
			t.Error = err.Error()
			dbExec("UPDATE history SET status='error' WHERE id=?", t.ID)
			return
		}
		audio, _ := io.ReadAll(io.LimitReader(resp.Body, maxAudioSize))
		resp.Body.Close()
		combined = append(combined, audio)
	}

	finalWAV := concatWAVs(combined)
	audioFile := t.ID + ".wav"
	os.MkdirAll(filepath.Join(cfg.DataDir, "audio"), 0755)
	if err := os.WriteFile(filepath.Join(cfg.DataDir, "audio", audioFile), finalWAV, 0644); err != nil {
		t.Status = "error"
		t.Error = "写入音频文件失败"
		dbExec("UPDATE history SET status='error' WHERE id=?", t.ID)
		return
	}

	duration := wavDuration(finalWAV)
	t.Status = "done"
	t.AudioURL = "/api/audio/" + audioFile
	t.Duration = duration

	dbExec("UPDATE history SET status='done',audio_file=?,duration=? WHERE id=?", audioFile, duration, t.ID)
}

// dbExec logs errors instead of silently ignoring them
func dbExec(query string, args ...any) {
	if _, err := db.Exec(query, args...); err != nil {
		log.Printf("WARN: db %q: %v", query[:50], err)
	}
}

func concatWAVs(wavs [][]byte) []byte {
	if len(wavs) == 0 {
		return nil
	}
	if len(wavs) == 1 {
		return wavs[0]
	}
	result := make([]byte, len(wavs[0]))
	copy(result, wavs[0])
	for _, w := range wavs[1:] {
		if len(w) > wavHeaderSize {
			result = append(result, w[wavHeaderSize:]...)
		}
	}
	dataSize := uint32(len(result) - wavHeaderSize)
	result[4] = byte(dataSize + 36)
	result[5] = byte((dataSize + 36) >> 8)
	result[6] = byte((dataSize + 36) >> 16)
	result[7] = byte((dataSize + 36) >> 24)
	result[40] = byte(dataSize)
	result[41] = byte(dataSize >> 8)
	result[42] = byte(dataSize >> 16)
	result[43] = byte(dataSize >> 24)
	return result
}

func wavDuration(data []byte) float64 {
	if len(data) < wavHeaderSize {
		return 0
	}
	dataSize := uint32(data[40]) | uint32(data[41])<<8 | uint32(data[42])<<16 | uint32(data[43])<<24
	sampleRate := uint32(data[24]) | uint32(data[25])<<8 | uint32(data[26])<<16 | uint32(data[27])<<24
	bits := uint32(data[34]) | uint32(data[35])<<8
	channels := uint32(data[22]) | uint32(data[23])<<8
	if sampleRate == 0 || bits == 0 || channels == 0 {
		return 0
	}
	return float64(dataSize) / float64(sampleRate*channels*(bits/8))
}

// ─── Task creation helper (DRY) ─────────────────────────

func newTaskID() string {
	b := make([]byte, 6)
	rand.Read(b)
	return fmt.Sprintf("%x", b)
}

type taskParams struct {
	text     string
	voice    string
	instruct string
	speed    float64
	fmt      string
	chunks   []map[string]string
}

func applyDefaults(p *taskParams) {
	if p.voice == "" {
		p.voice = "serena"
	}
	if p.speed == 0 {
		p.speed = 1.0
	}
	if p.fmt == "" {
		p.fmt = "wav"
	}
}

func createTask(p taskParams) (*Task, int) {
	if p.chunks == nil {
		p.chunks = splitText(p.text)
	}
	chunksJSON, _ := json.Marshal(p.chunks)
	taskID := newTaskID()

	dbExec(`INSERT INTO history(id,text,voice,instruct,speed,fmt,status,chunks_config,created_at)
		VALUES(?,?,?,?,?,?,?,?,?)`, taskID, truncate(p.text, maxTruncateLen), p.voice, p.instruct,
		p.speed, p.fmt, "queued", string(chunksJSON), time.Now().Unix())

	task := &Task{
		ID: taskID, Status: "queued", Total: len(p.chunks), Voice: p.voice,
		Instruct: p.instruct, Speed: p.speed, Fmt: p.fmt,
		ChunksJSON: string(chunksJSON), APBase: "http://localhost:8080",
	}
	pos := enqueue(task)
	return task, pos
}

// ─── API Handlers ────────────────────────────────────────

func handleCheck(w http.ResponseWriter, r *http.Request) {
	sendJSON(w, 200, map[string]bool{"ok": true})
}

func handleModel(w http.ResponseWriter, r *http.Request) {
	key := dbSetting("current_model")
	if key == "" {
		key = "qwen3-tts-customvoice-1.7b-f16"
	}
	info, ok := models[key]
	if !ok {
		sendJSON(w, 200, map[string]string{"key": key})
		return
	}
	sendJSON(w, 200, map[string]any{"key": key, "backend": info.Backend, "model_flag": info.ModelFlag,
		"voices": info.Voices, "has_instruct": info.HasInstruct, "has_clone": info.HasClone,
		"has_streaming": info.HasStream, "description": info.Desc, "auto_dl": info.AutoDL})
}

func handleModels(w http.ResponseWriter, r *http.Request) {
	list := make([]map[string]any, 0, len(models))
	for k, v := range models {
		list = append(list, map[string]any{"key": k, "backend": v.Backend, "model_flag": v.ModelFlag,
			"voices": v.Voices, "has_instruct": v.HasInstruct, "has_clone": v.HasClone,
			"has_streaming": v.HasStream, "description": v.Desc, "auto_dl": v.AutoDL})
	}
	sendJSON(w, 200, list)
}

func handleSwitchModel(w http.ResponseWriter, r *http.Request) {
	var body struct{ Model string `json:"model"` }
	if readJSON(r, &body) != nil {
		sendJSON(w, 400, map[string]string{"error": "无效请求"})
		return
	}
	info, ok := models[body.Model]
	if !ok {
		sendJSON(w, 400, map[string]string{"error": "未知模型"})
		return
	}
	binary := findCrispASR()
	cmdParts := []string{binary, "--server", "--backend", info.Backend, "-m", info.ModelFlag,
		"--voice-dir", filepath.Join(cfg.CrispASRDir, "voices"), "--port", "8080", "--host", "127.0.0.1"}
	execStart := strings.Join(cmdParts, " ")

	svcPath := "/etc/systemd/system/crispasr.service"
	content, err := os.ReadFile(svcPath)
	if err != nil {
		sendJSON(w, 400, map[string]string{"error": "需要systemd管理CrispASR", "cmd": execStart})
		return
	}
	newContent := reExecStart.ReplaceAllString(string(content), "ExecStart="+execStart)
	// Atomic write: temp file then rename
	tmp := svcPath + ".tmp"
	if err := os.WriteFile(tmp, []byte(newContent), 0644); err != nil {
		sendJSON(w, 500, map[string]string{"error": "写入服务文件失败"})
		return
	}
	if err := os.Rename(tmp, svcPath); err != nil {
		sendJSON(w, 500, map[string]string{"error": "更新服务文件失败"})
		return
	}
	exec.Command("sudo", "systemctl", "daemon-reload").Run()
	exec.Command("sudo", "systemctl", "restart", "crispasr").Run()
	dbSetSetting("current_model", body.Model)
	sendJSON(w, 200, map[string]any{"success": true, "model": body.Model, "message": "已切换到 " + info.Desc})
}

func findCrispASR() string {
	for _, p := range []string{
		filepath.Join(cfg.CrispASRDir, "bin", "crispasr"),
		filepath.Join(cfg.CrispASRDir, "crispasr"),
	} {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	if p, _ := exec.LookPath("crispasr"); p != "" {
		return p
	}
	return "crispasr"
}

func handleGenerate(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Text      string  `json:"text"`
		Voice     string  `json:"voice"`
		Instruct  string  `json:"instruct"`
		Speed     float64 `json:"speed"`
		Fmt       string  `json:"fmt"`
		ChunksCfg any     `json:"chunks_config"`
	}
	if readJSON(r, &body) != nil {
		sendJSON(w, 400, map[string]string{"error": "无效请求"})
		return
	}

	var chunks []map[string]string
	if body.ChunksCfg != nil {
		raw, _ := json.Marshal(body.ChunksCfg)
		json.Unmarshal(raw, &chunks)
	}

	p := taskParams{
		text: body.Text, voice: body.Voice, instruct: body.Instruct,
		speed: body.Speed, fmt: body.Fmt, chunks: chunks,
	}
	applyDefaults(&p)
	task, pos := createTask(p)
	sendJSON(w, 200, map[string]any{"task_id": task.ID, "queue_pos": pos})
}

func handleTaskStatus(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/api/task/")
	queueMu.Lock()
	t, ok := taskMap[id]
	queueMu.Unlock()
	if !ok {
		sendJSON(w, 404, map[string]string{"error": "任务不存在"})
		return
	}
	sendJSON(w, 200, t)
}

func handleSplit(w http.ResponseWriter, r *http.Request) {
	var body struct{ Text string `json:"text"` }
	if readJSON(r, &body) != nil {
		sendJSON(w, 400, map[string]string{"error": "无效请求"})
		return
	}
	chunks := splitText(body.Text)
	sendJSON(w, 200, map[string]any{"chunks": chunks, "count": len(chunks)})
}

func handleHistory(w http.ResponseWriter, r *http.Request) {
	// Handle single-item GET
	if r.Method == "GET" && strings.HasPrefix(r.URL.Path, "/api/history/") {
		id := strings.TrimPrefix(r.URL.Path, "/api/history/")
		var id_, text, voice, instruct, fmt_, audioFile, status string
		var speed, duration, createdAt float64
		err := db.QueryRow(`SELECT id,text,voice,instruct,speed,fmt,audio_file,duration,status,created_at
			FROM history WHERE id=?`, id).Scan(&id_, &text, &voice, &instruct, &speed, &fmt_, &audioFile, &duration, &status, &createdAt)
		if err != nil {
			sendJSON(w, 404, map[string]string{"error": "记录不存在"})
			return
		}
		sendJSON(w, 200, map[string]any{
			"id": id_, "text": text, "voice": voice, "instruct": instruct,
			"speed": speed, "fmt": fmt_, "audio_file": audioFile, "duration": duration,
			"status": status, "created_at": createdAt,
		})
		return
	}

	q := r.URL.Query()
	page, _ := strconv.Atoi(q.Get("page"))
	if page < 1 {
		page = 1
	}
	perPage, _ := strconv.Atoi(q.Get("per_page"))
	if perPage < 1 || perPage > 100 {
		perPage = 20
	}
	offset := (page - 1) * perPage
	search := q.Get("q")

	var where string
	var args []any
	if search != "" {
		where = "WHERE text LIKE ?"
		escaped := strings.ReplaceAll(search, "%", "\\%")
		escaped = strings.ReplaceAll(escaped, "_", "\\_")
		args = append(args, "%"+escaped+"%")
	}

	var total int
	db.QueryRow(fmt.Sprintf("SELECT COUNT(*) FROM history %s", where), args...).Scan(&total)

	rows, err := db.Query(fmt.Sprintf(
		`SELECT id,text,voice,instruct,speed,fmt,audio_file,duration,status,created_at
		FROM history %s ORDER BY created_at DESC LIMIT ? OFFSET ?`, where),
		append(args, perPage, offset)...)
	if err != nil {
		sendJSON(w, 500, map[string]string{"error": "查询失败"})
		return
	}
	defer rows.Close()

	items := []map[string]any{}
	for rows.Next() {
		var id, text, voice, instruct, fmt_, audioFile, status string
		var speed, duration, createdAt float64
		rows.Scan(&id, &text, &voice, &instruct, &speed, &fmt_, &audioFile, &duration, &status, &createdAt)
		items = append(items, map[string]any{
			"id": id, "text": text, "voice": voice, "instruct": instruct,
			"speed": speed, "fmt": fmt_, "audio_file": audioFile, "duration": duration,
			"status": status, "created_at": createdAt,
		})
	}
	sendJSON(w, 200, map[string]any{
		"items": items, "total": total, "page": page, "per_page": perPage,
		"pages": (total + perPage - 1) / perPage,
	})
}

func handleDeleteHistory(w http.ResponseWriter, r *http.Request) {
	if r.Method == "DELETE" && r.URL.Path == "/api/history" {
		rows, _ := db.Query("SELECT audio_file FROM history WHERE audio_file IS NOT NULL")
		for rows.Next() {
			var f string
			rows.Scan(&f)
			os.Remove(filepath.Join(cfg.DataDir, "audio", filepath.Base(f)))
		}
		rows.Close()
		dbExec("DELETE FROM history")
		sendJSON(w, 200, map[string]bool{"ok": true})
		return
	}

	// Batch delete
	if r.Method == "POST" && r.URL.Path == "/api/history/batch" {
		var body struct{ IDs []string `json:"ids"` }
		if readJSON(r, &body) != nil || len(body.IDs) == 0 {
			sendJSON(w, 400, map[string]string{"error": "无效请求"})
			return
		}
		for _, id := range body.IDs {
			var audioFile string
			db.QueryRow("SELECT audio_file FROM history WHERE id=?", id).Scan(&audioFile)
			if audioFile != "" {
				os.Remove(filepath.Join(cfg.DataDir, "audio", filepath.Base(audioFile)))
			}
			dbExec("DELETE FROM history WHERE id=?", id)
		}
		sendJSON(w, 200, map[string]bool{"ok": true})
		return
	}

	// Delete single
	id := strings.TrimPrefix(r.URL.Path, "/api/history/")
	var audioFile string
	db.QueryRow("SELECT audio_file FROM history WHERE id=?", id).Scan(&audioFile)
	if audioFile != "" {
		os.Remove(filepath.Join(cfg.DataDir, "audio", filepath.Base(audioFile)))
	}
	dbExec("DELETE FROM history WHERE id=?", id)
	sendJSON(w, 200, map[string]bool{"ok": true})
}

func handlePresets(w http.ResponseWriter, r *http.Request) {
	// Delete preset
	if r.Method == "DELETE" {
		name := strings.TrimPrefix(r.URL.Path, "/api/presets/")
		if name == "" {
			sendJSON(w, 400, map[string]string{"error": "无效预设名"})
			return
		}
		dbExec("DELETE FROM settings WHERE key=?", "preset:"+name)
		sendJSON(w, 200, map[string]bool{"ok": true})
		return
	}

	if r.Method == "GET" {
		rows, err := db.Query("SELECT key, value FROM settings WHERE key LIKE 'preset:%' ORDER BY key")
		if err != nil {
			sendJSON(w, 500, map[string]string{"error": "查询失败"})
			return
		}
		defer rows.Close()
		presets := []map[string]any{}
		for rows.Next() {
			var key, val string
			rows.Scan(&key, &val)
			name := strings.TrimPrefix(key, "preset:")
			var data map[string]any
			json.Unmarshal([]byte(val), &data)
			data["name"] = name
			presets = append(presets, data)
		}
		sendJSON(w, 200, presets)
		return
	}

	// POST: save preset
	var body struct {
		Name     string  `json:"name"`
		Voice    string  `json:"voice"`
		Instruct string  `json:"instruct"`
		Speed    float64 `json:"speed"`
		Fmt      string  `json:"fmt"`
	}
	if readJSON(r, &body) != nil {
		sendJSON(w, 400, map[string]string{"error": "无效请求"})
		return
	}
	safe := reSafeName.ReplaceAllString(body.Name, "_")
	if len(safe) > 64 {
		safe = safe[:64]
	}
	data, _ := json.Marshal(map[string]any{"voice": body.Voice, "instruct": body.Instruct, "speed": body.Speed, "fmt": body.Fmt})
	dbSetSetting("preset:"+safe, string(data))
	sendJSON(w, 200, map[string]string{"name": safe})
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
	// CPU usage: two samples 200ms apart for accurate reading
	cpuPct := cpuUsage()

	// Memory from /proc/meminfo
	memTotal, memAvail := 0, 0
	if f, err := os.ReadFile("/proc/meminfo"); err == nil {
		for _, line := range strings.Split(string(f), "\n") {
			parts := strings.Fields(line)
			if len(parts) < 2 {
				continue
			}
			val, _ := strconv.Atoi(parts[1])
			if parts[0] == "MemTotal:" {
				memTotal = val
			} else if parts[0] == "MemAvailable:" {
				memAvail = val
			}
		}
	}

	// Disk
	var diskTotal, diskFree uint64
	var stat syscall.Statfs_t
	if syscall.Statfs(cfg.DataDir, &stat) == nil {
		diskTotal = stat.Blocks * uint64(stat.Bsize)
		diskFree = stat.Bavail * uint64(stat.Bsize)
	}
	diskUsed := diskTotal - diskFree
	diskPct := 0.0
	if diskTotal > 0 {
		diskPct = round(float64(diskUsed)/float64(diskTotal)*100, 1)
	}

	// Audio file stats
	audioDir := filepath.Join(cfg.DataDir, "audio")
	var audioFiles int
	var audioSize int64
	if entries, err := os.ReadDir(audioDir); err == nil {
		for _, e := range entries {
			if !e.IsDir() {
				if fi, err := e.Info(); err == nil {
					audioFiles++
					audioSize += fi.Size()
				}
			}
		}
	}

	// CrispASR process check
	crispASRActive := false
	var crispASRPid int
	if out, err := exec.Command("pgrep", "-f", "crispasr.*--server").Output(); err == nil {
		pids := strings.Fields(strings.TrimSpace(string(out)))
		if len(pids) > 0 {
			crispASRActive = true
			crispASRPid, _ = strconv.Atoi(pids[0])
		}
	}

	queueMu.Lock()
	qd := len(queue)
	hasActive := active != nil
	queueMu.Unlock()

	memPct := 0.0
	if memTotal > 0 {
		memPct = round(float64(memTotal-memAvail)/float64(memTotal)*100, 1)
	}

	sendJSON(w, 200, map[string]any{
		"crispasr": map[string]any{"active": crispASRActive, "pid": crispASRPid},
		"cpu":      map[string]any{"percent": round(cpuPct, 1)},
		"memory":   map[string]any{"total_mb": memTotal / 1024, "used_mb": (memTotal - memAvail) / 1024, "percent": memPct},
		"disk": map[string]any{
			"disk_total_gb": round(float64(diskTotal)/1e9, 1), "disk_used_gb": round(float64(diskUsed)/1e9, 1),
			"disk_free_gb": round(float64(diskFree)/1e9, 1), "disk_percent": diskPct,
			"audio_files": audioFiles, "audio_size_mb": round(float64(audioSize)/1e6, 1),
		},
		"queue": map[string]any{"depth": qd, "active": hasActive},
	})
}

// cpuUsage reads /proc/stat twice to get accurate CPU percentage
func cpuUsage() float64 {
	readStat := func() (idle, total float64) {
		if f, err := os.ReadFile("/proc/stat"); err == nil {
			line := string(f)[:strings.IndexByte(string(f), '\n')]
			parts := strings.Fields(line)
			if len(parts) > 5 {
				idle, _ = strconv.ParseFloat(parts[4], 64)
				iowait, _ := strconv.ParseFloat(parts[5], 64)
				idle += iowait
				for _, p := range parts[1:] {
					v, _ := strconv.ParseFloat(p, 64)
					total += v
				}
			}
		}
		return
	}
	idle1, total1 := readStat()
	time.Sleep(200 * time.Millisecond)
	idle2, total2 := readStat()
	dIdle := idle2 - idle1
	dTotal := total2 - total1
	if dTotal > 0 {
		return (1 - dIdle/dTotal) * 100
	}
	return 0
}

func handleVoices(w http.ResponseWriter, r *http.Request) {
	if r.Method == "GET" {
		rows, err := db.Query("SELECT name, filename, created_at FROM voices ORDER BY created_at DESC")
		if err != nil {
			sendJSON(w, 500, map[string]string{"error": "查询失败"})
			return
		}
		defer rows.Close()
		items := []map[string]any{}
		for rows.Next() {
			var name, filename string
			var createdAt float64
			rows.Scan(&name, &filename, &createdAt)
			items = append(items, map[string]any{"name": name, "filename": filename, "created_at": createdAt})
		}
		sendJSON(w, 200, items)
		return
	}

	// POST: upload voice clone
	r.ParseMultipartForm(cfg.MaxUpload)
	file, header, err := r.FormFile("audio")
	if err != nil {
		sendJSON(w, 400, map[string]string{"error": "未找到音频文件"})
		return
	}
	defer file.Close()

	name := r.FormValue("name")
	if name == "" {
		name = fmt.Sprintf("custom_%d", time.Now().Unix())
	}
	safe := reSafeNameHy.ReplaceAllString(name, "_")
	if len(safe) > 64 {
		safe = safe[:64]
	}

	uploadPath := filepath.Join(cfg.DataDir, "uploads", safe+".wav")
	os.MkdirAll(filepath.Dir(uploadPath), 0755)
	dst, err := os.Create(uploadPath)
	if err != nil {
		sendJSON(w, 500, map[string]string{"error": "保存文件失败"})
		return
	}
	written, err := io.Copy(dst, file)
	dst.Close()
	if err != nil {
		os.Remove(uploadPath)
		sendJSON(w, 500, map[string]string{"error": "写入文件失败"})
		return
	}

	// Copy to CrispASR voices dir
	voiceDir := filepath.Join(cfg.CrispASRDir, "voices")
	os.MkdirAll(voiceDir, 0755)
	voicePath := filepath.Join(voiceDir, safe+".wav")
	if err := os.Link(uploadPath, voicePath); err != nil {
		// Cross-filesystem: fall back to copy
		src, _ := os.Open(uploadPath)
		if src != nil {
			defer src.Close()
			if vdst, err := os.Create(voicePath); err == nil {
				io.Copy(vdst, src)
				vdst.Close()
			}
		}
	}

	dbExec("INSERT OR REPLACE INTO voices(name,filename,created_at) VALUES(?,?,?)", safe, safe+".wav", time.Now().Unix())
	log.Printf("Uploaded voice: %s (%d bytes from %s)", safe, written, header.Filename)
	sendJSON(w, 200, map[string]string{"name": safe, "filename": safe + ".wav"})
}

func handleDeleteVoice(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimPrefix(r.URL.Path, "/api/voices/")
	var filename string
	db.QueryRow("SELECT filename FROM voices WHERE name=?", name).Scan(&filename)
	os.Remove(filepath.Join(cfg.DataDir, "uploads", filepath.Base(filename)))
	os.Remove(filepath.Join(cfg.CrispASRDir, "voices", filepath.Base(filename)))
	dbExec("DELETE FROM voices WHERE name=?", name)
	sendJSON(w, 200, map[string]bool{"ok": true})
}

func handleAudition(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Text     string  `json:"text"`
		Voice    string  `json:"voice"`
		Instruct string  `json:"instruct"`
		Speed    float64 `json:"speed"`
	}
	readJSON(r, &body)
	p := taskParams{voice: body.Voice, speed: body.Speed}
	applyDefaults(&p)

	payload, _ := json.Marshal(map[string]any{
		"model": "tts-1", "input": body.Text, "voice": p.voice,
		"speed": p.speed, "consent_attestation": "test", "spoken_disclaimer": false,
	})
	req, _ := http.NewRequest("POST", "http://localhost:8080/v1/audio/speech", strings.NewReader(string(payload)))
	req.Header.Set("Content-Type", "application/json")
	resp, err := httpClient.Do(req)
	if err != nil {
		sendJSON(w, 500, map[string]string{"error": err.Error()})
		return
	}
	defer resp.Body.Close()
	w.Header().Set("Content-Type", "audio/wav")
	io.Copy(w, io.LimitReader(resp.Body, maxAudioSize))
}

func handleCompare(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Text     string  `json:"text"`
		VoiceA   string  `json:"voice_a"`
		VoiceB   string  `json:"voice_b"`
		Instruct string  `json:"instruct"`
		Speed    float64 `json:"speed"`
		Fmt      string  `json:"fmt"`
	}
	readJSON(r, &body)
	applyDefaultsPtr(&body.Speed, &body.Fmt)

	results := []string{}
	for _, voice := range []string{body.VoiceA, body.VoiceB} {
		p := taskParams{
			text: body.Text, voice: voice, instruct: body.Instruct,
			speed: body.Speed, fmt: body.Fmt,
			chunks: []map[string]string{{"text": body.Text, "voice": voice, "instruct": body.Instruct}},
		}
		task, _ := createTask(p)
		results = append(results, task.ID)
	}
	sendJSON(w, 200, map[string]any{"task_a": results[0], "task_b": results[1]})
}

// applyDefaultsPtr for cases where we only have speed/fmt pointers
func applyDefaultsPtr(speed *float64, fmt_ *string) {
	if *speed == 0 {
		*speed = 1.0
	}
	if *fmt_ == "" {
		*fmt_ = "wav"
	}
}

func handleBatch(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Texts    []string `json:"texts"`
		Voice    string   `json:"voice"`
		Instruct string   `json:"instruct"`
		Speed    float64  `json:"speed"`
		Fmt      string   `json:"fmt"`
	}
	readJSON(r, &body)
	if len(body.Texts) == 0 {
		sendJSON(w, 400, map[string]string{"error": "texts不能为空"})
		return
	}
	if len(body.Texts) > maxBatchItems {
		sendJSON(w, 400, map[string]string{"error": "单次最多20条"})
		return
	}

	p := taskParams{voice: body.Voice, speed: body.Speed, fmt: body.Fmt, instruct: body.Instruct}
	applyDefaults(&p)

	ids := []string{}
	for _, text := range body.Texts {
		text = strings.TrimSpace(text)
		if text == "" {
			continue
		}
		task, _ := createTask(taskParams{
			text: text, voice: p.voice, instruct: p.instruct,
			speed: p.speed, fmt: p.fmt,
			chunks: []map[string]string{{"text": text, "voice": p.voice, "instruct": p.instruct}},
		})
		ids = append(ids, task.ID)
	}
	sendJSON(w, 200, map[string]any{"task_ids": ids, "count": len(ids)})
}

func handleCrispASRVersion(w http.ResponseWriter, r *http.Request) {
	current := getCrispASRVersion()
	sendJSON(w, 200, map[string]string{"current": current, "latest": current})
}

func getCrispASRVersion() string {
	binary := findCrispASR()
	out, err := exec.Command(binary, "--version").CombinedOutput()
	if err != nil {
		return "unknown"
	}
	if m := reSemVer.FindStringSubmatch(string(out)); len(m) > 1 {
		return m[1]
	}
	return "unknown"
}

func handleCrispASRUpdate(w http.ResponseWriter, r *http.Request) {
	updateScript := filepath.Join(cfg.CrispASRDir, "update.sh")
	if _, err := os.Stat(updateScript); err != nil {
		sendJSON(w, 400, map[string]string{"error": "未找到更新脚本", "hint": "在 CRISPASR_DIR 下放置 update.sh"})
		return
	}
	out, err := exec.Command("/bin/bash", updateScript).CombinedOutput()
	if err != nil {
		sendJSON(w, 500, map[string]any{"success": false, "message": "更新失败", "log": string(out)})
		return
	}
	sendJSON(w, 200, map[string]any{"success": true, "message": "更新完成", "log": string(out)})
}

func handleResumable(w http.ResponseWriter, r *http.Request) {
	// Find the most recent incomplete task
	var id, status string
	var current, total int
	err := db.QueryRow(`SELECT id, status, current, total FROM history
		WHERE status IN ('pending','processing','generating')
		ORDER BY created_at DESC LIMIT 1`).Scan(&id, &status, &current, &total)
	if err != nil {
		sendJSON(w, 200, map[string]any{"task_id": nil})
		return
	}
	sendJSON(w, 200, map[string]any{"task_id": id, "status": status, "completed": current, "total": total})
}

func handleResume(w http.ResponseWriter, r *http.Request) {
	// Re-queue the most recent incomplete task
	var id string
	err := db.QueryRow(`SELECT id FROM history
		WHERE status IN ('pending','processing','generating')
		ORDER BY created_at DESC LIMIT 1`).Scan(&id)
	if err != nil {
		sendJSON(w, 404, map[string]string{"error": "无可恢复任务"})
		return
	}
	queueMu.Lock()
	if _, exists := taskMap[id]; exists {
		queueMu.Unlock()
		sendJSON(w, 200, map[string]string{"task_id": id, "message": "任务已在队列中"})
		return
	}
	queueMu.Unlock()

	// Reconstruct task from DB
	var text, voice, instruct, fmt_, chunksJSON string
	var speed float64
	db.QueryRow(`SELECT text,voice,instruct,speed,fmt,chunks_config FROM history WHERE id=?`, id).
		Scan(&text, &voice, &instruct, &speed, &fmt_, &chunksJSON)
	var chunks []map[string]string
	json.Unmarshal([]byte(chunksJSON), &chunks)
	task := &Task{ID: id, Status: "pending", Total: len(chunks), Voice: voice,
		Instruct: instruct, Speed: speed, Fmt: fmt_,
		ChunksJSON: chunksJSON, APBase: "http://localhost:8080"}
	enqueue(task)
	sendJSON(w, 200, map[string]string{"task_id": id})
}

func handleLogs(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	lines := q.Get("lines")
	if lines == "" {
		lines = "200"
	}
	// Validate lines is a number
	if _, err := strconv.Atoi(lines); err != nil {
		lines = "200"
	}

	filter := q.Get("q")
	args := []string{"-u", "crispasr", "-n", lines, "--no-pager", "--output=short-iso"}
	if filter != "" {
		args = append(args, "--grep="+filter)
	}

	out, err := exec.Command("journalctl", args...).CombinedOutput()
	if err != nil {
		sendJSON(w, 500, map[string]string{"error": "无法读取日志"})
		return
	}
	sendJSON(w, 200, map[string]string{"logs": string(out)})
}

// ─── Text Split ─────────────────────────────────────────

func splitText(text string) []map[string]string {
	if len(text) <= splitThreshold {
		return []map[string]string{{"text": text}}
	}
	chunks := []string{}
	runes := []rune(text)
	i := 0
	for i < len(runes) {
		end := i + splitThreshold
		if end > len(runes) {
			end = len(runes)
		}
		if end < len(runes) {
			for j := end; j > i+200 && j > i; j-- {
				if runes[j-1] == '。' || runes[j-1] == '.' || runes[j-1] == '！' || runes[j-1] == '？' || runes[j-1] == '\n' {
					end = j
					break
				}
			}
		}
		chunks = append(chunks, string(runes[i:end]))
		i = end
	}
	result := make([]map[string]string, len(chunks))
	for i, c := range chunks {
		result[i] = map[string]string{"text": c}
	}
	return result
}

// ─── Helpers ─────────────────────────────────────────────

// truncate by runes to avoid breaking UTF-8
func truncate(s string, n int) string {
	runes := []rune(s)
	if len(runes) <= n {
		return s
	}
	return string(runes[:n])
}

func round(v float64, d int) float64 {
	p := 1.0
	for i := 0; i < d; i++ {
		p *= 10
	}
	return float64(int(v*p+0.5)) / p
}

// safePath prevents path traversal by cleaning and basing the name
func safePath(baseDir, name string) string {
	return filepath.Join(baseDir, filepath.Base(filepath.Clean(name)))
}

// ─── Main ────────────────────────────────────────────────

func main() {
	initConfig()

	// Load password from env file
	if cfg.Password == "" {
		if data, err := os.ReadFile(envFilePath); err == nil {
			for _, line := range strings.Split(string(data), "\n") {
				if strings.HasPrefix(line, "TTS_PASSWORD=") {
					cfg.Password = strings.TrimPrefix(line, "TTS_PASSWORD=")
				}
			}
		}
	}

	// Generate or persist JWT secret
	if cfg.JWTSecret == "" {
		jwtPath := filepath.Join(cfg.DataDir, ".jwt_secret")
		if data, err := os.ReadFile(jwtPath); err == nil && len(data) >= 32 {
			cfg.JWTSecret = string(data)
		} else {
			b := make([]byte, 32)
			rand.Read(b)
			cfg.JWTSecret = fmt.Sprintf("%x", b)
			os.MkdirAll(cfg.DataDir, 0755)
			os.WriteFile(jwtPath, []byte(cfg.JWTSecret), 0600)
		}
	}

	// Periodically clean up login rate-limit log
	go func() {
		for {
			time.Sleep(loginRateWindow)
			cleanupLoginLog()
		}
	}()

	if err := initDB(); err != nil {
		log.Fatal("DB init failed: ", err)
	}

	go queueLoop()

	staticDir := filepath.Join(".", "static")
	fs := http.FileServer(http.Dir(staticDir))

	mux := http.NewServeMux()

	// Static files
	mux.Handle("/static/", http.StripPrefix("/static/", fs))

	// Public routes
	mux.HandleFunc("/api/login", handleLogin)
	mux.HandleFunc("/api/check", handleCheck)

	// Protected routes
	mux.HandleFunc("/api/model", requireAuth(handleModel))
	mux.HandleFunc("/api/models", requireAuth(handleModels))
	mux.HandleFunc("/api/model/switch", requireAuth(handleSwitchModel))
	mux.HandleFunc("/api/status", requireAuth(handleStatus))
	mux.HandleFunc("/api/logs", requireAuth(handleLogs))
	mux.HandleFunc("/api/presets", requireAuth(handlePresets))
	mux.HandleFunc("/api/presets/", requireAuth(handlePresets))
	mux.HandleFunc("/api/generate", requireAuth(handleGenerate))
	mux.HandleFunc("/api/split", requireAuth(handleSplit))
	mux.HandleFunc("/api/audition", requireAuth(handleAudition))
	mux.HandleFunc("/api/compare", requireAuth(handleCompare))
	mux.HandleFunc("/api/batch", requireAuth(handleBatch))
	mux.HandleFunc("/api/crispasr/version", requireAuth(handleCrispASRVersion))
	mux.HandleFunc("/api/crispasr/update", requireAuth(handleCrispASRUpdate))
	mux.HandleFunc("/api/resumable", requireAuth(handleResumable))
	mux.HandleFunc("/api/resume", requireAuth(handleResume))
	mux.HandleFunc("/api/voices", requireAuth(handleVoices))
	mux.HandleFunc("/api/history", requireAuth(handleHistory))
	mux.HandleFunc("/api/history/", requireAuth(handleDeleteHistory))
	mux.HandleFunc("/api/task/", requireAuth(handleTaskStatus))
	mux.HandleFunc("/api/voices/", requireAuth(handleDeleteVoice))
	mux.HandleFunc("/api/change-password", requireAuth(handleChangePassword))

	// Audio serving (auth via header or ?token=) — path traversal safe
	audioDir := filepath.Join(cfg.DataDir, "audio")
	audioFs := http.FileServer(http.Dir(audioDir))
	mux.HandleFunc("/api/audio/", func(w http.ResponseWriter, r *http.Request) {
		if !authed(r) {
			http.Error(w, "Unauthorized", 401)
			return
		}
		name := strings.TrimPrefix(r.URL.Path, "/api/audio/")
		if strings.Contains(name, "..") {
			http.Error(w, "Forbidden", 403)
			return
		}
		r.URL.Path = "/" + name
		audioFs.ServeHTTP(w, r)
	})

	// Upload serving — path traversal safe
	uploadDir := filepath.Join(cfg.DataDir, "uploads")
	uploadFs := http.FileServer(http.Dir(uploadDir))
	mux.HandleFunc("/uploads/", func(w http.ResponseWriter, r *http.Request) {
		if !authed(r) {
			http.Error(w, "Unauthorized", 401)
			return
		}
		name := strings.TrimPrefix(r.URL.Path, "/uploads/")
		if strings.Contains(name, "..") {
			http.Error(w, "Forbidden", 403)
			return
		}
		r.URL.Path = "/" + name
		uploadFs.ServeHTTP(w, r)
	})

	// Root → index.html
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		http.ServeFile(w, r, filepath.Join(staticDir, "index.html"))
	})

	addr := fmt.Sprintf(":%d", cfg.Port)
	log.Printf("CrispASR Web UI v%s-go listening on %s", appVersion, addr)
	log.Fatal(http.ListenAndServe(addr, cors(mux)))
}

func cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin == "" {
			origin = "*"
		}
		w.Header().Set("Access-Control-Allow-Origin", origin)
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if r.Method == "OPTIONS" {
			w.WriteHeader(200)
			return
		}
		next.ServeHTTP(w, r)
	})
}
