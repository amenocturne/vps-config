# VPS Configuration Management

default:
    @uv run vps

setup:
    uv run vps setup

deploy *ARGS:
    uv run vps deploy {{ARGS}}

doctor *ARGS:
    uv run vps doctor {{ARGS}}

server *ARGS:
    uv run vps server {{ARGS}}

panel *ARGS:
    uv run vps panel {{ARGS}}

secrets *ARGS:
    uv run vps secrets {{ARGS}}
