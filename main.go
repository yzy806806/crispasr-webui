package main

import (
	"crypto/hmac"
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
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
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
	loginMu   sync.Mutex
	loginLog  = map[string][]time.Time{}
)

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
	if len(body.NewPassword) < 4 {
		sendJSON(w, 400, map[string]string{"error": "新密码至少4位"})
		return
	}
	// Update in-memory
	cfg.Password = body.NewPassword
	// Persist to env file
	envPath := envOr("TTS_ENV_FILE", "/etc/tts-webui.env")
	writeEnvPassword(envPath, body.NewPassword)
	sendJSON(w, 200, map[string]string{"message": "密码已修改"})
}

func writeEnvPassword(path, password string) {
	data, err := os.ReadFile(path)
	if err != nil {
		// Create new file
		os.WriteFile(path, []byte("TTS_PASSWORD="+password+"\n"), 0644)
		return
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
	os.WriteFile(path, []byte(strings.Join(lines, "\n")), 0644)
}

func handleLogin(w http.ResponseWriter, r *http.Request) {
	ip := strings.Split(r.RemoteAddr, ":")[0]
	loginMu.Lock()
	now := time.Now()
	cutoff := now.Add(-5 * time.Minute)
	recent := []time.Time{}
	for _, t := range loginLog[ip] {
		if t.After(cutoff) {
			recent = append(recent, t)
		}
	}
	if len(recent) >= 10 {
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
	db.QueryRow("SELECT value FROM settings WHERE key=?", key).Scan(&val)
	return val
}

func dbSetSetting(key, val string) {
	db.Exec("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", key, val)
}

// ─── Task Queue ──────────────────────────────────────────

type Task struct {
	ID          string  `json:"id"`
	Status      string  `json:"status"`
	Progress    float64 `json:"progress"`
	Current     int     `json:"current"`
	Total       int     `json:"total"`
	AudioURL    string  `json:"audio_url"`
	Error       string  `json:"error"`
	Duration    float64 `json:"duration"`
	QueuePos    int     `json:"queue_pos"`
	Voice       string  `json:"voice,omitempty"`
	Instruct    string  `json:"instruct,omitempty"`
	Speed       float64 `json:"speed,omitempty"`
	Fmt         string  `json:"fmt,omitempty"`
	ChunksJSON  string  `json:"-"`
	APBase      string  `json:"-"`
}

var (
	queueMu   sync.Mutex
	queue     []*Task
	active    *Task
	taskMap   = map[string]*Task{}
	taskCond  = sync.NewCond(&queueMu)
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
		// Update positions
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
	json.Unmarshal([]byte(t.ChunksJSON), &chunks)

	t.Status = "processing"
	db.Exec("UPDATE history SET status='processing' WHERE id=?", t.ID)

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
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Status = "error"
			t.Error = err.Error()
			db.Exec("UPDATE history SET status='error' WHERE id=?", t.ID)
			return
		}
		audio, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		combined = append(combined, audio)
	}

	// Concatenate WAV files
	finalWAV := concatWAVs(combined)
	audioFile := t.ID + ".wav"
	os.MkdirAll(filepath.Join(cfg.DataDir, "audio"), 0755)
	os.WriteFile(filepath.Join(cfg.DataDir, "audio", audioFile), finalWAV, 0644)

	duration := wavDuration(finalWAV)
	t.Status = "done"
	t.AudioURL = "/api/audio/" + audioFile
	t.Duration = duration

	db.Exec("UPDATE history SET status='done',audio_file=?,duration=? WHERE id=?", audioFile, duration, t.ID)
}

