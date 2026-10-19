# The Full Command Surface

Everything the quickstart does not show. The same context flags apply
throughout — `--table`, `--project`, `--out`, `--limit`, `--format`.

```bash
CLI=/run/media/rodri/AI/skills/edstem-cli/scripts/ed_cli.py
```

## Workspace files and Git sync

```bash
# Stream the real-time file tree from the live workspace container
python3 $CLI workspace-files <workspace_id>

# Read a file directly from the container buffer, without downloading
python3 $CLI workspace-cat <workspace_id> archive.h

# Pull the full workspace tree to a local directory
python3 $CLI workspace-pull <workspace_id> --dest ./my_assessment_3

# Live sync to Git — a continuous watch daemon with auto-commits
python3 $CLI workspace-sync <workspace_id> --dest ./my_assessment_3 --push

# Single-pass sync and git commit, then exit
python3 $CLI workspace-sync <workspace_id> --dest ./my_assessment_3 --once
```

## Discovery

```bash
# The authenticated user profile and their organisation
python3 $CLI me
```

## Reading a thread

```bash
# The full raw JSON payload
python3 $CLI thread <thread_id>
```
