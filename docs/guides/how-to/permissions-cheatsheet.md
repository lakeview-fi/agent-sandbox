# Permissions cheat sheet

Task to command, for both tools. Replace `myproj` with your sandbox name. Details and caveats: [Docker how-to](docker-sandbox-how-to.md), [OpenShell how-to](openshell-how-to.md).

| Task | Docker Sandboxes (`sbx`) | OpenShell |
|---|---|---|
| Set the network default | `sbx policy init deny-all\|balanced\|allow-all` (once) | `policy.yaml` lists allowed endpoints; everything else is denied |
| List current rules | `sbx policy ls myproj` | `openshell policy get myproj --full` |
| See blocked requests | `sbx policy log myproj` | `openshell logs myproj --source sandbox` |
| Allow a host (live) | `sbx policy allow network --sandbox myproj host` | `openshell policy update myproj --rule-name X --binary P --add-endpoint host:443:read-only:rest:enforce --wait` |
| Limit to some requests | `--method GET --path '/v1/**'` | `--add-allow host:443:GET:/v1/**` (needs `--rule-name`, `--binary`) |
| Block a host | `sbx policy deny network --sandbox myproj host` | `--remove-endpoint host:443` or `--remove-rule X` |
| Remove a rule | `sbx policy rm network --id ID` | `openshell policy update myproj --remove-rule X` |
| Let the agent ask, you approve | `sbx policy approval ls` / `respond` | Policy Advisor: `openshell rule get myproj --status pending`, then `rule approve` / `reject` |
| Add a path or mount | `additionalWorkspaces` in `sbxenv.yaml`, recreate | `read_only` / `read_write` in `policy.yaml`, recreate |
| Make a path read-only | `readOnly: true` or `:ro` on the mount | List it under `read_only` only |
| Store a credential | `sbx secret set <service> [--sandbox myproj]` | `openshell provider create --name X --type T --from-existing` |
| List credentials | `sbx secret ls` | `openshell provider list` |
| Bind a credential to hosts | `bindings.<service>.apiKey.domains` | Provider endpoint binding |
| Run non-interactively | `sbx exec myproj -- <cmd>` | `openshell sandbox exec -n myproj -- <cmd>` |
| Copy files in | mount, or `sbx cp ./f myproj:/path/` | `--upload` at create, or `openshell sandbox upload myproj ./f /dest` |
| Copy files out | Nothing to copy (direct mount); `sandbox/pull.ps1` (clone mode); or `sbx cp myproj:/path ./` | `openshell sandbox download myproj /path ./` |
| Persist a live change | Add the host to `kit/kit.yaml`; recreate | Copy the rule into `policy.yaml`; recreate |
| Check a policy is within limits | `sbx policy check network host`; run the negative tests | `openshell-prover check effective.yaml --boundary boundary.yaml` |
| Stop, keep state | `sbx stop myproj` | `openshell sandbox stop myproj` |
| Delete | `sbx rm myproj` / `sbx env rm` (from the repo root) | `openshell sandbox delete myproj` |

## What needs a recreate

| Change | Docker | OpenShell |
|---|---|---|
| Network rule | Live | Live |
| Mount or filesystem path | Recreate | Recreate |
| Process user, Landlock mode | n/a | Recreate |
| Credential or binding | Recreate | Recreate |
| Image or kit contents | Recreate | Recreate |

## Negative tests (run after every change)

An unlisted host is blocked, a host path outside the project is not visible, and a write to a read-only path fails. A rule that was never tested has not been shown to hold.
