# VPS Configuration Management
#
# Two ways to use:
#   just install   — install `vps` globally, then use `vps <args>` from anywhere
#   just <args>    — run via uv without installing (e.g. just doctor --secrets)

install:
    uv tool install -e . --force

default *ARGS:
    @uv run vps {{ARGS}}

# Aliases so `just doctor` works (not just `just -- doctor`)
setup *ARGS: (default "setup" ARGS)
deploy *ARGS: (default "deploy" ARGS)
doctor *ARGS: (default "doctor" ARGS)
server *ARGS: (default "server" ARGS)
panel *ARGS: (default "panel" ARGS)
secrets *ARGS: (default "secrets" ARGS)
