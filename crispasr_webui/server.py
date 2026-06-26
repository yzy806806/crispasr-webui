#!/usr/bin/env python3
"""CrispASR TTS Web UI v0.9 — Server entry point."""

import argparse
import os
import uuid

from . import config
from . import database
from .handlers import TTSHandler, ThreadedHTTPServer


def main():
    parser = argparse.ArgumentParser(description="CrispASR TTS Web UI v0.9")
    parser.add_argument("--listen", default="0.0.0.0", help="Listen address")
    parser.add_argument("--port", type=int, default=8888, help="Listen port")
    parser.add_argument("--api", default="http://localhost:8080", help="CrispASR API base URL")
    parser.add_argument("--password", default="", help="Login password (required)")
    parser.add_argument("--data-dir", default="", help="Data directory (history, audio, uploads)")
    parser.add_argument("--crispasr-dir", default="", help="CrispASR installation directory")
    args = parser.parse_args()

    # Password: CLI arg > env var > auto-generate
    args.password = args.password or os.environ.get("TTS_PASSWORD", "")
    if not args.password:
        print("⚠️  No password set! Use --password or TTS_PASSWORD env var")
        args.password = uuid.uuid4().hex[:8]
        print(f"   Auto-generated temporary password: {args.password}")

    # Paths
    if args.data_dir:
        config.set_data_dir(args.data_dir)
    if args.crispasr_dir:
        config.set_crispasr_dir(args.crispasr_dir)

    if not config.JWT_SECRET:
        config.set_jwt_secret(uuid.uuid4().hex + uuid.uuid4().hex)

    database.init_db()

    TTSHandler.api_base = args.api
    TTSHandler.password = args.password

    server = ThreadedHTTPServer((args.listen, args.port), TTSHandler)
    print(f"🎙️  CrispASR TTS Web UI v0.9")
    print(f"   URL:       http://{args.listen}:{args.port}")
    print(f"   API:       {args.api}")
    print(f"   Data:      {config.DATA_DIR}")
    print(f"   CrispASR:  {config.CRISPASR_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
        server.server_close()


if __name__ == "__main__":
    main()
