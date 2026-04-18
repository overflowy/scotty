from __future__ import annotations

import os
import textwrap

from scotty.ui import output as out
from scotty.ui.prompts import text


def handle_init(args) -> int:
    filename = "Scotty.sh"

    if os.path.exists(filename):
        out.error(f"{filename} already exists.")
        return 1

    host = text(label="Server host", placeholder="user@hostname", required=True)

    with open(filename, "w") as f:
        f.write(_bash_template(host))

    out.info(f"Created {filename}")
    return 0


def _bash_template(host: str) -> str:
    return textwrap.dedent(f"""\
        #!/usr/bin/env scotty

        # @servers local=127.0.0.1 remote={host}
        # @macro deploy startDeployment deploy

        BRANCH="main"

        # @task on:local
        startDeployment() {{
            git checkout $BRANCH
            git pull origin $BRANCH
        }}

        # @task on:remote
        deploy() {{
            cd /home/forge/myapp
            git pull origin $BRANCH
            php artisan migrate --force
        }}
    """)
