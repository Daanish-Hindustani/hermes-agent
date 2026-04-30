#!/usr/bin/env bash
# Set up local Docker images for the Hermes protein-design plugin.
#
# This script does not install Hermes. It is safe to call from `hermes setup`
# after the Python environment already exists.

set -euo pipefail

FOUNDRY_IMAGE_DEFAULT="rosettacommons/foundry:latest"
ESMFOLD_IMAGE_DEFAULT="hermes-esmfold:latest"

FOUNDRY_IMAGE="${HERMES_PROTEIN_FOUNDRY_IMAGE:-$FOUNDRY_IMAGE_DEFAULT}"
ESMFOLD_IMAGE="${HERMES_PROTEIN_ESMFOLD_IMAGE:-$ESMFOLD_IMAGE_DEFAULT}"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
SKIP_FOUNDRY=0
SKIP_ESMFOLD_BUILD=0
SKIP_SMOKE_TESTS=0

usage() {
  cat <<'EOF'
Usage: scripts/setup_protein_design_local.sh [options]

Options:
  --skip-foundry        Do not pull/check the Foundry image for RFD3/ProteinMPNN
  --skip-esmfold-build  Do not build/check the local ESMFold image
  --skip-smoke-tests    Do not run GPU/tool smoke tests after pull/build
  -h, --help            Show this help

Environment overrides:
  HERMES_HOME                            Default: ~/.hermes
  HERMES_PROTEIN_FOUNDRY_IMAGE           Default: rosettacommons/foundry:latest
  HERMES_PROTEIN_ESMFOLD_IMAGE           Default: hermes-esmfold:latest
  HERMES_PROTEIN_WORKSPACE_ROOT          Default: $HERMES_HOME/protein-design
  HERMES_PROTEIN_DEFAULT_TIMEOUT_SECONDS Default: 7200
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-foundry) SKIP_FOUNDRY=1 ;;
    --skip-esmfold-build) SKIP_ESMFOLD_BUILD=1 ;;
    --skip-smoke-tests) SKIP_SMOKE_TESTS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log() {
  printf '\n==> %s\n' "$*"
}

warn() {
  printf '\nWARN: %s\n' "$*" >&2
}

docker_cmd() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo docker "$@"
  else
    docker "$@"
  fi
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required for local protein-design compute." >&2
    echo "Install Docker and NVIDIA Container Toolkit, then rerun this script." >&2
    exit 1
  fi
  docker_cmd version >/dev/null
}

write_config() {
  log "Writing protein-design local compute config"
  mkdir -p "$HERMES_HOME_DIR"

  local config_python="python3"
  if [[ -x "$REPO_ROOT/venv/bin/python" ]]; then
    config_python="$REPO_ROOT/venv/bin/python"
  elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    config_python="$REPO_ROOT/.venv/bin/python"
  fi

  HERMES_HOME="$HERMES_HOME_DIR" "$config_python" - <<'PY'
import os
from pathlib import Path

import yaml

home = Path(os.environ["HERMES_HOME"]).expanduser()
config_path = home / "config.yaml"
config = {}
if config_path.exists():
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

plugins = config.setdefault("plugins", {})
enabled = plugins.setdefault("enabled", [])
if "protein-design" not in enabled:
    enabled.append("protein-design")

protein = config.setdefault("protein_design", {})
protein["foundry_image"] = os.environ.get("HERMES_PROTEIN_FOUNDRY_IMAGE", "rosettacommons/foundry:latest")
protein["esmfold_image"] = os.environ.get("HERMES_PROTEIN_ESMFOLD_IMAGE", "hermes-esmfold:latest")
protein.setdefault("workspace_root", os.environ.get("HERMES_PROTEIN_WORKSPACE_ROOT", str(home / "protein-design")))
protein.setdefault("default_timeout_seconds", int(os.environ.get("HERMES_PROTEIN_DEFAULT_TIMEOUT_SECONDS", "7200")))

config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
print(config_path)
PY
}

check_gpu_runtime() {
  if [[ "$SKIP_SMOKE_TESTS" == "1" ]]; then
    return
  fi

  log "Checking Docker GPU runtime"
  if ! docker_cmd run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi; then
    warn "Docker GPU check failed. HTTPS/API protein tools will still work, but RFD3/ProteinMPNN/ESMFold need Docker GPU access for practical local compute."
  fi
}

setup_foundry() {
  if [[ "$SKIP_FOUNDRY" == "1" ]]; then
    log "Skipping Foundry image"
    return
  fi

  log "Pulling Foundry image: $FOUNDRY_IMAGE"
  docker_cmd pull "$FOUNDRY_IMAGE"

  if [[ "$SKIP_SMOKE_TESTS" == "1" ]]; then
    return
  fi

  log "Checking Foundry commands"
  docker_cmd run --rm --gpus all "$FOUNDRY_IMAGE" rfd3 --help >/tmp/hermes-rfd3-help.txt
  docker_cmd run --rm --gpus all "$FOUNDRY_IMAGE" mpnn --help >/tmp/hermes-mpnn-help.txt || \
    warn "Foundry mpnn --help failed. The image may still work depending on its entrypoint; inspect /tmp/hermes-mpnn-help.txt."
}

setup_esmfold() {
  if [[ "$SKIP_ESMFOLD_BUILD" == "1" ]]; then
    log "Skipping ESMFold image build"
    return
  fi

  log "Building ESMFold image: $ESMFOLD_IMAGE"
  docker_cmd build \
    -t "$ESMFOLD_IMAGE" \
    -f plugins/protein-design/docker/esmfold.Dockerfile \
    plugins/protein-design/docker

  if [[ "$SKIP_SMOKE_TESTS" == "1" ]]; then
    return
  fi

  log "Checking ESMFold command"
  docker_cmd run --rm --gpus all "$ESMFOLD_IMAGE" esm-fold --help >/tmp/hermes-esmfold-help.txt
}

require_docker
write_config
check_gpu_runtime
setup_foundry
setup_esmfold

cat <<EOF

Protein-design local compute setup complete.

Configured images:
  Foundry: $FOUNDRY_IMAGE
  ESMFold: $ESMFOLD_IMAGE

Config:
  $HERMES_HOME_DIR/config.yaml

EOF
