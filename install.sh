#!/usr/bin/env bash
set -euo pipefail

start_services=true
for argument in "$@"; do
  case "$argument" in
    --no-start) start_services=false ;;
    *)
      printf 'Unknown option: %s\n' "$argument" >&2
      exit 2
      ;;
  esac
done

os_name="$(uname -s)"

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_root="${XDG_DATA_HOME:-$HOME/.local/share}/agentdiode"
venv_dir="$install_root/venv"
bin_dir="$HOME/.local/bin"
integration_dir="$install_root/integrations/callbacks"

command -v python3 >/dev/null || {
  printf '%s\n' "Python 3 is required." >&2
  exit 1
}

python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' || {
  printf '%s\n' "Python 3.11 or newer is required." >&2
  exit 1
}

if [[ "$os_name" == "Darwin" ]]; then
  macos_major="$(sw_vers -productVersion | cut -d. -f1)"
  if [[ "$macos_major" -lt 26 ]]; then
    printf '%s\n' "Warning: AgentDiode targets macOS 26 (Tahoe) or newer; detected $macos_major.x. Continuing anyway." >&2
  fi
fi

mkdir -p "$install_root" "$bin_dir" "$integration_dir"
python3 -m venv "$venv_dir"
"$venv_dir/bin/pip" install --upgrade pip
"$venv_dir/bin/pip" install "$project_dir[tray]"

for executable in agentdiode agentdiode-daemon agentdiode-tray; do
  ln -sfn "$venv_dir/bin/$executable" "$bin_dir/$executable"
done

install -m 0755 "$project_dir/integrations/callbacks/codex-hook" \
  "$integration_dir/codex-hook"
install -m 0755 "$project_dir/integrations/callbacks/claude-hook" \
  "$integration_dir/claude-hook"
install -m 0755 "$project_dir/integrations/callbacks/antigravity-hook" \
  "$integration_dir/antigravity-hook"

if [[ "$os_name" == "Darwin" ]]; then
  agents_dir="$HOME/Library/LaunchAgents"
  mkdir -p "$agents_dir"
  for unit in io.agentdiode.daemon io.agentdiode.tray; do
    sed "s#__AGENTDIODE_BIN_DIR__#$bin_dir#g" \
      "$project_dir/packaging/launchd/$unit.plist" > "$agents_dir/$unit.plist"
  done

  if "$start_services"; then
    for unit in io.agentdiode.daemon io.agentdiode.tray; do
      launchctl bootout "gui/$(id -u)/$unit" >/dev/null 2>&1 || true
      launchctl bootstrap "gui/$(id -u)" "$agents_dir/$unit.plist"
      launchctl enable "gui/$(id -u)/$unit"
    done
  else
    printf '%s\n' "LaunchAgents were installed but not started (--no-start)."
  fi
else
  systemd_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  desktop_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  icon_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
  mkdir -p "$systemd_dir" "$desktop_dir" "$icon_dir"

  install -m 0644 "$project_dir/packaging/systemd/agentdiode-daemon.service" \
    "$systemd_dir/agentdiode-daemon.service"
  install -m 0644 "$project_dir/packaging/systemd/agentdiode-tray.service" \
    "$systemd_dir/agentdiode-tray.service"
  install -m 0644 "$project_dir/packaging/desktop/io.agentdiode.AgentDiode.desktop" \
    "$desktop_dir/io.agentdiode.AgentDiode.desktop"
  install -m 0644 "$project_dir/packaging/icons/io.agentdiode.AgentDiode.svg" \
    "$icon_dir/io.agentdiode.AgentDiode.svg"

  if "$start_services"; then
    systemctl --user daemon-reload
    systemctl --user enable --now agentdiode-daemon.service
    systemctl --user enable --now agentdiode-tray.service
  else
    printf '%s\n' "User services were installed but not started (--no-start)."
  fi
fi

printf '%s\n' "AgentDiode installed in $install_root"
if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
  printf '%s\n' "Add $bin_dir to PATH to use the AgentDiode CLI."
fi
printf '%s\n' "Run: agentdiode integrations setup --codex"
printf '%s\n' "Then open Codex and use /hooks to review and trust the hooks."
printf '%s\n' "Diagnostics: agentdiode doctor"
