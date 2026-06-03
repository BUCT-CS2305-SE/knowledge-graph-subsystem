"""命令行启动入口：python3 -m server。"""

import os

import uvicorn


def main() -> None:
    host = os.environ.get("KG_API_HOST", "127.0.0.1")
    port = int(os.environ.get("KG_API_PORT", "8000") or 8000)
    reload_flag = os.environ.get("KG_API_RELOAD", "0") == "1"
    uvicorn.run("server.main:app", host=host, port=port, reload=reload_flag)


if __name__ == "__main__":
    main()
