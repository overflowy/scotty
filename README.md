# Scotty

A beautiful SSH task runner. Write your deploy steps in plain bash with a few annotation comments, and Scotty takes care of connecting to your servers, running each script, and streaming the output back to you.

This is a Python port of Spatie's Scotty. Only the `Scotty.sh` bash-with-annotations format is supported — Laravel Envoy's Blade format is not.

## Why

The `Scotty.sh` format is plain bash with annotation comments. Every line is real bash, so your editor highlights it correctly and all your shell tooling (linting, syntax checking, autocompletion) just works.

While your tasks run, Scotty shows each one with its name, a step counter, elapsed time, and the command that's currently executing. When everything finishes, you get a summary table so you can see at a glance how long each step took. If you need to interrupt a deploy, you can press `p` to pause after the current task and resume with `Enter`, or `Ctrl+C` to cancel.

There's also a `scotty doctor` command that checks your setup: it validates your file, tests SSH connectivity to each server, and verifies that tools like `node`, `npm`, and `git` are installed on the remote machines.

## Requirements

- Python 3.13+
- SSH access to your target servers (key-based authentication recommended)
- macOS or Linux (Windows via WSL2)

## Installation

Using [uv](https://docs.astral.sh/uv/) (recommended):

```sh
uv tool install .
```

From inside a project clone:

```sh
uv sync
uv run scotty --help
```

## Getting started

In your project root:

```sh
scotty init
```

You'll be asked for your server's SSH connection string (for example `deployer@your-server.com`). Scotty creates a `Scotty.sh` for you.

Or create one by hand:

```sh
#!/usr/bin/env scotty

# @servers remote=deployer@your-server.com

# @task on:remote
checkUptime() {
    uptime
    df -h /
}
```

Run it:

```sh
scotty run checkUptime
```

## The Scotty.sh format

### Servers

Define which servers you want to connect to:

```sh
# @servers local=127.0.0.1 remote=deployer@your-server.com
```

You can define as many as you need:

```sh
# @servers local=127.0.0.1 web-1=deployer@1.1.1.1 web-2=deployer@2.2.2.2
```

`127.0.0.1`, `localhost`, and `local` are all treated as the local machine — Scotty skips SSH entirely for them.

### Tasks

A task is a bash function with a `# @task` annotation above it. The `on:` parameter tells Scotty which server to run it on:

```sh
# @task on:remote
deploy() {
    cd /var/www/my-app
    git pull origin main
}
```

#### Running on multiple servers

Target multiple servers by separating their names with commas. By default the task runs on each server sequentially:

```sh
# @task on:web-1,web-2
deploy() {
    cd /var/www/my-app
    git pull origin main
}
```

#### Parallel execution

Add `parallel` to run on all servers at the same time:

```sh
# @task on:web-1,web-2 parallel
restartWorkers() {
    sudo supervisorctl restart all
}
```

#### Confirmation

For dangerous tasks, require confirmation before running:

```sh
# @task on:remote confirm="Are you sure you want to deploy to production?"
deploy() {
    cd /var/www/my-app
    git pull origin main
}
```

### Macros

A macro groups multiple tasks so you can run them with a single command:

```sh
# @macro deploy pullCode runComposer clearCache restartWorkers
```

If the list gets long, use the multi-line form:

```sh
# @macro deploy
#   pullCode
#   runComposer
#   generateAssets
#   updateSymlinks
#   clearCache
#   restartWorkers
# @endmacro
```

Run it with `scotty run deploy`. Tasks execute in the order you listed them. If any task fails, execution stops immediately.

### Variables

Define variables at the top of your file, right after the server and macro lines:

```sh
BRANCH="main"
REPOSITORY="your/repo"
APP_DIR="/var/www/my-app"
RELEASES_DIR="$APP_DIR/releases"
NEW_RELEASE_NAME=$(date +%Y%m%d-%H%M%S)
```

These are plain bash variables, so computed values like `$(date)` work naturally. All variables are available in all tasks.

You can also pass variables from the command line:

```sh
scotty run deploy --branch=develop
```

The key gets uppercased and dashes become underscores, so `--branch=develop` sets `$BRANCH` to `develop`. Values are single-quoted on the wire, so special characters (`"`, `$`, spaces) are passed to the remote script literally.

### Helper functions

Any function without a `# @task` annotation is treated as a helper. Helpers are available in all tasks:

```sh
log() {
    echo -e "\033[32m$1\033[0m"
}

# @task on:remote
deploy() {
    log "Deploying..."
    cd /var/www/my-app
    git pull origin main
}
```

### Hooks

You can run code at different points during execution — useful for notifications, logging, etc:

```sh
# @before
beforeEachTask() {
    echo "Starting task..."
}

# @after
afterEachTask() {
    echo "Task done."
}

# @success
onSuccess() {
    curl -X POST https://hooks.slack.com/... -d '{"text": "Deploy succeeded!"}'
}

# @error
onError() {
    curl -X POST https://hooks.slack.com/... -d '{"text": "Deploy failed!"}'
}

# @finished
onFinished() {
    echo "Deploy process complete."
}
```

`@before` and `@after` run around each task. `@success` and `@error` run once at the end depending on whether everything passed. `@finished` always runs, regardless of the outcome. All hooks execute locally.

## Running tasks

### Basic usage

```sh
scotty run deploy
scotty run cloneRepository
```

### Pretend mode

See what would happen without connecting anywhere:

```sh
scotty run deploy --pretend
```

This prints the SSH command Scotty would run, including the full heredoc it would pipe to `bash -se` on the remote.

### Continue on failure

By default, Scotty stops at the first failed task. To keep going:

```sh
scotty run deploy --continue
```

### Summary mode

Hide task output and only show the results table. Failed tasks always show their output:

```sh
scotty run deploy --summary
```

### Dynamic options

Pass custom variables from the command line:

```sh
scotty run deploy --branch=develop
```

`--branch=develop` becomes `$BRANCH` inside your tasks.

### Pause and resume

Press `p` mid-deploy and Scotty will wait after the current task finishes. Press `Enter` to continue, or `Ctrl+C` to quit.

### Cancelling

Press `Ctrl+C` at any time. Scotty restores the terminal and exits cleanly, leaving the output in your scrollback.

## Other commands

### List tasks

```sh
scotty tasks
```

Shows all macros and tasks defined in your file, along with the server they target.

### SSH into a server

```sh
scotty ssh
scotty ssh remote
```

With one remote server defined, Scotty connects directly. With multiple, you'll get a picker. Local servers are skipped.

### Doctor

```sh
scotty doctor
```

Runs through a series of checks:

1. A Scotty file exists and is found
2. The file parses without errors, and reports how many tasks and macros were found
3. At least one server is defined
4. At least one task is defined
5. All tasks referenced by macros actually exist
6. SSH connectivity to each remote server, with connection timing
7. Whether `node`, `npm`, and `git` are available on each reachable server

Useful after setting up a new server or before your first deploy to a new environment.

### Init

```sh
scotty init
```

Prompts you for a server host and creates a `Scotty.sh` template in the current directory.

## File lookup order

When you run a command without `--path` or `--conf`, Scotty looks for the following files in the current directory, in order:

1. `Scotty.sh`
2. `scotty.sh`

It uses the first one it finds. Pass `--path=path/to/file.sh` or `--conf=Custom.sh` to point somewhere else.

## Complete example

```sh
#!/usr/bin/env scotty

# @servers local=127.0.0.1 remote=deployer@your-server.com
# @macro deploy
#   startDeployment
#   cloneRepository
#   runComposer
#   blessNewRelease
#   cleanOldReleases
# @endmacro

BRANCH="main"
REPOSITORY="your/repo"
APP_DIR="/var/www/my-app"
RELEASES_DIR="$APP_DIR/releases"
CURRENT_DIR="$APP_DIR/current"
NEW_RELEASE_NAME=$(date +%Y%m%d-%H%M%S)
NEW_RELEASE_DIR="$RELEASES_DIR/$NEW_RELEASE_NAME"

# @task on:local
startDeployment() {
    git checkout $BRANCH
    git pull origin $BRANCH
}

# @task on:remote
cloneRepository() {
    cd $RELEASES_DIR
    git clone --depth 1 git@github.com:$REPOSITORY --branch $BRANCH $NEW_RELEASE_NAME
}

# @task on:remote
runComposer() {
    cd $NEW_RELEASE_DIR
    ln -nfs $APP_DIR/.env .env
    composer install --prefer-dist --no-dev -o
}

# @task on:remote
blessNewRelease() {
    ln -nfs $NEW_RELEASE_DIR $CURRENT_DIR
    sudo service php8.4-fpm restart
}

# @task on:remote
cleanOldReleases() {
    cd $RELEASES_DIR
    ls -dt $RELEASES_DIR/* | tail -n +4 | xargs rm -rf
}
```

## Development

Install dev dependencies and run the test suite:

```sh
uv sync
uv run pytest
```

Tests live in `tests/`. Unit tests cover the parser, models, and SSH command builder; feature tests drive the `scotty` CLI end-to-end via subprocess.

## Notes on this port

- Laravel Envoy compatibility was dropped. Neither the Blade (`Envoy.blade.php`) format nor auto-discovery of `Envoy.sh` is supported.
- `scotty doctor` checks `node`, `npm`, and `git` on remotes — no PHP/Composer probes.
- Environment variables injected into the remote script via `--key=value` are `shlex`-quoted, so values containing `"`, `$`, spaces, etc. are passed through literally.

## Credits

This project is a Python port of [Spatie's Scotty](https://github.com/spatie/scotty) by [Spatie](https://spatie.be). The original is licensed under MIT. The `Scotty.sh` format, CLI ergonomics, and output design are all their work — this port reimplements those ideas in Python.

## License

Released under the MIT License.
