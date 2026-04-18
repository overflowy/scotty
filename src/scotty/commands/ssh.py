from __future__ import annotations

import os

from scotty.parsing.models import ServerDefinition
from scotty.ui import output as out
from scotty.ui.prompts import select


def handle_ssh(args, file_path: str, parser) -> int:
    config = parser.parse(file_path)
    servers = config.servers

    if not servers:
        out.error("No servers defined.")
        return 1

    host_options: dict[str, str] = {}
    for server in servers.values():
        for host in server.hosts:
            host_options[f"{server.name} ({host})"] = host

    name = args.name

    if name is not None:
        server = config.get_server(name)

        if server is None:
            out.error(f'Server "{name}" is not defined.')
            return 1

        if server.is_local():
            out.error("Cannot SSH into local server.")
            return 1

        if len(server.hosts) == 1:
            host = server.hosts[0]
        else:
            filtered = {k: v for k, v in host_options.items() if v in server.hosts}
            selected = select(label="Which host?", options=list(filtered.keys()))
            host = filtered[selected]
    else:
        remote_options = {
            k: v for k, v in host_options.items() if not ServerDefinition.is_local_host(v)
        }

        if not remote_options:
            out.error("No remote servers defined.")
            return 1

        if len(remote_options) == 1:
            selected = next(iter(remote_options))
        else:
            selected = select(label="Which server?", options=list(remote_options.keys()))

        host = remote_options[selected]

    os.execvp("ssh", ["ssh", host])
    return 0  # unreachable
