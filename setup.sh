#!/usr/bin/env bash
# One-time setup for a fresh clone of this repo on a new machine.
#
# What this actually needs to do (verified 2026-07-21, not assumed):
#   - The cabt simulator engine (libcg.so) ships INSIDE the
#     `kaggle-environments` pip package, Linux x86_64 only. Every
#     *_docker.sh script in this repo already runs `pip install
#     kaggle-environments` fresh inside its own ephemeral container, so
#     there is no binary artifact to copy in by hand — libcg_docker.so
#     at the repo root is a leftover, unused by any script (grepped),
#     and stays gitignored on purpose.
#   - What a fresh machine actually needs: Docker installed and running,
#     the base image pulled once (so the first real eval isn't also
#     eating a slow first-pull), and one real container boot that proves
#     kaggle-environments installs AND the "cabt" engine actually loads
#     (dlopen failures are exactly the kind of thing that's silent until
#     you try to use it) — plus the champion snapshot initialized so
#     --opponent snapshot works without a separate manual step.
#
# Docker install (added 2026-07-21, Linux only): on Linux, a missing
# Docker gets installed automatically via the distro's own signed package
# repo (apt/dnf/yum) following Docker's official steps, falling back to
# Docker's official convenience script (downloaded to a file and reviewed
# before execution, never blind `curl | sh`) for anything else. This
# needs root — via sudo if you're not already root — and will say so
# BEFORE asking for a password, never silently. macOS/other platforms
# still just get a link: Docker Desktop is a GUI app with its own
# licensing/permission flow, not something worth silently installing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
IMAGE="python:3.11-slim-bookworm"
DOCKER_CMD="docker"  # may become "sudo docker" for this run — see below

echo "== 1/4: Docker =="

_as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "ERROR: this step needs root and 'sudo' isn't available. Re-run as root, or install sudo first."
    exit 1
  fi
}

_install_docker_linux() {
  echo "Docker not found. Installing (Linux, needs root — you may be asked for a password)..."

  if command -v apt-get >/dev/null 2>&1; then
    echo "-- apt-based system: installing via Docker's official apt repo --"
    # Docker publishes SEPARATE apt repos for Ubuntu vs Debian — hardcoding
    # one breaks the other (Ubuntu codenames don't exist in Debian's repo
    # and vice versa). Distinguish via /etc/os-release, default to Debian's
    # repo for unlisted apt-based distros unless they identify as Ubuntu-like.
    . /etc/os-release
    if [ "${ID:-}" = "ubuntu" ] || printf '%s' "${ID_LIKE:-}" | grep -qw ubuntu; then
      DOCKER_APT_DISTRO="ubuntu"
    else
      DOCKER_APT_DISTRO="debian"
    fi
    DOCKER_APT_CODENAME="${UBUNTU_CODENAME:-$VERSION_CODENAME}"
    _as_root apt-get update -y
    _as_root apt-get install -y ca-certificates curl gnupg
    _as_root install -m 0755 -d /etc/apt/keyrings
    # Docker's apt signing key — long-lived infra, unlike a per-script
    # checksum, so pinning the fetch URL (not a content hash that would
    # go stale) is the right level of trust here.
    curl -fsSL "https://download.docker.com/linux/$DOCKER_APT_DISTRO/gpg" | _as_root gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    _as_root chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$DOCKER_APT_DISTRO $DOCKER_APT_CODENAME stable" \
      | _as_root tee /etc/apt/sources.list.d/docker.list >/dev/null
    _as_root apt-get update -y
    _as_root apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  elif command -v dnf >/dev/null 2>&1; then
    echo "-- dnf-based system: installing via Docker's official dnf repo --"
    # Same split as apt: Fedora gets Docker's fedora repo; RHEL/CentOS
    # Stream/Rocky/Alma (all dnf-based) use Docker's centos repo path,
    # per Docker's own install docs for RHEL-family distros.
    . /etc/os-release
    if [ "${ID:-}" = "fedora" ]; then
      DOCKER_DNF_REPO="https://download.docker.com/linux/fedora/docker-ce.repo"
    else
      DOCKER_DNF_REPO="https://download.docker.com/linux/centos/docker-ce.repo"
    fi
    _as_root dnf -y install dnf-plugins-core
    # Fedora 41+ ships DNF5, which replaced config-manager's flag syntax
    # with a subcommand one — `--add-repo <url>` is gone, it's now
    # `addrepo --from-repofile=<url>`. RHEL-family (Rocky/Alma/CentOS
    # Stream) is still classic DNF4 as of this writing. Verified against
    # real containers (fedora:41 = dnf5, rockylinux:9 = dnf 4.14) — the
    # old syntax hard-fails with "Unknown argument --add-repo" on DNF5,
    # it doesn't just warn, so this has to branch, not just try one form.
    if dnf --version 2>/dev/null | head -1 | grep -q '^dnf5'; then
      _as_root dnf config-manager addrepo --from-repofile="$DOCKER_DNF_REPO"
    else
      _as_root dnf config-manager --add-repo "$DOCKER_DNF_REPO"
    fi
    _as_root dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  elif command -v yum >/dev/null 2>&1; then
    echo "-- yum-based system: installing via Docker's official yum repo --"
    _as_root yum install -y yum-utils
    _as_root yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    _as_root yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  else
    echo "-- no recognized package manager (apt/dnf/yum) — falling back to Docker's official installer --"
    echo "   Downloading to a file first (never piping an unreviewed remote script to a shell)."
    DOCKER_INSTALL_SH="$(mktemp /tmp/get-docker.XXXXXX.sh)"
    curl -fsSL https://get.docker.com -o "$DOCKER_INSTALL_SH"
    echo "   Downloaded to $DOCKER_INSTALL_SH ($(wc -l < "$DOCKER_INSTALL_SH") lines) — running it now."
    _as_root sh "$DOCKER_INSTALL_SH"
    rm -f "$DOCKER_INSTALL_SH"
  fi

  # Start + enable the daemon if this is a systemd system; harmless no-op
  # (non-fatal) if it's a container/minimal environment without systemd.
  if command -v systemctl >/dev/null 2>&1; then
    _as_root systemctl enable --now docker || true
  fi

  # Let the current user run docker without sudo — but that only takes
  # effect on a NEW login session, not this one, so we don't pretend
  # it's usable yet.
  if [ "$(id -u)" -ne 0 ] && command -v usermod >/dev/null 2>&1; then
    _as_root usermod -aG docker "$(id -un)" || true
    echo "Added $(id -un) to the 'docker' group — log out and back in (or run 'newgrp docker')"
    echo "for docker to work WITHOUT sudo in your normal shell. Using sudo for the rest of this run."
    DOCKER_CMD="sudo docker"
  fi

  echo "OK: Docker installed."
}

