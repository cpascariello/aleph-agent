"""Entry point: python -m aleph_agent_mcp"""

from .server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
