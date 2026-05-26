"""
Entry point for `python -m permadesign`.

    python -m permadesign mcp      # start the MCP server
    python -m permadesign <cli>    # everything else goes to the CLI
"""

import sys


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "mcp":
        from src.mcp_server import main as mcp_main
        mcp_main()
    else:
        from src.cli import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()
