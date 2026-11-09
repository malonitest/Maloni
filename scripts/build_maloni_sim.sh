#!/usr/bin/env bash
set -euo pipefail
root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cmake -S "$root_dir/maloni_sim/native" -B "$root_dir/build/maloni_sim" -DCMAKE_BUILD_TYPE=Release
cmake --build "$root_dir/build/maloni_sim" --parallel 2