func concatWAVs(wavs [][]byte) []byte {
	if len(wavs) == 0 {
		return nil
	}
	if len(wavs) == 1 {
		return wavs[0]
	}
	// Simple WAV concat: strip headers from 2nd+, append PCM data
	result := make([]byte, len(wavs[0]))
	copy(result, wavs[0])
	for _, w := range wavs[1:] {
		if len(w) > 44 {
			result = append(result, w[44:]...)
		}
	}
	// Fix WAV header: update data chunk size and RIFF size
	dataSize := uint32(len(result) - 44)
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
	if len(data) < 44 {
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
	// Restart crispasr via systemd
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
	re := regexp.MustCompile(`ExecStart=.*`)
	newContent := re.ReplaceAllString(string(content), "ExecStart="+execStart)
	os.WriteFile(svcPath, []byte(newContent), 0644)
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
		Text        string  `json:"text"`
		Voice       string  `json:"voice"`
		Instruct    string  `json:"instruct"`
		Speed       float64 `json:"speed"`
		Fmt         string  `json:"fmt"`
		ChunksCfg   any     `json:"chunks_config"`
	}
	if readJSON(r, &body) != nil {
		sendJSON(w, 400, map[string]string{"error": "无效请求"})
		return
	}
	if body.Voice == "" {
		body.Voice = "serena"
	}
	if body.Speed == 0 {
		body.Speed = 1.0
	}
	if body.Fmt == "" {
		body.Fmt = "wav"
	}

	// Build chunks
	var chunks []map[string]string
	if body.ChunksCfg != nil {
		raw, _ := json.Marshal(body.ChunksCfg)
		json.Unmarshal(raw, &chunks)
	} else {
		chunks = splitText(body.Text)
	}

	chunksJSON, _ := json.Marshal(chunks)
	taskID := fmt.Sprintf("%x", time.Now().UnixNano())[:12]

	db.Exec(`INSERT INTO history(id,text,voice,instruct,speed,fmt,status,chunks_config,created_at)
		VALUES(?,?,?,?,?,?,?,?,?)`, taskID, truncate(body.Text, 2000), body.Voice, body.Instruct,
		body.Speed, body.Fmt, "pending", string(chunksJSON), time.Now().Unix())

	task := &Task{
		ID: taskID, Status: "pending", Total: len(chunks), Voice: body.Voice,
		Instruct: body.Instruct, Speed: body.Speed, Fmt: body.Fmt,
		ChunksJSON: string(chunksJSON), APBase: "http://localhost:8080",
	}
	pos := enqueue(task)
	sendJSON(w, 200, map[string]any{"task_id": taskID, "queue_pos": pos})
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
		args = append(args, "%"+search+"%")
	}

	var total int
	db.QueryRow(fmt.Sprintf("SELECT COUNT(*) FROM history %s", where), args...).Scan(&total)

	rows, _ := db.Query(fmt.Sprintf(
		`SELECT id,text,voice,instruct,speed,fmt,audio_file,duration,status,created_at
		FROM history %s ORDER BY created_at DESC LIMIT ? OFFSET ?`, where),
		append(args, perPage, offset)...)
	defer rows.Close()

	items := []map[string]any{}
	for rows.Next() {
		var id, text, voice, instruct, fmt_, audioFile, status string
		var speed, duration float64
		var createdAt float64
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
		// Delete all
		rows, _ := db.Query("SELECT audio_file FROM history WHERE audio_file IS NOT NULL")
		for rows.Next() {
			var f string
			rows.Scan(&f)
			os.Remove(filepath.Join(cfg.DataDir, "audio", f))
		}
		rows.Close()
		db.Exec("DELETE FROM history")
		sendJSON(w, 200, map[string]bool{"ok": true})
		return
	}
	// Delete single
	id := strings.TrimPrefix(r.URL.Path, "/api/history/")
	var audioFile string
	db.QueryRow("SELECT audio_file FROM history WHERE id=?", id).Scan(&audioFile)
	if audioFile != "" {
		os.Remove(filepath.Join(cfg.DataDir, "audio", audioFile))
	}
	db.Exec("DELETE FROM history WHERE id=?", id)
	sendJSON(w, 200, map[string]bool{"ok": true})
}

