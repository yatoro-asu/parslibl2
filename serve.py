import subprocess
import sys
from pathlib import Path

from livereload import Server

BASE_DIR = Path(__file__).resolve().parent


def build() -> None:
    subprocess.run(
        [sys.executable, str(BASE_DIR / "generate_site.py")],
        check=True,
        cwd=str(BASE_DIR),
    )


build()
server = Server()
server.watch(str(BASE_DIR / "books.json"), build)
server.watch(str(BASE_DIR / "templates"), build)
server.watch(str(BASE_DIR / "generate_site.py"), build)
server.serve(root=str(BASE_DIR), open_url_delay=1)
