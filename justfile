# VPS Configuration Management
#
# Two ways to use:
#   just install   — install `vps` globally, then use `vps <args>` from anywhere
#   just vps <args> — run via uv without installing (e.g. just vps doctor --secrets)

install:
    uv tool install -e . --force

vps *ARGS:
    @uv run vps {{ARGS}}
