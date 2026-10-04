#!/usr/bin/env bash

bioagent_load_profile() {
    local component=$1 profile=${BIOAGENT_DEPLOYMENT_PROFILE:-} loader_root python_bin env_file line key value
    [[ -n "$profile" ]] || return 0
    loader_root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
    if [[ "$profile" != /* ]]; then
        profile="$loader_root/$profile"
    fi
    python_bin=${BIOAGENT_PROFILE_PYTHON:-python3}
    env_file=$(mktemp "${TMPDIR:-/tmp}/bioagent-profile.XXXXXX")
    if ! "$python_bin" "$loader_root/deployment_profile.py" env "$profile" "$component" >"$env_file"; then
        rm -f "$env_file"
        return 1
    fi
    while IFS= read -r line; do
        [[ "$line" == *=* ]] || {
            rm -f "$env_file"
            echo "DeploymentProfile 输出无效。" >&2
            return 1
        }
        key=${line%%=*}
        value=${line#*=}
        [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || {
            rm -f "$env_file"
            echo "DeploymentProfile 环境变量名无效：$key" >&2
            return 1
        }
        printf -v "$key" '%s' "$value"
        export "$key"
    done <"$env_file"
    rm -f "$env_file"
}
