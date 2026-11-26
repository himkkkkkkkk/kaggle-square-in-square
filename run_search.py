"""Run search/algorithm.py with only search/ writable and networking disabled."""

from __future__ import annotations

import argparse
import os
import resource
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEARCH = ROOT / "search"
MEMORY_LIMIT_MB = int(os.environ.get("SEARCH_MEMORY_MB", "2048"))


def limit_memory():
    limit = MEMORY_LIMIT_MB * 1024**2
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


MOUNT_SCRIPT = r"""
set -eu
home=$1
search=$2
root=$3
mount_bin=$4
shift 4
"$mount_bin" --make-rprivate /
"$mount_bin" --bind "$home" "$home"
"$mount_bin" -o remount,bind,ro "$home"
for private_file in "$root/record.json" "$root/aim.json"; do
  "$mount_bin" --bind /dev/null "$private_file"
  "$mount_bin" -o remount,bind,ro "$private_file"
done
"$mount_bin" --bind "$search" "$search"
"$mount_bin" -o remount,bind,rw "$search"
"$mount_bin" -t tmpfs tmpfs /tmp
cd "$search"
exec "$@"
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arguments", nargs=argparse.REMAINDER, help="arguments passed to search/algorithm.py")
    arguments = parser.parse_args()
    env = os.environ.copy()
    env.pop("DEEPSEEK_API_KEY", None)
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    env["MALLOC_ARENA_MAX"] = "2"
    uid = os.environ.get("SEARCH_UNPRIVILEGED_UID")
    if uid is not None:
        def demote():
            limit_memory()
            os.setgroups([])
            os.setgid(int(uid))
            os.setuid(int(uid))
        env["HOME"] = "/tmp"
        result = subprocess.run(
            [sys.executable, str(SEARCH / "algorithm.py"), *arguments.arguments],
            cwd=SEARCH,
            env=env,
            preexec_fn=demote,
        )
        raise SystemExit(result.returncode)

    unshare = shutil.which("unshare")
    mount = "/run/current-system/sw/bin/mount" if Path("/run/current-system/sw/bin/mount").exists() else shutil.which("mount")
    if not unshare or not mount:
        raise SystemExit("sandbox requires Linux util-linux unshare and mount")
    home = Path.home().resolve()
    try:
        SEARCH.relative_to(home)
    except ValueError:
        raise SystemExit(f"repository must be inside {home} for this sandbox") from None

    command = [
        unshare,
        "--user",
        "--map-root-user",
        "--mount",
        "--net",
        "--pid",
        "--fork",
        "--mount-proc",
        "sh",
        "-c",
        MOUNT_SCRIPT,
        "sh",
        str(home),
        str(SEARCH),
        str(ROOT),
        mount,
        sys.executable,
        str(SEARCH / "algorithm.py"),
        *arguments.arguments,
    ]
    raise SystemExit(subprocess.run(command, env=env, preexec_fn=limit_memory).returncode)


if __name__ == "__main__":
    main()
