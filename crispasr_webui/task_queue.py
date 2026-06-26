#!/usr/bin/env python3
"""
CrispASR TTS Web UI v3 — Task Queue
Background TTS generation with queue, position tracking, resume support.
Imports: config, database, audio_utils, text_split
"""

import json
import os
import subprocess
import threading
import time
import urllib.request

from . import config
from . import database
from . import audio_utils
# text_split imported lazily only if needed (currently not used here directly)


# ─── Module-level state ─────────────────────────────────
# {task_id: {"status", "progress", "total", "current", "audio_url", "error", "chunks", "finished_at", "queue_pos"}}
_tasks: dict[str, dict] = {}

# H3: Lock ordering to prevent deadlock — always acquire in this order:
#   _queue_lock → _tasks_lock → _update_lock
# Never acquire a lower-priority lock while holding a higher-priority one.
_tasks_lock = threading.Lock()
_task_queue: list[str] = []  # ordered list of pending task_ids
_queue_lock = threading.Lock()
_active_task_id: str | None = None


def enqueue_task(task_id: str, task_info: dict) -> int:
    """Add a task to the queue and start it if no active task.
    
    Returns the queue position (0 = running immediately).
    Thread-safe: acquires _queue_lock and _tasks_lock internally.
    """
    global _active_task_id
    with _tasks_lock:
        _tasks[task_id] = task_info

    should_start = False
    with _queue_lock:
        queue_pos = len(_task_queue)
        _task_queue.append(task_id)
        with _tasks_lock:
            _tasks[task_id]["queue_pos"] = queue_pos
        # H2: If no active task, start this one directly (atomic with queue add)
        if _active_task_id is None:
            _active_task_id = task_id
            _task_queue.pop(0)  # Remove from queue since we're running it
            should_start = True
    
    # Start task thread outside the lock to avoid holding it during I/O
    if should_start:
        t = threading.Thread(target=_run_task, args=(task_id,), daemon=True)
        t.start()
    
    return queue_pos


def get_task(task_id: str) -> dict:
    """Get task info by ID (thread-safe)."""
    with _tasks_lock:
        return dict(_tasks.get(task_id, {}))

def queue_depth() -> int:
    """Get current queue depth (thread-safe)."""
    with _queue_lock:
        return len(_task_queue)

def has_active_task() -> bool:
    """Check if a task is currently running (thread-safe)."""
    with _queue_lock:
        return _active_task_id is not None


def cleanup_tasks() -> None:
    """Public wrapper for _cleanup_tasks."""
    _cleanup_tasks()


def _cleanup_tasks() -> None:
    """Remove completed tasks older than 1 hour."""
    with _tasks_lock:
        now = time.time()
        expired = [tid for tid, t in _tasks.items()
                   if t.get("status") in ("done", "error") and now - t.get("finished_at", now) > 3600]
        for tid in expired:
            del _tasks[tid]


def _process_queue() -> None:
    """Process next task in queue. Called after each task completes."""
    global _active_task_id
    next_id = None
    with _queue_lock:
        if _task_queue:
            next_id = _task_queue.pop(0)
            _active_task_id = next_id
            # Update queue positions
            for i, tid in enumerate(_task_queue):
                with _tasks_lock:
                    if tid in _tasks:
                        _tasks[tid]["queue_pos"] = i + 1
        else:
            _active_task_id = None

    # Start task thread outside the lock to avoid holding it during I/O
    if next_id:
        t = threading.Thread(
            target=_run_task,
            args=(next_id,),
            daemon=True,
        )
        t.start()


def _run_task(task_id: str) -> None:
    """Run a task and process queue when done."""
    task_info = _tasks.get(task_id, {})
    generate_task(
        task_id,
        task_info.get("chunks_config", []),
        task_info.get("global_voice", "serena"),
        task_info.get("global_instruct", ""),
        task_info.get("speed", 1.0),
        task_info.get("fmt", "wav"),
        task_info.get("api_base", "http://localhost:8080"),
    )
    _process_queue()


