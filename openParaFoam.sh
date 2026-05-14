#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  ./openParaFoam.sh [caseDir]
  ./openParaFoam.sh --server [caseDir] [port]

Examples:
  ./openParaFoam.sh RakinVortex2
  ./openParaFoam.sh --server RakinVortex2 11111

Notes:
  - The script creates <caseName>.foam in the case directory.
  - GUI mode uses paraFoam when available, otherwise paraview.
  - Server mode starts pvserver for connecting from ParaView on another machine.
EOF
}

load_openfoam_env() {
    if command -v paraFoam >/dev/null 2>&1; then
        return 0
    fi

    local candidates=()

    if [[ -n "${WM_PROJECT_DIR:-}" ]]; then
        candidates+=("$WM_PROJECT_DIR/etc/bashrc")
    fi

    candidates+=(
        "$HOME/OpenFOAM/OpenFOAM-v2112/etc/bashrc"
        "$HOME/OpenFOAM/OpenFOAM-2112/etc/bashrc"
        "/usr/lib/openfoam/openfoam2112/etc/bashrc"
        "/opt/openfoam2112/etc/bashrc"
        "/opt/OpenFOAM/OpenFOAM-v2112/etc/bashrc"
    )

    local bashrc
    for bashrc in "${candidates[@]}"; do
        if [[ -f "$bashrc" ]]; then
            # shellcheck disable=SC1090
            source "$bashrc"
            if command -v paraFoam >/dev/null 2>&1; then
                return 0
            fi
        fi
    done
}

make_foam_file() {
    local case_dir=$1
    local case_name
    case_name=$(basename "$case_dir")
    touch "$case_dir/$case_name.foam"
    printf '%s\n' "$case_dir/$case_name.foam"
}

find_pvserver() {
    local candidates=()

    if [[ -n "${PVSERVER_BIN:-}" ]]; then
        candidates+=("$PVSERVER_BIN")
    fi

    candidates+=(
        "$HOME/apps/paraview-5.13.1-egl/bin/pvserver"
    )

    local pvserver_bin
    for pvserver_bin in "${candidates[@]}"; do
        if [[ -x "$pvserver_bin" ]]; then
            printf '%s\n' "$pvserver_bin"
            return 0
        fi
    done

    if command -v pvserver >/dev/null 2>&1; then
        command -v pvserver
        return 0
    fi

    return 1
}

mode="gui"
case_dir="."
port="11111"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        --server)
            mode="server"
            shift
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
        *)
            case_dir=$1
            shift
            if [[ "$mode" == "server" && $# -gt 0 && "$1" =~ ^[0-9]+$ ]]; then
                port=$1
                shift
            fi
            ;;
    esac
done

case_dir=${case_dir%/}
if [[ ! -d "$case_dir" ]]; then
    echo "Case directory not found: $case_dir" >&2
    exit 1
fi

if [[ ! -d "$case_dir/system" || ! -d "$case_dir/constant" ]]; then
    echo "This does not look like an OpenFOAM case: $case_dir" >&2
    echo "Expected to find system/ and constant/." >&2
    exit 1
fi

load_openfoam_env
foam_file=$(make_foam_file "$case_dir")

if [[ "$mode" == "server" ]]; then
    if ! pvserver_bin=$(find_pvserver); then
        echo "pvserver was not found in PATH." >&2
        exit 1
    fi

    pvserver_version=$("$pvserver_bin" --version 2>&1 | tail -n 1 || true)
    host_ip=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
    echo "Created: $foam_file"
    echo "Server: ${pvserver_version:-pvserver version unknown}"
    echo "Binary: $pvserver_bin"
    echo "Use the same ParaView version on the client machine."
    echo "Starting pvserver on port $port ..."
    echo "Connect from ParaView with host=${host_ip:-<VM-IP>} port=$port"
    exec "$pvserver_bin" --server-port="$port"
fi

if command -v paraFoam >/dev/null 2>&1; then
    exec paraFoam -case "$case_dir"
fi

if command -v paraview >/dev/null 2>&1; then
    echo "paraFoam was not found; opening the .foam file with paraview instead."
    exec paraview "$foam_file"
fi

echo "Neither paraFoam nor paraview was found in PATH." >&2
echo "Source your OpenFOAM environment first, or install ParaView." >&2
exit 1
