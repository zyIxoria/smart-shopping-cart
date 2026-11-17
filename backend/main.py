"""Điểm chạy Backend:  python -m backend.main"""
from __future__ import annotations

import logging
import os

import uvicorn

from backend.api.app import create_app
from backend.config import Settings


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = Settings()
    uvicorn.run(create_app(s), host=s.host, port=s.port, log_level="warning")


if __name__ == "__main__":
    main()
