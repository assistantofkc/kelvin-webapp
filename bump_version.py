#!/usr/bin/env python3
"""Auto-bump Cooking Ideas version number in index.html"""

import re
import sys
import subprocess
from pathlib import Path

TEMPLATE = Path(__file__).parent / "templates/cooking/index.html"
VERSION_RE = re.compile(r'(<span[^>]*opacity:0\.5[^>]*>)v(\d+)\.(\d+)(</span>)')


def bump(part: str = "patch"):
    html = TEMPLATE.read_text(encoding="utf-8")
    m = VERSION_RE.search(html)
    if not m:
        print("❌ Version span not found!")
        sys.exit(1)

    major, patch = int(m.group(2)), int(m.group(3))
    if part == "major":
        major += 1
        patch = 0
    elif part == "minor":
        patch += 1  # treat as minor bump
    else:
        patch += 1

    new_ver = f"v{major}.{patch}"
    new_html = html[:m.start()] + f"{m.group(1)}{new_ver}{m.group(4)}" + html[m.end():]
    TEMPLATE.write_text(new_html, encoding="utf-8")
    print(f"✅ Version bumped: v{m.group(2)}.{m.group(3)} → {new_ver}")
    return new_ver


def git_push():
    repo = TEMPLATE.parents[1]  # webapp/
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Auto bump version"], cwd=repo, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=True)
    print("✅ Git pushed")


def reload_pa():
    subprocess.run([
        "curl", "-s", "-X", "POST",
        "https://www.pythonanywhere.com/api/v0/user/assistantofkc/webapps/assistantofkc.pythonanywhere.com/reload/",
        "-H", "Authorization: Token 1950ca7126f9b8389c82d24327dbc7fc020ed8e2"
    ], check=True)
    print("✅ PythonAnywhere reloaded")


if __name__ == "__main__":
    part = sys.argv[1] if len(sys.argv) > 1 else "patch"
    bump(part)
    git_push()
    reload_pa()
