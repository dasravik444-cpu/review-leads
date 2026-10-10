"""The Android one-paste setup (android/setup.sh) and the getkey command (android/inside.sh), run against stand-ins for
Termux's tools. Plant Parlour runs in the same Termux, so the setup must leave what works alone (proot-distro, the
package lists), never release the shared keep-awake lock, and getkey must not take Plant Parlour's Google keys."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (shutil.which("bash") and shutil.which("sha256sum")), reason="needs bash")

UBUNTU = b"pretend this is Ubuntu"

STUBS = {
    "apt-get": '''echo "apt-get $*" >> "$LOG"
case "$*" in *"install proot-distro"*) touch "$FAKE/proot-distro" ;; esac''',
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
  list) [ -f "$FAKE/proot-distro" ] || exit 127 ;;
  install) touch "$FAKE/ubuntu" ;;
  login)
    [ -f "$FAKE/ubuntu" ] || exit 1
    if [ "$3" = --get-proot-cmd ]; then printf 'proot \\\n  --rootfs=%s/rootfs \\\n  --bind=/dev\n' "$FAKE"; exit 0; fi
    case "$4" in
      test) [ -f "$FAKE/robot" ] || exit 1 ;;           # the robot's folder
      bash) cat > /dev/null ;;
      dpkg) [ -f "$FAKE/packages" ] || exit 1 ;;        # Python, git ... in Ubuntu
      env) case "$*" in *" install "*) touch "$FAKE/packages" ;; esac ;;
      git) case "$*" in *" clone "*) touch "$FAKE/robot" ;; esac ;;
    esac ;;
esac
exit 0''',
}

MAIN_BEFORE = "deb https://linux.domainesia.com/applications/termux/termux-main stable main\n"
X11_BEFORE = "deb https://linux.domainesia.com/applications/termux/termux-x11 x11 main\n"


def termux(tmp_path: Path, download: bytes = UBUNTU, proot_distro_works: bool = False) -> dict:
    prefix, fake, stubs = tmp_path / "usr", tmp_path / "fake", tmp_path / "stubs"
    for d in (prefix / "bin", prefix / "tmp", prefix / "etc/termux/mirrors", prefix / "etc/apt/sources.list.d",
              tmp_path / "home", fake, stubs):
        d.mkdir(parents=True, exist_ok=True)
    (prefix / "etc/termux/mirrors/default").write_text(
        'WEIGHT=10\nMAIN="https://packages-cf.termux.dev/apt/termux-main"\n'
        'ROOT="https://packages-cf.termux.dev/apt/termux-root"\nX11="https://packages-cf.termux.dev/apt/termux-x11"\n')
    (prefix / "etc/apt/sources.list").write_text(MAIN_BEFORE)
    (prefix / "etc/apt/sources.list.d/x11.list").write_text(X11_BEFORE)
    good = hashlib.sha256(UBUNTU).hexdigest()
    (fake / "SHA256SUMS").write_text(f"{'0' * 64} *ubuntu-base-24.04.4-base-arm64.tar.gz\n"
                                     f"{good} *ubuntu-base-24.04.5-base-arm64.tar.gz\n"
                                     f"{'1' * 64} *ubuntu-base-24.04.5-base-amd64.tar.gz\n")
    (fake / "download").write_bytes(download)
    if proot_distro_works:
        (fake / "proot-distro").touch()
    (fake / "rootfs/root/review-leads/android").mkdir(parents=True)          # what the clone puts into Ubuntu
    shutil.copy(ROOT / "android" / "robot.sh", fake / "rootfs/root/review-leads/android/robot.sh")
    for name, body in STUBS.items():
        (stubs / name).write_text("#!/bin/bash\n" + body + "\n")
        (stubs / name).chmod(0o755)
    return {**os.environ, "PREFIX": str(prefix), "HOME": str(tmp_path / "home"), "TMPDIR": str(prefix / "tmp"),
            "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}", "LOG": str(tmp_path / "log"), "FAKE": str(fake)}


def setup(env: dict, *args: str) -> subprocess.CompletedProcess:
    # the way the tablet runs it: the script arrives on standard input (curl ... | bash -s ...)
    script = (ROOT / "android" / "setup.sh").read_text(encoding="utf-8")
    return subprocess.run(["bash", "-s", *args], input=script, env=env, capture_output=True, text=True, timeout=60)


def log(tmp_path: Path) -> str:
    return (tmp_path / "log").read_text()


def test_new_tablet_gets_proot_distro_from_termux_server_ubuntu_once_and_the_commands(tmp_path):
    env = termux(tmp_path)
    first = setup(env)
    assert first.returncode == 0, first.stdout + first.stderr
    assert "Done." in first.stdout
    prefix = tmp_path / "usr"
    assert (prefix / "etc/apt/sources.list").read_text() == "deb https://packages-cf.termux.dev/apt/termux-main stable main\n"
    assert (prefix / "etc/apt/sources.list.d/x11.list").read_text() == "deb https://packages-cf.termux.dev/apt/termux-x11 x11 main\n"
    assert "install proot-distro" in log(tmp_path) and "upgrade" not in log(tmp_path)   # not all of Termux
    tarball = prefix / "tmp" / "ubuntu-base-24.04.5-base-arm64.tar.gz"                   # the newest for this device
    assert f"proot-distro install --name review-leads {tarball}" in log(tmp_path)
    assert not tarball.exists()                                                          # removed once installed
    for cmd in ("getkey", "settings", "check", "leads", "emails", "import", "update"):
        assert os.access(prefix / "bin" / cmd, os.X_OK)
        if cmd != "update":
            assert f"login review-leads -- bash /root/review-leads/android/inside.sh {cmd} \"$@\"" in (prefix / "bin" / cmd).read_text()
    leads = (prefix / "bin" / "leads").read_text()
    assert "termux-wake-lock" in leads and "unlock" not in leads       # Plant Parlour keeps its keep-awake lock
    assert "android/setup.sh | bash -s update" in (prefix / "bin" / "update").read_text()
    robot = (prefix / "bin" / "robot").read_text()
    assert f'exec bash "{tmp_path}/fake/rootfs/root/review-leads/android/robot.sh" "$@"' in robot
    whatsapp = (prefix / "bin" / "whatsapp").read_text()
    assert f'exec bash "{tmp_path}/fake/rootfs/root/review-leads/android/whatsapp.sh" "$@"' in whatsapp
    assert not list((prefix / "bin").glob(".*.new"))

    again = setup(env, "update")                                       # what the update command runs
    assert again.returncode == 0, again.stdout + again.stderr
    assert "Updated." in again.stdout
    second = log(tmp_path).split("termux-setup-storage")[-1]
    assert log(tmp_path).count("proot-distro install") == 1
    assert "apt-get" not in second                                     # nothing installed again
    assert "git -C /root/review-leads pull --ff-only" in second


def test_with_plant_parlour_already_there_termux_is_left_as_it_is(tmp_path):
    env = termux(tmp_path, proot_distro_works=True)
    result = setup(env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "usr/etc/apt/sources.list").read_text() == MAIN_BEFORE              # its package lists
    assert (tmp_path / "usr/etc/apt/sources.list.d/x11.list").read_text() == X11_BEFORE
    assert not [line for line in log(tmp_path).splitlines() if line.startswith("apt-get")]   # no Termux packages touched


def test_a_damaged_ubuntu_download_is_not_installed(tmp_path):
    result = setup(termux(tmp_path, download=b"cut off halfw"))
    assert result.returncode == 1 and "damaged" in result.stdout
    assert "proot-distro install" not in log(tmp_path)
    assert not list((tmp_path / "usr" / "tmp").glob("*.tar.gz"))


def test_getkey_takes_only_this_business_key_and_removes_other_business_keys(tmp_path):
    robot = tmp_path / "robot"
    (robot / "android").mkdir(parents=True)
    shutil.copy(ROOT / "android" / "inside.sh", robot / "android" / "inside.sh")
    (robot / "secrets").mkdir()
    (robot / "secrets" / "README.txt").write_text("keys go here")
    downloads = tmp_path / "Download"
    downloads.mkdir()

    def key(project, email):
        return json.dumps({"type": "service_account", "project_id": project, "client_email": email}, indent=2)

    plant = key("plant-parlour-automation", "pp@plant-parlour-automation.iam.gserviceaccount.com")
    (downloads / "plant-parlour-automation-60ba43bf3ce5.json").write_text(plant)
    (downloads / "review-leads-473512-abc.json").write_text(key("review-leads-473512", "sheet-writer@review-leads-473512.iam.gserviceaccount.com"))
    (downloads / "notes.json").write_text('{"note": 1}')
    (robot / "secrets" / "plant-parlour-automation-6735c91ba5ec.json").write_text(plant)    # taken by an older getkey
    env = {**os.environ, "DOWNLOAD_DIR": str(downloads)}
    out = subprocess.run(["bash", str(robot / "android" / "inside.sh"), "getkey"], env=env, capture_output=True,
                         text=True, timeout=30).stdout
    assert sorted(p.name for p in (robot / "secrets").iterdir()) == ["README.txt", "review-leads-473512-abc.json"]
    assert "Removed plant-parlour-automation-6735c91ba5ec.json" in out
    assert "sheet-writer@review-leads-473512.iam.gserviceaccount.com" in out

    (downloads / "review-leads-473512-abc.json").unlink()
    (robot / "secrets" / "review-leads-473512-abc.json").unlink()
    out = subprocess.run(["bash", str(robot / "android" / "inside.sh"), "getkey"], env=env, capture_output=True,
                         text=True, timeout=30).stdout
    assert "No key of the Google Cloud project review-leads" in out
    assert sorted(p.name for p in (robot / "secrets").iterdir()) == ["README.txt"]


def test_shell_scripts_parse():
    for f in [*ROOT.glob("android/*.sh"), *ROOT.glob("run_*.sh")]:
        assert subprocess.run(["bash", "-n", str(f)]).returncode == 0, f


ROBOT_STUBS = {
    # "robot serve" inside Ubuntu: one at a time (else exit 75, like the real one), reports in like the real one, and
    # works until  robot off  leaves data/robot.stop for it
    "proot-distro": '''echo "proot-distro $*" >> "$LOG"
case "$*" in
  *"robot serve"*) pid=$(cat "$FAKE_HOST/serve.pid" 2>/dev/null)
                   [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && exit 75
                   echo $$ > "$FAKE_HOST/serve.pid"; echo "serve $$" >> "$LOG"
                   while [ ! -f "$FAKE_HOST/data/robot.stop" ]; do
                     printf '{"scheduler": {"heartbeat": %s.25}}' "$(date +%s)" > "$FAKE_HOST/data/robot-status.json"
                     sleep 0.2
                   done
                   rm -f "$FAKE_HOST/data/robot.stop" "$FAKE_HOST/serve.pid"
                   printf '{"scheduler": {"heartbeat": 0}}' > "$FAKE_HOST/data/robot-status.json"; exit 0 ;;
  *"robot status"*) echo "Robot: RUNNING" ;;
esac''',
    "termux-wake-lock": 'echo "wake-lock" >> "$LOG"',
    "termux-wake-unlock": 'echo "wake-UNLOCK" >> "$LOG"',
    "termux-job-scheduler": 'echo "job-scheduler $*" >> "$LOG"',
}


def robot_env(tmp_path):
    host = tmp_path / "rootfs/root/review-leads"
    (host / "android").mkdir(parents=True)
    (host / "data").mkdir()
    shutil.copy(ROOT / "android" / "robot.sh", host / "android" / "robot.sh")
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in ROBOT_STUBS.items():
        (stubs / name).write_text("#!/bin/bash\n" + body + "\n")
        (stubs / name).chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "PREFIX": str(tmp_path / "usr"), "LOG": str(tmp_path / "log"),
           "FAKE_HOST": str(host), "ROBOT_WAIT_SECONDS": "1", "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"}
    robot = lambda *a: subprocess.run(["bash", str(host / "android" / "robot.sh"), *a], env=env,  # noqa: E731
                                      capture_output=True, text=True, timeout=240)
    return host, home, env, robot


def wait_for(check, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        if check():
            return True
        time.sleep(0.1)
    return False


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_robot_switch_starts_keeps_itself_running_and_stops(tmp_path):
    host, home, env, robot = robot_env(tmp_path)
    on = robot("on")
    assert "The robot is on" in on.stdout, on.stdout + on.stderr
    pid = int((home / ".review-leads/robot.pid").read_text())
    os.kill(pid, 0)                                                          # the supervisor runs
    boot = (home / ".termux/boot/review-leads").read_text()
    assert f'exec bash "{host}/android/robot.sh" watchdog' in boot and "termux-wake-lock" in boot
    assert "job-scheduler --job-id 7711" in (tmp_path / "log").read_text()    # not Plant Parlour's 4711
    assert wait_for(lambda: (host / "serve.pid").exists())                   # the robot itself is up
    assert "wake-lock" in (tmp_path / "log").read_text()
    status = robot("status").stdout
    assert "Switch: ON\n" in status and "Robot: RUNNING" in status
    assert "already on" in robot("on").stdout and int((home / ".review-leads/robot.pid").read_text()) == pid
    robot("watchdog")                                                        # the 15-minute check: all is well
    assert (tmp_path / "log").read_text().count("serve ") == 1
    off = robot("off")
    assert "The robot is off" in off.stdout
    assert not (home / ".review-leads/robot.pid").exists() and not (host / "serve.pid").exists()
    assert wait_for(lambda: not alive(pid))
    log = (tmp_path / "log").read_text()
    assert "job-scheduler --cancel --job-id 7711" in log and "UNLOCK" not in log  # the shared lock is kept
    assert "Switch: OFF (robot on starts it)" in robot("status").stdout
    robot("watchdog")                                                        # switched off: it stays off
    assert not (home / ".review-leads/robot.pid").exists()


def test_two_supervisors_started_at_once_leave_one_and_its_number_stays(tmp_path):
    # robot on and the 15-minute check (it runs at once when it is set) can start a supervisor at the same moment
    host, home, env, robot = robot_env(tmp_path)
    procs = [subprocess.Popen(["bash", str(host / "android" / "robot.sh"), "supervise"], env=env) for _ in range(2)]
    try:
        assert wait_for(lambda: sum(p.poll() is None for p in procs) == 1)    # one has left by itself
        (left,) = [p for p in procs if p.poll() is not None]
        (kept,) = [p for p in procs if p.poll() is None]
        assert left.returncode == 0
        assert wait_for(lambda: (host / "serve.pid").exists())
        assert int((home / ".review-leads/robot.pid").read_text()) == kept.pid   # not removed by the one that left
        assert "Switch: ON\n" in robot("status").stdout
        robot("watchdog")
        time.sleep(2)
        assert (tmp_path / "log").read_text().count("serve ") == 1               # still one robot
    finally:
        robot("off")
        for p in procs:
            p.wait(30)
    assert not (home / ".review-leads/robot.pid").exists() and not (host / "serve.pid").exists()


def test_a_number_left_from_before_a_tablet_restart_does_not_count_as_running(tmp_path):
    host, home, env, robot = robot_env(tmp_path)
    other = subprocess.Popen(["sleep", "60"])                    # after a restart the old number is someone else's
    try:
        (home / ".review-leads").mkdir()
        (home / ".review-leads/robot.pid").write_text(str(other.pid))
        assert "Switch: not running" in robot("status").stdout
        on = robot("on")
        assert "The robot is on" in on.stdout and "already" not in on.stdout
        assert int((home / ".review-leads/robot.pid").read_text()) != other.pid
        assert wait_for(lambda: (host / "serve.pid").exists())
    finally:
        robot("off")
        other.kill()
        other.wait()


def test_a_robot_still_running_from_earlier_is_waited_for_not_doubled_and_robot_off_waits_for_it(tmp_path):
    # e.g. a robot whose supervisor Android closed, or one started by an older version of this script
    host, home, env, robot = robot_env(tmp_path)
    earlier = subprocess.Popen(["proot-distro", "login", "review-leads", "--", "bash", "inside.sh", "robot", "serve"],
                               env=env)
    try:
        assert wait_for(lambda: (host / "data/robot-status.json").exists() and (host / "serve.pid").exists())
        assert "Switch: ON\n" in robot("status").stdout                       # it runs, with no supervisor
        assert "The robot is on" in robot("on").stdout
        time.sleep(3)
        assert int((host / "serve.pid").read_text()) == earlier.pid           # no second robot was started
        (host / "data/robot.stop").touch()                                     # the earlier one ends ...
        earlier.wait(30)
        assert wait_for(lambda: (host / "serve.pid").exists())               # ... and the supervisor starts one
        assert int((host / "serve.pid").read_text()) != earlier.pid
        sup = int((home / ".review-leads/robot.pid").read_text())
        assert alive(sup)
        (home / ".review-leads/robot.pid").unlink()                            # as an older script's supervisor did
        off = robot("off")                                                     # still waits for the robot to stop
        assert "Stopping" in off.stdout and "The robot is off" in off.stdout
        assert not (host / "serve.pid").exists()
        assert wait_for(lambda: not alive(sup))
    finally:
        if earlier.poll() is None:
            earlier.kill()
        robot("off")