func handlePresets(w http.ResponseWriter, r *http.Request) {
	if r.Method == "GET" {
		rows, _ := db.Query("SELECT key, value FROM settings WHERE key LIKE 'preset:%' ORDER BY key")
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
		Name    string  `json:"name"`
		Voice   string  `json:"voice"`
		Instruct string `json:"instruct"`
		Speed   float64 `json:"speed"`
		Fmt     string  `json:"fmt"`
	}
	readJSON(r, &body)
	safe := regexp.MustCompile(`[^\w]`).ReplaceAllString(body.Name, "_")
	if len(safe) > 64 {
		safe = safe[:64]
	}
	data, _ := json.Marshal(map[string]any{"voice": body.Voice, "instruct": body.Instruct, "speed": body.Speed, "fmt": body.Fmt})
	dbSetSetting("preset:"+safe, string(data))
	sendJSON(w, 200, map[string]string{"name": safe})
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
	// CPU usage from /proc/stat
	cpuPct := 0.0
	if f, err := os.ReadFile("/proc/stat"); err == nil {
		parts := strings.Fields(string(f)[:strings.IndexByte(string(f), '\n')])
		if len(parts) > 5 {
			idle, _ := strconv.ParseFloat(parts[4], 64)
			iowait, _ := strconv.ParseFloat(parts[5], 64)
			total := 0.0
			for _, p := range parts[1:] {
				v, _ := strconv.ParseFloat(p, 64)
				total += v
			}
			if total > 0 {
				cpuPct = (1 - (idle+iowait)/total) * 100
			}
		}
	}

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

	queueMu.Lock()
	qd := len(queue)
	hasActive := active != nil
	queueMu.Unlock()

	sendJSON(w, 200, map[string]any{
		"cpu":    map[string]any{"percent": round(cpuPct, 1)},
		"memory": map[string]any{"total_mb": memTotal / 1024, "used_mb": (memTotal - memAvail) / 1024, "percent": round(float64(memTotal-memAvail)/float64(memTotal)*100, 1)},
		"disk":   map[string]any{"total_gb": round(float64(diskTotal)/1e9, 1), "free_gb": round(float64(diskFree)/1e9, 1), "percent": round(float64(diskTotal-diskFree)/float64(diskTotal)*100, 1)},
		"queue":  map[string]any{"depth": qd, "active": hasActive},
	})
}

