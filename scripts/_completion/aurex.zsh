#compdef aurex aurex-backup aurex-calendar aurex-contacts aurex-cookbook aurex-docs aurex-gallery aurex-mail aurex-mcp aurex-memory aurex-notes aurex-personal aurex-preset aurex-research aurex-sessions aurex-signature aurex-skills aurex-tasks aurex-theme aurex-webhook
# Zsh tab-completion for the aurex umbrella + sub-CLIs.
#
# Drop in any directory on $fpath, e.g.:
#     fpath=(/path/to/aurex-ui/scripts/_completion $fpath)
#     autoload -U compinit; compinit
#
# Then `aurex <tab>` completes subcommands; `aurex mail <tab>`
# completes mail subcommands; `aurex-mail <tab>` works the same.

_aurex_scripts_dir() {
    local self="${(%):-%x}"
    while [[ -L "$self" ]]; do self="$(readlink "$self")"; done
    cd "${self:h}/.." && pwd
}

typeset -gA _aurex_subs

_aurex_refresh() {
    _aurex_subs=()
    local dir="$(_aurex_scripts_dir)"
    local py="$dir/../venv/bin/python"
    [[ -x "$py" ]] || py="$(command -v python3)"
    local f sub help_out commands
    for f in "$dir"/aurex-*; do
        [[ -x "$f" ]] || continue
        case "$f" in
            *.bak|*.pyc|*.pre-*) continue ;;
        esac
        sub="${${f:t}#aurex-}"
        help_out=$("$py" "$f" --help 2>/dev/null) || continue
        commands=$(echo "$help_out" | grep -oE '\{[a-z0-9_,-]+\}' | head -1 \
            | tr -d '{}' | tr ',' ' ')
        _aurex_subs[$sub]="$commands"
    done
}

_aurex() {
    [[ ${#_aurex_subs} -eq 0 ]] && _aurex_refresh

    local cmd="${words[1]}"

    if [[ "$cmd" == "aurex" ]]; then
        if (( CURRENT == 2 )); then
            local -a subs=(${(k)_aurex_subs} help)
            _describe 'subcommand' subs
            return
        fi
        local sub="${words[2]}"
        if [[ "$sub" == "help" ]] && (( CURRENT == 3 )); then
            local -a subs=(${(k)_aurex_subs})
            _describe 'subcommand' subs
            return
        fi
        if (( CURRENT == 3 )); then
            local -a sc=(${(s/ /)_aurex_subs[$sub]})
            _describe 'command' sc
            return
        fi
        return
    fi

    # aurex-foo <tab>
    local sub="${cmd#aurex-}"
    if (( CURRENT == 2 )); then
        local -a sc=(${(s/ /)_aurex_subs[$sub]})
        _describe 'command' sc
        return
    fi
}

_aurex "$@"
