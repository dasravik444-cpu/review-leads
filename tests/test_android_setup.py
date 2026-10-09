"""The Android one-paste setup (android/setup.sh), run against stand-ins for Termux's tools: it points Termux at its
own package server, installs only proot-distro (no upgrade of all of Termux), fetches Ubuntu and checks it, installs
it once, and writes the short commands."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (shutil.which("bash") and shutil.which("sha256sum")), reason="needs bash")

UBUNTU = b"pretend this is Ubuntu"

STUBS = {
    "apt-get": 'echo "apt-get $*" >> "$LOG"',
    "termux-setup-storage": 'echo "termux-setup-storage" >> "$LOG"',
    "dpkg": '[ "$1" = --print-architecture ] && echo aarch64; exit 0',
    "curl": '''echo "curl $*" >> "$LOG"
out=""; url=""
while [ $# -gt 0 ]; do case "$1" in -o) out=$2; shift 2 ;; -C|--retry) shift 2 ;; -*) shift ;; *) url=$1; shift ;; esac; done
case "$url" in
  */SHA256SUMS) cat "$FAKE/SHA256SUMS" ;;
  *.tar.gz) cp "$FAKE/download" "$out" ;;
  */android/dns.sh) echo true ;;
  *) exit 22 ;;
esac''',
    "proot-distro": '''echo "proot-distro $*" >> "$LOG"
case "$1" in
  install) touch "$FAKE/installed" ;;
  login)
    [ -f "$FAKE/installed" ] || exit 1
    case "$4" in
      test) exit 1 ;;                                   # the robot's folder is not there yet
      bash) cat > /dev/null ;;
    esac ;;
esac
exit 0''',
}


def termux(tmp_path: Path, download: bytes = UBUNTU) -> dict:
    prefix, fake, stubs = tmp_path / "usr", tmp_path / "fake", tmp_path / "stubs"
    for d in (prefix / "bin", prefix / "tmp", prefix / "etc/termux/mirrors", prefix / "etc/apt/sources.list.d",
              tmp_path / "home", fake, stubs):
        d.mkdir(parents=True, exist_ok=True)
    (prefix / "etc/termux/mirrors/default").write_text(
        'WEIGHT=10\nMAIN="https://packages-cf.termux.dev/apt/termux-main"\n'
        'ROOT="https://packages-cf.termux.dev/apt/termux-root"\nX11="https://packages-cf.termux.dev/apt/termux-x11"\n')
    (prefix / "etc/apt/sources.list").write_text("deb https://linux.domainesia.com/applications/termux/termux-main stable main\n")
    (prefix / "etc/apt/sources.list.d/x11.list").write_text("deb https://linux.domainesia.com/applications/termux/termux-x11 x11 main\n")
    good = hashlib.sha256(UBUNTU).hexdigest()
    (fake / "SHA256SUMS").write_text(f"{'0' * 64} *ubuntu-base-24.04.4-base-arm64.tar.gz\n"
                                     f"{good} *ubuntu-base-24.04.5-base-arm64.tar.gz\n"
                                     f"{'1' * 64} *ubuntu-base-24.04.5-base-amd64.tar.gz\n")
    (fake / "download").write_bytes(download)
    for name, body in STUBS.items():
        (stubs / name).write_text("#!/bin/bash\n" + body + "\n")
        (stubs / name).chmod(0o755)
    return {**os.environ, "PREFIX": str(prefix), "HOME": str(tmp_path / "home"), "TMPDIR": str(prefix / "tmp"),
            "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}", "LOG": str(tmp_path / "log"), "FAKE": str(fake)}


def setup(env: dict) -> subprocess.CompletedProcess:
    # the way the tablet runs it: the script arrives on standard input (curl ... | bash)
    script = (ROOT / "android" / "setup.sh").read_text(encoding="utf-8")
    return subprocess.run(["bash"], input=script, env=env, capture_output=True, text=True, timeout=60)


def test_setup_installs_ubuntu_once_from_termux_own_server_and_writes_the_commands(tmp_path):
    env = termux(tmp_path)
    first = setup(env)
    assert first.returncode == 0, first.stdout + first.stderr
    assert "Done." in first.stdout
    prefix = tmp_path / "usr"
    assert (prefix / "etc/apt/sources.list").read_text() == "deb https://packages-cf.termux.dev/apt/termux-main stable main\n"
    assert (prefix / "etc/apt/sources.list.d/x11.list").read_text() == "deb https://packages-cf.termux.dev/apt/termux-x11 x11 main\n"
    log = (tmp_path / "log").read_text()
    assert "install proot-distro" in log and "upgrade" not in log           # not all of Termux
    tarball = prefix / "tmp" / "ubuntu-base-24.04.5-base-arm64.tar.gz"      # the newest for this device
    assert f"proot-distro install --name review-leads {tarball}" in log
    assert not tarball.exists()                                             # removed once installed
    for cmd in ("getkey", "settings", "check", "leads", "emails", "update"):
        text = (prefix / "bin" / cmd).read_text()
        assert f"login review-leads -- bash /root/review-leads/android/inside.sh {cmd} \"$@\"" in text
        assert os.access(prefix / "bin" / cmd, os.X_OK)
    assert "termux-wake-lock" in (prefix / "bin" / "leads").read_text()

    again = setup(env)                                                       # pasting the line again is safe
    assert again.returncode == 0, again.stdout + again.stderr
    assert (tmp_path / "log").read_text().count("proot-distro install") == 1


def test_a_damaged_ubuntu_download_is_not_installed(tmp_path):
    result = setup(termux(tmp_path, download=b"cut off halfw"))
    assert result.returncode == 1 and "damaged" in result.stdout
    assert "proot-distro install" not in (tmp_path / "log").read_text()
    assert not list((tmp_path / "usr" / "tmp").glob("*.tar.gz"))


def test_shell_scripts_parse():
    for f in [*ROOT.glob("android/*.sh"), *ROOT.glob("run_*.sh")]:
        assert subprocess.run(["bash", "-n", str(f)]).returncode == 0, f