def generate_task(task_id: str, chunks_config: list[dict], global_voice: str,
                  global_instruct: str, speed: float, fmt: str, api_base: str) -> None:
    """Background thread: generate TTS for each chunk."""
    wav_files = []
    total_duration = 0.0

    # Resolve effective voice/instruct for each chunk
    resolved_chunks = []
    for chunk in chunks_config:
        effective_voice = chunk.get("voice") or global_voice
        effective_instruct = chunk.get("instruct") or global_instruct
        resolved_chunks.append({
            "text": chunk.get("text", ""),
            "voice": effective_voice,
            "instruct": effective_instruct,
        })

    try:
        for i, chunk in enumerate(resolved_chunks):
            with _tasks_lock:
                _tasks[task_id]["status"] = "generating"
                _tasks[task_id]["current"] = i + 1
                _tasks[task_id]["total"] = len(resolved_chunks)
                _tasks[task_id]["progress"] = int((i / len(resolved_chunks)) * 100)

            chunk_file = str(config.AUDIO_DIR / f"{task_id}_chunk_{i:04d}.wav")

            # Resume support: skip if chunk already exists and is valid
            if os.path.exists(chunk_file) and os.path.getsize(chunk_file) > 44:
                dur = audio_utils.wav_duration(chunk_file)
                if dur > 0:
                    wav_files.append(chunk_file)
                    total_duration += dur
                    continue

            payload = json.dumps({
                "model": "tts-1",
                "input": chunk["text"],
                "voice": chunk["voice"],
                "speed": speed,
                "consent_attestation": "test",
                "spoken_disclaimer": False,
                **({"instruct": chunk["instruct"]} if chunk["instruct"] else {}),
            }, ensure_ascii=False).encode("utf-8")

            req = urllib.request.Request(
                f"{api_base}/v1/audio/speech",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=1800) as resp:
                data = resp.read()
                with open(chunk_file, "wb") as f:
                    f.write(data)

            wav_files.append(chunk_file)
            total_duration += audio_utils.wav_duration(chunk_file)

        # Concatenate all chunks
        final_wav = str(config.AUDIO_DIR / f"{task_id}.wav")
        if len(wav_files) == 1:
            os.rename(wav_files[0], final_wav)
        else:
            concat_file = str(config.AUDIO_DIR / f"{task_id}_concat.txt")
            with open(concat_file, "w") as f:
                for wf in wav_files:
                    safe_wf = wf.replace("'", "'\\''")
                    f.write(f"file '{safe_wf}'\n")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", concat_file, "-c", "copy", final_wav],
                capture_output=True, timeout=120, check=True,
            )
            for wf in wav_files:
                os.unlink(wf)
            os.unlink(concat_file)

        # Format conversion
        if fmt != "wav":
            converted = audio_utils.convert_audio(final_wav, fmt)
            if converted:
                os.unlink(final_wav)
                final_wav = converted

        # Update database
        audio_filename = os.path.basename(final_wav)
        conn = database.db_conn()
        try:
            conn.execute(
                "UPDATE history SET status='done', audio_file=?, duration=?, finished_at=? WHERE id=?",
                (audio_filename, total_duration, time.time(), task_id),
            )
            conn.commit()
        finally:
            conn.close()

        with _tasks_lock:
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["progress"] = 100
            _tasks[task_id]["audio_url"] = f"/api/audio/{audio_filename}"
            _tasks[task_id]["duration"] = total_duration
            _tasks[task_id]["finished_at"] = time.time()

    except Exception as e:
        # On error, DON'T delete chunk files — allow resume
        try:
            conn = database.db_conn()
            try:
                conn.execute("UPDATE history SET status='error', finished_at=? WHERE id=?", (time.time(), task_id))
                conn.commit()
            finally:
                conn.close()
        except:
            pass
        with _tasks_lock:
            _tasks[task_id]["status"] = "error"
            _tasks[task_id]["error"] = str(e)
            _tasks[task_id]["finished_at"] = time.time()
