import logging
import os
import sys
from pathlib import Path


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    audit_log_path = os.getenv("POLICY_AUDIT_LOG_PATH", "").strip()
    pal = logging.getLogger("app.policy.audit")
    pal.setLevel(logging.INFO)
    if audit_log_path:
        p = Path(audit_log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(p), encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(message)s"))
        pal.addHandler(fh)
        pal.propagate = False