OS="$(uname -s)"
if ! command -v docker >/dev/null 2>&1; then
  if [ "$OS" = "Linux" ]; then
    _install_docker_linux
  elif [ "$OS" = "Darwin" ]; then
    echo "ERROR: docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
  else
    echo "ERROR: docker not found and I don't know how to install it on '$OS'."
    echo "       Install Docker manually: https://docs.docker.com/engine/install/"
    exit 1
  fi
fi

if ! $DOCKER_CMD info >/dev/null 2>&1; then
  if [ "$OS" = "Linux" ] && command -v systemctl >/dev/null 2>&1; then
    echo "Docker installed but daemon not running — starting it..."
    _as_root systemctl start docker || true
  fi
  if ! $DOCKER_CMD info >/dev/null 2>&1; then
    if [ "$OS" = "Darwin" ]; then
      echo "ERROR: docker is installed but not running. Start Docker Desktop and re-run this script."
    else
      echo "ERROR: docker is installed but the daemon still isn't reachable (even via sudo)."
      echo "       Check 'systemctl status docker' / 'journalctl -u docker' for why it won't start."
    fi
    exit 1
  fi
fi
echo "OK: Docker is installed and running (using: $DOCKER_CMD)."

echo ""
echo "== 2/4: pull the eval base image (one-time, ~100MB) =="
$DOCKER_CMD pull --platform linux/amd64 "$IMAGE"

echo ""
echo "== 3/4: verify the simulator actually loads (not just that Docker works) =="
$DOCKER_CMD run --rm --platform linux/amd64 "$IMAGE" bash -c '
  set -e
  pip install -q "kaggle-environments>=1.14.10"
  python3 -c "
from kaggle_environments import make
env = make(\"cabt\", debug=False)
print(\"OK: cabt engine loaded (libcg.so resolved correctly)\")
"
'

echo ""
echo "== 4/4: initialize the champion snapshot for protocol-v2 eval =="
# `[ -d .git ]` breaks in a git worktree (.git is a FILE there, pointing at
# the real gitdir, not a directory) — use git itself to ask, not a path guess.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ./eval/set_champion.sh HEAD
else
  echo "SKIP: not a git checkout, can't pin a champion commit — run"
  echo "      ./eval/set_champion.sh <commit> manually once you have one."
fi

chmod +x ./*.sh ./eval/*.sh 2>/dev/null || true

echo ""
echo "Setup complete. Try:"
if [ "$DOCKER_CMD" = "sudo docker" ]; then
  echo "  (you're in the 'docker' group now but this shell predates that —"
  echo "   log out/in or 'newgrp docker' before running these WITHOUT sudo)"
fi
echo "  ./eval/run_batch_docker.sh --games 10 --opponent random   # smoke test"
echo "  ./eval/run_train_eval.sh                                   # frozen 50-game protocol"
echo "  ./package_submission.sh                                    # build submission.tar.gz"
echo ""
echo "Note: this repo's knowledge/ directory is a git submodule (the PTCG"
echo "strategy brain, its own repo). If knowledge/ looks empty, run:"
echo "  git submodule update --init --recursive"
