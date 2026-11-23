"""Scaffold a new agent project from templates/agent-skeleton.

    python scripts/new_agent.py "Invoice Triage Agent" --out ./invoice-triage-agent
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "agent-skeleton"


def scaffold(project_name: str, out: Path) -> Path:
    pkg = re.sub(r"[^a-z0-9]+", "_", project_name.lower()).strip("_") or "agent"
    if pkg[0].isdigit():
        pkg = "agent_" + pkg
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} exists and is not empty")
    for src in TEMPLATE.rglob("*.tmpl"):
        rel = src.relative_to(TEMPLATE).as_posix().replace("__PKG__", pkg)[: -len(".tmpl")]
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text().replace("{{PROJECT_NAME}}", project_name).replace("{{PKG}}", pkg))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name"); ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    out = a.out or Path(re.sub(r"[^a-z0-9]+", "-", a.name.lower()).strip("-"))
    try:
        print("created", scaffold(a.name, out))
    except FileExistsError as e:
        sys.exit(str(e))