func handleVoices(w http.ResponseWriter, r *http.Request) {
	if r.Method == "GET" {
		rows, _ := db.Query("SELECT name, filename, created_at FROM voices ORDER BY created_at DESC")
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
	safe := regexp.MustCompile(`[^\w-]`).ReplaceAllString(name, "_")
	if len(safe) > 64 {
		safe = safe[:64]
	}

	uploadPath := filepath.Join(cfg.DataDir, "uploads", safe+".wav")
	os.MkdirAll(filepath.Dir(uploadPath), 0755)
	dst, _ := os.Create(uploadPath)
	io.Copy(dst, file)
	dst.Close()

	// Copy to CrispASR voices dir
	voiceDir := filepath.Join(cfg.CrispASRDir, "voices")
	os.MkdirAll(voiceDir, 0755)
	os.Link(uploadPath, filepath.Join(voiceDir, safe+".wav"))

	db.Exec("INSERT OR REPLACE INTO voices(name,filename,created_at) VALUES(?,?,?)", safe, safe+".wav", time.Now().Unix())
	log.Printf("Uploaded voice: %s (%d bytes from %s)", safe, header.Size, header.Filename)
	sendJSON(w, 200, map[string]string{"name": safe, "filename": safe + ".wav"})
}

func handleDeleteVoice(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimPrefix(r.URL.Path, "/api/voices/")
	var filename string
	db.QueryRow("SELECT filename FROM voices WHERE name=?", name).Scan(&filename)
	os.Remove(filepath.Join(cfg.DataDir, "uploads", filename))
	os.Remove(filepath.Join(cfg.CrispASRDir, "voices", filename))
	db.Exec("DELETE FROM voices WHERE name=?", name)
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
	if body.Voice == "" {
		body.Voice = "serena"
	}
	if body.Speed == 0 {
		body.Speed = 1.0
	}

	payload, _ := json.Marshal(map[string]any{
		"model": "tts-1", "input": body.Text, "voice": body.Voice,
		"speed": body.Speed, "consent_attestation": "test", "spoken_disclaimer": false,
	})
	req, _ := http.NewRequest("POST", "http://localhost:8080/v1/audio/speech", strings.NewReader(string(payload)))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		sendJSON(w, 500, map[string]string{"error": err.Error()})
		return
	}
	defer resp.Body.Close()
	w.Header().Set("Content-Type", "audio/wav")
	io.Copy(w, resp.Body)
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
	if body.Speed == 0 {
		body.Speed = 1.0
	}
	if body.Fmt == "" {
		body.Fmt = "wav"
	}

	results := []string{}
	for _, voice := range []string{body.VoiceA, body.VoiceB} {
		chunks := []map[string]string{{"text": body.Text, "voice": voice, "instruct": body.Instruct}}
		chunksJSON, _ := json.Marshal(chunks)
		taskID := fmt.Sprintf("%x", time.Now().UnixNano())[:12]
		db.Exec(`INSERT INTO history(id,text,voice,instruct,speed,fmt,status,chunks_config,created_at)
			VALUES(?,?,?,?,?,?,?,?,?)`, taskID, truncate(body.Text, 2000), voice, body.Instruct,
			body.Speed, body.Fmt, "pending", string(chunksJSON), time.Now().Unix())
		task := &Task{ID: taskID, Status: "pending", Total: 1, Voice: voice,
			Instruct: body.Instruct, Speed: body.Speed, Fmt: body.Fmt,
			ChunksJSON: string(chunksJSON), APBase: "http://localhost:8080"}
		enqueue(task)
		results = append(results, taskID)
	}
	sendJSON(w, 200, map[string]any{"task_a": results[0], "task_b": results[1]})
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
	if len(body.Texts) > 20 {
		sendJSON(w, 400, map[string]string{"error": "单次最多20条"})
		return
	}
	if body.Voice == "" {
		body.Voice = "serena"
	}
	if body.Speed == 0 {
		body.Speed = 1.0
	}

	ids := []string{}
	for _, text := range body.Texts {
		text = strings.TrimSpace(text)
		if text == "" {
			continue
		}
		chunks := []map[string]string{{"text": text, "voice": body.Voice, "instruct": body.Instruct}}
		chunksJSON, _ := json.Marshal(chunks)
		taskID := fmt.Sprintf("%x", time.Now().UnixNano())[:12]
		db.Exec(`INSERT INTO history(id,text,voice,instruct,speed,fmt,status,chunks_config,created_at)
			VALUES(?,?,?,?,?,?,?,?,?)`, taskID, truncate(text, 2000), body.Voice, body.Instruct,
			body.Speed, body.Fmt, "pending", string(chunksJSON), time.Now().Unix())
		task := &Task{ID: taskID, Status: "pending", Total: 1, Voice: body.Voice,
			Instruct: body.Instruct, Speed: body.Speed, Fmt: body.Fmt,
			ChunksJSON: string(chunksJSON), APBase: "http://localhost:8080"}
		enqueue(task)
		ids = append(ids, taskID)
	}
	sendJSON(w, 200, map[string]any{"task_ids": ids, "count": len(ids)})
}

func handleCrispASRVersion(w http.ResponseWriter, r *http.Request) {
	current := getCrispASRVersion()
	sendJSON(w, 200, map[string]string{"current": current})
}

func getCrispASRVersion() string {
	binary := findCrispASR()
	out, err := exec.Command(binary, "--version").CombinedOutput()
	if err != nil {
		return "unknown"
	}
	re := regexp.MustCompile(`(\d+\.\d+\.\d+)`)
	if m := re.FindStringSubmatch(string(out)); len(m) > 1 {
		return m[1]
	}
	return "unknown"
}

func handleLogs(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	lines := q.Get("lines")
	if lines == "" {
		lines = "200"
	}
	out, err := exec.Command("journalctl", "-u", "crispasr", "-n", lines, "--no-pager", "--output=short-iso").CombinedOutput()
	if err != nil {
		sendJSON(w, 500, map[string]string{"error": "无法读取日志"})
		return
	}
	sendJSON(w, 200, map[string]string{"logs": string(out)})
}

