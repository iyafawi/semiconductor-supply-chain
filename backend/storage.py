"""Compatibility entry point; persistence is exclusively SQL Server."""

from repository import SqlRepository, connect, initialize


def snapshot():
    return SqlRepository().network()


if __name__ == "__main__":
    initialize()
