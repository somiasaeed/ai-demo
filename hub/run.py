"""Dev server for the Agent Hub."""

import uvicorn


def main() -> None:
    uvicorn.run(
        "hub.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        reload_dirs=["hub"],
    )


if __name__ == "__main__":
    main()
