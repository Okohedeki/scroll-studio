"""The agent skills (.agents/skills, mirrored for Claude Code in .claude/skills) stay complete and in step."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents" / "skills"


def front(path: Path) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    assert m, f"{path} has no front matter"
    return yaml.safe_load(m.group(1))


def skills() -> list[Path]:
    return sorted(d for d in SKILLS.iterdir() if d.is_dir())


def test_every_skill_names_itself_and_says_when_to_use_it():
    assert skills(), "no skills in .agents/skills"
    for d in skills():
        meta = front(d / "SKILL.md")
        assert meta["name"] == d.name
        assert len(meta["description"]) > 80 and "Use " in meta["description"]


def test_claude_code_sees_the_same_skills():
    mirrored = sorted(d.name for d in (ROOT / ".claude" / "skills").iterdir() if d.is_dir())
    assert mirrored == [d.name for d in skills()]
    for d in skills():
        wrapper = ROOT / ".claude" / "skills" / d.name / "SKILL.md"
        assert front(wrapper) == front(d / "SKILL.md")
        assert f".agents/skills/{d.name}/SKILL.md" in wrapper.read_text(encoding="utf-8")


def test_skills_never_send_an_agent_to_copy_an_example():
    for d in skills():
        text = (d / "SKILL.md").read_text(encoding="utf-8")
        for line in text.splitlines():
            if "create_project(" in line and "example" in line or "--example" in line:
                assert re.search(r"\b(never|not|do not|don't)\b", line, re.I), f"{d.name}: {line.strip()}"


def test_the_skills_named_in_the_entry_skill_exist():
    entry = (SKILLS / "designai" / "SKILL.md").read_text(encoding="utf-8")
    for name in set(re.findall(r"`(scroll-[a-z-]+)`", entry)) - {"designai"}:
        assert (SKILLS / name / "SKILL.md").exists(), name
