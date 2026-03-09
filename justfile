# VPS Configuration Management
# Usage: just <command> [args] — passes everything to `uv run vps`

default *ARGS:
    @uv run vps {{ARGS}}

# Aliases for direct `just <command>` usage
setup *ARGS: (default "setup" ARGS)
deploy *ARGS: (default "deploy" ARGS)
doctor *ARGS: (default "doctor" ARGS)
server *ARGS: (default "server" ARGS)
panel *ARGS: (default "panel" ARGS)
secrets *ARGS: (default "secrets" ARGS)
