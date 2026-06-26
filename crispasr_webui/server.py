#!/usr/bin/env python3
"""CrispASR TTS Web UI v3 — Server entry point."""

import argparse
import os
import uuid

from . import config
from . import database
from .handlers import TTSHandler, ThreadedHTTPServer


def main():
    parser = argparse.ArgumentParser(description="CrispASR TTS Web UI v3")
    parser.add_argument("--listen", default="0.0.0.0", help="Listen address")
    parser.add_argument("--port", type=int, default=8888, help="Listen port")
    parser.add_argument("--api", default="http://localhost:8080", help="CrispASR API base URL")
    parser.add_argument("--password", default="", help="Login password (required)")
    parser.add_argument("--data-dir", default="", help="Data directory")
    args = parser.parse_args()

    args.password = args.password or os.environ.get("TTS_PASSWORD", "")

    if not args.password:
        print("⚠️  No password set! Use --password or TTS_PASSWORD env var")
        args.password = uuid.uuid4().hex[:8]
        print(f"   Auto-generated temporary password: {args.password}")

    if args.data_dir:
        config.set_data_dir(args.data_dir)

    if not config.JWT_SECRET:
        # C4: Use random secret independent of password
        config.set_jwt_secret(uuid.uuid4().hex + uuid.uuid4().hex)

    database.init_db()

    TTSHandler.api_base = args.api
    TTSHandler.password = args.password

    server = ThreadedHTTPServer((args.listen, args.port), TTSHandler)
    print(f"🎙️  CrispASR TTS Web UI v3")
    print(f"   URL:  http://{args.listen}:{args.port}")
    print(f"   API:  {args.api}")
    print(f"   Data: {config.DATA_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
        server.server_close()


if __name__ == "__main__":
    main()
