import os

from pathlib import Path

from invoke import task, Context  # type: ignore

DATA_GENERATORS = [
    "init_data.py",
]

# If no version is indicated, we will take the latest
VERSION = os.getenv("INFRAHUB_VERSION", None)
COMPOSE_COMMAND = f"curl https://infrahub.opsmill.io/{VERSION if VERSION else ''} | docker compose -f -"

@task
def start(context: Context) -> None:
    context.run(f"{COMPOSE_COMMAND} up -d")

@task
def load_schema(context: Context, schema: Path=Path("./models/**/*.yml")) -> None:
    context.run(f"infrahubctl schema load {schema}")

@task
def load_data(context: Context) -> None:
    for generator in DATA_GENERATORS:
        context.run(f"infrahubctl run scripts/{generator}")

@task
def destroy(context: Context) -> None:
    context.run(f"{COMPOSE_COMMAND} down -v")

@task
def stop(context: Context) -> None:
    context.run(f"{COMPOSE_COMMAND} down")

@task
def restart(context: Context, component: str="")-> None:
    if component:
        context.run(f"{COMPOSE_COMMAND} restart {component}")
        return

    context.run(f"{COMPOSE_COMMAND} restart")

