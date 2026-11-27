"""Exercise the actual local shell launcher with fake tools and synthetic settings only."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT_ENV = "GEMINI_API_KEY=synthetic-private-key\nENCRYPTION_KEY=synthetic-private-encryption\n"
SCRIPT = Path(__file__).resolve().parents[3] / "scripts/demo-local.sh"


def launcher(tmp_path, link):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "apps/web").mkdir(parents=True)
    (tmp_path / "bin").mkdir()
    shutil.copyfile(SCRIPT, tmp_path / "scripts/demo-local.sh")
    root = tmp_path / ".env"
    root.write_text(ROOT_ENV)
    target = tmp_path / "apps/web/.env.local"
    if link == "symlink":
        target.symlink_to("../../.env")
    elif link == "hardlink":
        os.link(root, target)
    elif link == "regular":
        target.write_text("old\n")
    tool = tmp_path / "bin/npx"
    tool.write_text("""#!/bin/sh
case "$*" in
  *supabase*status*)
    echo 'DB_URL="postgresql://synthetic"'
    echo 'API_URL="http://localhost:54321"'
    echo 'PUBLISHABLE_KEY="synthetic-public"'
    echo 'SECRET_KEY="synthetic-server-key"'
    echo 'JWT_SECRET="synthetic-jwt"'
    echo 'MAILPIT_URL="http://localhost:54324"'
    ;;
  *pnpm*build*) echo 'BUILD';;
  *pnpm*start*) echo 'START';;
  *) exit 1;;
esac
""")
    tool.chmod(0o700)
    return root, target


def run(tmp_path):
    return subprocess.run(
        ["bash", str(tmp_path / "scripts/demo-local.sh"), "web"],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}", "DEMO_MODE": "real"},
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize("link", ["symlink", "hardlink", "regular", "missing"])
def test_s47_t01_t02_t04_web_config_cannot_overwrite_backend(tmp_path, link):
    root, target = launcher(tmp_path, link)
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert root.read_text() == ROOT_ENV
    assert not target.is_symlink()
    assert target.stat().st_ino != root.stat().st_ino
    assert target.stat().st_mode & 0o777 == 0o600
    assert "synthetic-public" in target.read_text()
    assert "synthetic-private" not in target.read_text() + result.stdout + result.stderr
    assert "synthetic-server-key" not in target.read_text()
    assert "BUILD" in result.stdout and "START" in result.stdout
    assert not list(target.parent.glob(".env.local.tmp.*"))


def test_s47_t03_failed_replace_preserves_configuration(tmp_path):
    root, target = launcher(tmp_path, "regular")
    mv = tmp_path / "bin/mv"
    mv.write_text("#!/bin/sh\nexit 1\n")
    mv.chmod(0o700)
    result = run(tmp_path)
    assert result.returncode != 0
    assert root.read_text() == ROOT_ENV and target.read_text() == "old\n"
    assert not list(target.parent.glob(".env.local.tmp.*"))


@pytest.mark.parametrize("symlink", [False, True])
def test_s47_t05_directory_destination_is_rejected(tmp_path, symlink):
    root, target = launcher(tmp_path, "missing")
    if symlink:
        actual = tmp_path / "elsewhere"
        actual.mkdir()
        target.symlink_to(actual, target_is_directory=True)
    else:
        target.mkdir()
        actual = target
    result = run(tmp_path)
    assert result.returncode != 0
    assert root.read_text() == ROOT_ENV
    assert not list(actual.iterdir())
    assert "BUILD" not in result.stdout and "START" not in result.stdout
    assert not list(target.parent.glob(".env.local.tmp.*"))
