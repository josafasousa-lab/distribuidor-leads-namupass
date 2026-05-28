import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger as _loguru


def gerar_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")


def make_run_logger(run_id: str):
    log_path = Path("data/logs/runs") / f"run_{run_id}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    run_logger = _loguru.bind(run_id=run_id)

    _loguru.remove()
    _loguru.add(sys.stderr, level="INFO")
    _loguru.add(str(log_path), level="DEBUG", format="{message}", colorize=False)

    return _loguru.bind(run_id=run_id)
