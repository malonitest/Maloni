#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ort_dir="$script_dir/../unitree_rl_lab/deploy/thirdparty/onnxruntime-linux-x64-1.22.0"
g++ -std=c++17 -O1 "$script_dir/policy_runner.cpp" -I "$ort_dir/include" -L "$ort_dir/lib" "-Wl,-rpath,$ort_dir/lib" -l:libonnxruntime.so.1.22.0 -o "$script_dir/policy_runner"
