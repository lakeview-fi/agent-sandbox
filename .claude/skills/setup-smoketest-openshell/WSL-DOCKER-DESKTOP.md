# Docker Desktop for WSL2 (Windows host)

Use this when the trial runs in WSL2 on a Windows 11 host and the OpenShell gateway needs Docker. Live docs: https://docs.docker.com/desktop/features/wsl/ (they override this file). Menu labels change between releases; match on meaning.

## Settings

- **General → Choose Virtual Machine Manager (VMM):** set to `wsl2`. Older docs call this "Use WSL 2 based engine"; that checkbox is gone.
- **Resources → WSL integration:** turn on **Enable integration with additional distros**, then switch on your distro (for example `Ubuntu`). The page may not show the toggle state clearly; confirm it with `docker info` after restart.
- **General → Expose daemon on tcp://localhost:2375 without TLS:** keep **off**. The UI warns it allows remote code execution, and the trial does not need it.
- **General → Add the \*.docker.internal names to the host's /etc/hosts file:** disabled on a per-user install (for example from the Microsoft Store), with the tooltip "Per-user installations can't run the privileged helper service". Use the fallback below.

Click **Apply & restart** after changes.

## Fallback: resolve host.docker.internal

`gateway.toml` uses `https://host.docker.internal:17670`, so the name must resolve. With the checkbox disabled, the user adds it to the WSL hosts file (needs sudo):

```sh
echo "127.0.0.1 host.docker.internal" | sudo tee -a /etc/hosts
getent hosts host.docker.internal    # expect: 127.0.0.1  host.docker.internal
```

Alternatives:

- Windows side: as administrator, add the same line to `C:\Windows\System32\drivers\etc\hosts`. Only needed if Windows tools must resolve the name.
- Reinstall Docker Desktop system-wide from docker.com. That enables the checkbox and the helper service. Bigger change; ask first.

A WSL hosts entry only affects processes in WSL. Containers reach the host through Docker Desktop's own networking, so check the gateway's container-side endpoint once the gateway runs.

## Restart order

Do this after changing integration settings, and again if the socket is denied:

1. Apply & restart in Docker Desktop.
2. In Windows PowerShell: `wsl --shutdown`.
3. Quit Docker Desktop from the system tray, start it again, and wait for "Engine running".
4. In the WSL shell: `docker info`. Expect a `Server Version` line.

## Socket symptoms

- `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`.
- With a per-user Docker Desktop install on WSL2, the socket can show as `srw-rw---- nobody nogroup`, and so can the sockets under `/mnt/wsl/docker-desktop/shared-sockets/`. Adding the user to the `docker` group does not help, because the socket's group is `nogroup`.
- In that state the error usually goes away only after the restart order above. Do not chmod or chown the socket; the change does not survive a restart and bypasses Docker Desktop's access handling.

## What success looks like

- `docker info` shows a `Server Version` line.
- `openshell status` shows `Status: Connected` and `Authentication: Authenticated (mTLS transport)`.
- `systemctl --user` may fail from the agent's sandboxed shell (`Operation not permitted`). Restart the gateway from the user's own shell if needed.
