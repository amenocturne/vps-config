# VPS Configuration Management

default:
    @uv run vps --help

setup:
    uv run vps setup

deploy *ARGS:
    uv run vps deploy {{ARGS}}

logs *ARGS:
    uv run vps logs {{ARGS}}

restart *ARGS:
    uv run vps restart {{ARGS}}

ssh *ARGS:
    uv run vps ssh {{ARGS}}

ping *ARGS:
    uv run vps ping {{ARGS}}

validate *ARGS:
    uv run vps validate {{ARGS}}
