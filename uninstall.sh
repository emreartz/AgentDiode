#!/usr/bin/env bash
set -euo pipefail

: "${HOME:?HOME must be set}"

keep_data=true
restore_integrations=false
manage_services=true
for argument in "$@"; do
  case "$argument" in
    --keep-data) keep_data=true ;;
    --remove-data) keep_data=false ;;
    --restore-integrations) restore_integrations=true ;;
    --no-services) manage_services=false ;;
    *)
      printf 'Unknown option: %s\n' "$argument" >&2
      exit 2
      ;;
  esac
done

os_name="$(uname -s)"

install_root="${XDG_DATA_HOME:-$HOME/.local/share}/agentdiode"
venv_dir="$install_root/venv"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/agentdiode"
if [[ "$os_name" == "Darwin" ]]; then
  state_dir="$HOME/Library/Application Support/agentdiode"
fi
hooks_file="$HOME/.codex/hooks.json"

# Refuse to touch anything unless install_root is the specific path we
# expect (never empty/HOME/root) -- guards rm -rf below against a broken
# or hijacked XDG_DATA_HOME/HOME environment.
case "$install_root" in
  */agentdiode) : ;;
  *)
    printf 'agentdiode: refusing to uninstall, unexpected install path: %s\n' "$install_root" >&2
    exit 1
    ;;
esac
if [[ "$install_root" == "$HOME" || "$install_root" == "/" || -z "$install_root" ]]; then
  printf 'agentdiode: refusing to uninstall, unsafe install path: %s\n' "$install_root" >&2
  exit 1
fi

# Only remove a symlink we can confirm install.sh created, i.e. one whose
# target text still points inside our own venv_dir (install.sh writes these
# symlinks using this exact same, uncanonicalized path). Deliberately not
# using `readlink -f`: on macOS it canonicalizes ancestor symlinks like
# /var -> /private/var, which would make this path-prefix check pass or
# fail for reasons unrelated to who owns the file. Leaves alone anything
# else that happens to occupy the same filename (another tool, a user's
# own script), and dangling symlinks left by a prior partial uninstall are
# still recognized since we're comparing link text, not resolving it.
remove_owned_link() {
  local target="$1"
  if [[ -L "$target" ]]; then
    local link_text
    link_text="$(readlink -- "$target" 2>/dev/null || true)"
    case "$link_text" in
      "$venv_dir"/*) rm -- "$target" ;;
      *) printf 'agentdiode: leaving unrecognized symlink in place: %s\n' "$target" >&2 ;;
    esac
  elif [[ -f "$target" ]]; then
    printf 'agentdiode: leaving unexpected non-symlink in place: %s\n' "$target" >&2
  fi
}

# Only remove a launchd/systemd unit file if its contents actually reference
# this project, so a same-named file that isn't ours is never touched.
remove_owned_unit() {
  local target="$1"
  local marker="$2"
  if [[ -f "$target" ]] && grep -qF -- "$marker" "$target" 2>/dev/null; then
    rm -- "$target"
  elif [[ -f "$target" ]]; then
    printf 'agentdiode: leaving unexpected file in place: %s\n' "$target" >&2
  fi
}

if "$restore_integrations" && [[ -x "$venv_dir/bin/agentdiode" ]]; then
  "$venv_dir/bin/agentdiode" integrations remove codex --hooks-file "$hooks_file"
  "$venv_dir/bin/agentdiode" integrations remove claude
  "$venv_dir/bin/agentdiode" integrations remove antigravity
fi

if [[ "$os_name" == "Darwin" ]]; then
  agents_dir="$HOME/Library/LaunchAgents"
  if "$manage_services"; then
    for unit in io.agentdiode.tray io.agentdiode.daemon; do
      launchctl bootout "gui/$(id -u)/$unit" >/dev/null 2>&1 || true
    done
  fi
  for executable in agentdiode agentdiode-daemon agentdiode-tray; do
    remove_owned_link "$HOME/.local/bin/$executable"
  done
  remove_owned_unit "$agents_dir/io.agentdiode.daemon.plist" "<string>io.agentdiode.daemon</string>"
  remove_owned_unit "$agents_dir/io.agentdiode.tray.plist" "<string>io.agentdiode.tray</string>"
else
  systemd_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  if "$manage_services"; then
    systemctl --user disable --now agentdiode-tray.service 2>/dev/null || true
    systemctl --user disable --now agentdiode-daemon.service 2>/dev/null || true
  fi
  for executable in agentdiode agentdiode-daemon agentdiode-tray; do
    remove_owned_link "$HOME/.local/bin/$executable"
  done
  remove_owned_unit "$systemd_dir/agentdiode-daemon.service" "agentdiode-daemon"
  remove_owned_unit "$systemd_dir/agentdiode-tray.service" "agentdiode-tray"
  remove_owned_unit \
    "${XDG_DATA_HOME:-$HOME/.local/share}/applications/io.agentdiode.AgentDiode.desktop" \
    "io.agentdiode.AgentDiode"
  icon_file="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps/io.agentdiode.AgentDiode.svg"
  if [[ -f "$icon_file" ]]; then
    rm -- "$icon_file"
  fi
  if "$manage_services"; then
    systemctl --user daemon-reload
  fi
fi

if [[ -d "$install_root" ]]; then
  rm -rf -- "$install_root"
fi

if ! "$keep_data" && [[ -d "$state_dir" ]]; then
  printf 'Delete AgentDiode history and logs in %s? [y/N] ' "$state_dir"
  read -r answer
  if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
    rm -rf -- "$state_dir"
    printf '%s\n' "History and logs removed; this cannot be undone."
  fi
fi

printf '%s\n' "AgentDiode application files removed."
if "$keep_data"; then
  printf 'History preserved in %s\n' "$state_dir"
fi
