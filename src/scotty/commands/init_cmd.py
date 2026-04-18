from __future__ import annotations

import os
import textwrap

from scotty.ui import output as out
from scotty.ui.prompts import select, text


def handle_init(args) -> int:
    fmt = select(
        label="Which format?",
        options={"bash": "Bash (Scotty.sh)", "blade": "Blade (Scotty.blade.php)"},
        default="bash",
    )

    filename = "Scotty.sh" if fmt == "bash" else "Scotty.blade.php"

    if os.path.exists(filename):
        out.error(f"{filename} already exists.")
        return 1

    host = text(label="Server host", placeholder="user@hostname", required=True)

    if fmt == "bash":
        content = _bash_template(host)
    else:
        content = _blade_template(host)

    with open(filename, "w") as f:
        f.write(content)

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


def _blade_template(host: str) -> str:
    return textwrap.dedent(f"""\
        @servers(['local' => '127.0.0.1', 'remote' => '{host}'])

        @task('deploy', ['on' => 'remote'])
            cd /home/forge/myapp
            git pull origin {{{{ $branch }}}}
            php artisan migrate --force
        @endtask
    """)
