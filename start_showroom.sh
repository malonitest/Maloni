#!/usr/bin/env bash
set -euo pipefail
root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$root_dir"
robot_model=maloni120
previous_arg=''
for arg in "$@"; do
    if [[ "$previous_arg" == --robot ]]; then robot_model="$arg"; fi
    if [[ "$arg" == --robot=* ]]; then robot_model="${arg#--robot=}"; fi
    previous_arg="$arg"
done
native_library="$root_dir/build/maloni_sim/libmaloni_physics.so"
if [[ "$robot_model" == g1 ]] && [[ ! -f "$native_library" || "$root_dir/maloni_sim/native/engine.cpp" -nt "$native_library" || "$root_dir/maloni_sim/native/CMakeLists.txt" -nt "$native_library" ]]; then
    bash "$root_dir/scripts/build_maloni_sim.sh"
fi
exec "$root_dir/.venv/bin/python" -m chery_showroom.runtime "$@"
