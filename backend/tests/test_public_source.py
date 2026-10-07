"""Exercise export/history boundaries with synthetic Git repositories only."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from public_source import export, internal_file, load_policy  # noqa: E402
from release_check import history_errors  # noqa: E402


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    files = {
        "tools/public_docs.json": json.dumps(
            {"version": 1, "documents": ["README.md", "docs/USER_GUIDE.md"]}
        ),
        "README.md": "Public guide",
        "docs/USER_GUIDE.md": "Public usage",
        "docs/HANDOFF.md": "PRIVATE_HANDOFF_SENTINEL",
        "docs/research/new-study.md": "PRIVATE_RESEARCH_SENTINEL",
        "docs/new-unreviewed-document.md": "PRIVATE_UNREVIEWED_SENTINEL",
        "AGENTS.md": "PRIVATE_AGENT_SENTINEL",
        ".private-workspace": "Private development checkout",
        "backend/app.py": "print('public code')\n",
    }
    for name, text in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(root, "add", ".")
    git(root, "commit", "-qm", "Synthetic initial tree")
    return root


def test_export_keeps_code_public_guides_and_no_private_history(repository, tmp_path):
    target = tmp_path / "public"
    export(repository, target)
    assert (target / "README.md").read_text() == "Public guide"
    assert (target / "backend/app.py").is_file()
    assert (target / "docs/USER_GUIDE.md").is_file()
    assert not (target / ".git").exists()
    assert not (target / "AGENTS.md").exists()
    assert sorted(
        p.relative_to(target).as_posix() for p in (target / "docs").rglob("*") if p.is_file()
    ) == ["docs/USER_GUIDE.md"]
    assert not any(b"PRIVATE_" in p.read_bytes() for p in target.rglob("*") if p.is_file())
    with pytest.raises(ValueError, match="empty"):
        export(repository, target)


def test_tree_deletion_does_not_hide_history_and_export_ignores_uncommitted_policy(
    repository, tmp_path
):
    (repository / "docs/HANDOFF.md").unlink()
    git(repository, "add", "-u")
    git(repository, "commit", "-qm", "Remove current internal file")
    documents = load_policy(repository)
    assert any("docs/HANDOFF.md" in e for e in history_errors(repository, documents))
    policy = repository / "tools/public_docs.json"
    value = json.loads(policy.read_text())
    value["documents"].append("docs/research/new-study.md")
    policy.write_text(json.dumps(value))
    export(repository, tmp_path / "public")
    assert not (tmp_path / "public/docs/research").exists()


def test_public_documentation_policy_defaults_to_private():
    root = Path(__file__).parents[2]
    documents = load_policy(root)
    for name in (
        "AGENTS.md",
        ".private-workspace",
        "docs/HANDOFF.md",
        "docs/PRD.md",
        "docs/ACCEPTANCE.md",
        "docs/decisions/new.md",
        "docs/new-notes.json",
        "analysis.md",
        "tools/internal/report.json",
    ):
        assert internal_file(name, documents)
    for name in (
        "README.md",
        "docs/DEPLOYMENT.md",
        "docs/images/deck.jpg",
        "docs/DEPENDENCIES.json",
        "examples/learning-notes.md",
        "backend/app.py",
    ):
        assert not internal_file(name, documents)
