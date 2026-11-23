import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from new_agent import scaffold  # noqa: E402


def test_scaffolded_project_passes_its_own_tests_and_evals(tmp_path):
    out = scaffold("Invoice Triage Agent", tmp_path / "proj")
    assert (out / "invoice_triage_agent" / "agent.py").exists() and not list(out.rglob("*.tmpl"))
    assert "{{" not in "".join(p.read_text() for p in out.rglob("*") if p.is_file())      # every placeholder replaced
    t = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=out, capture_output=True, text=True, timeout=120)
    assert t.returncode == 0, t.stdout + t.stderr
    e = subprocess.run([sys.executable, "-m", "evals.run_evals"], cwd=out, capture_output=True, text=True, timeout=120)
    assert e.returncode == 0, e.stdout + e.stderr
    res = json.loads((out / "evals" / "results.json").read_text())
    assert res["policy_violations"] == 0 and res["by_tier"]["direct"] == 100.0


def test_refuses_to_overwrite_a_non_empty_directory(tmp_path):
    (tmp_path / "x").mkdir(); (tmp_path / "x" / "keep.txt").write_text("hi")
    with pytest.raises(FileExistsError):
        scaffold("Anything", tmp_path / "x")


def test_package_name_is_sanitised(tmp_path):
    assert (scaffold("2nd Line-Support!", tmp_path / "p") / "agent_2nd_line_support").is_dir()