// ─── Text Split ─────────────────────────────────────────

func splitText(text string) []map[string]string {
	if len(text) <= 800 {
		return []map[string]string{{"text": text}}
	}
	// Split at sentence boundaries
	chunks := []string{}
	runes := []rune(text)
	i := 0
	for i < len(runes) {
		end := i + 800
		if end > len(runes) {
			end = len(runes)
		}
		if end < len(runes) {
			// Find sentence break
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

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

func round(v float64, d int) float64 {
	p := 1.0
	for i := 0; i < d; i++ {
		p *= 10
	}
	return float64(int(v*p+0.5)) / p
}

// ─── Main ────────────────────────────────────────────────

func main() {
	initConfig()

	// Load password from env file
	if cfg.Password == "" {
		if data, err := os.ReadFile("/etc/tts-webui.env"); err == nil {
			for _, line := range strings.Split(string(data), "\n") {
				if strings.HasPrefix(line, "TTS_PASSWORD=") {
					cfg.Password = strings.TrimPrefix(line, "TTS_PASSWORD=")
				}
			}
		}
	}

	// Generate JWT secret if not set
	if cfg.JWTSecret == "" {
		cfg.JWTSecret = fmt.Sprintf("%x", time.Now().UnixNano())
	}

	// Init database
	if err := initDB(); err != nil {
		log.Fatal("DB init failed: ", err)
	}

	// Start task queue
	go queueLoop()

	// Serve static files
	staticDir := filepath.Join(".", "static")
	fs := http.FileServer(http.Dir(staticDir))

	// Build mux
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
	mux.HandleFunc("/api/generate", requireAuth(handleGenerate))
	mux.HandleFunc("/api/split", requireAuth(handleSplit))
	mux.HandleFunc("/api/audition", requireAuth(handleAudition))
	mux.HandleFunc("/api/compare", requireAuth(handleCompare))
	mux.HandleFunc("/api/batch", requireAuth(handleBatch))
	mux.HandleFunc("/api/crispasr/version", requireAuth(handleCrispASRVersion))
	mux.HandleFunc("/api/voices", requireAuth(handleVoices))
	mux.HandleFunc("/api/history", requireAuth(handleHistory))
	mux.HandleFunc("/api/history/", requireAuth(handleDeleteHistory))
	mux.HandleFunc("/api/task/", requireAuth(handleTaskStatus))
	mux.HandleFunc("/api/voices/", requireAuth(handleDeleteVoice))
	mux.HandleFunc("/api/change-password", requireAuth(handleChangePassword))

	// Audio serving (auth via header or ?token=)
	audioDir := filepath.Join(cfg.DataDir, "audio")
	audioFs := http.FileServer(http.Dir(audioDir))
	mux.HandleFunc("/api/audio/", func(w http.ResponseWriter, r *http.Request) {
		if !authed(r) {
			http.Error(w, "Unauthorized", 401)
			return
		}
		http.StripPrefix("/api/audio/", audioFs).ServeHTTP(w, r)
	})

	// Upload serving
	uploadDir := filepath.Join(cfg.DataDir, "uploads")
	uploadFs := http.FileServer(http.Dir(uploadDir))
	mux.HandleFunc("/uploads/", func(w http.ResponseWriter, r *http.Request) {
		if !authed(r) {
			http.Error(w, "Unauthorized", 401)
			return
		}
		http.StripPrefix("/uploads/", uploadFs).ServeHTTP(w, r)
	})

	// Root → index.html
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		http.ServeFile(w, r, filepath.Join(staticDir, "index.html"))
	})

	// CORS middleware
	handler := cors(mux)

	addr := fmt.Sprintf(":%d", cfg.Port)
	log.Printf("CrispASR Web UI v0.9.3-go listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, handler))
}

func cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if r.Method == "OPTIONS" {
			w.WriteHeader(200)
			return
		}
		next.ServeHTTP(w, r)
	})
}
