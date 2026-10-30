"""Checks 5-7: raw TCP, secret-like env vars, approvals queued. Observations only (INFO)."""
from .model import INFO, Check, Ctx
from .process import guest, pending_titles


def step_observations(ctx: Ctx) -> list[Check]:
    n = ctx.name
    tcp = guest(n, 'timeout 5 bash -c "exec 3<>/dev/tcp/1.1.1.1/443" && echo CONNECTED || echo FAILED')
    flow = guest(n, "curl --noproxy '*' -sk -m 8 -o /dev/null -w '%{http_code}' https://1.1.1.1; true")
    env = guest(n, "env | grep -Ei '^[^=]*(key|token|secret|passw|ssh_auth|credential)' "
                   "| awk -F= '{print $1\" (value length \"length($0)-length($1)-1\")\"}' || echo none")
    new_titles = sorted(set(pending_titles(n)) - ctx.approvals_before)
    return [
        Check("5 raw TCP to 1.1.1.1:443 (connect / HTTP status, 000 = no data)", INFO, f"{tcp.text[-100:]} / {flow.text[-100:]}"),
        Check("6 secret-like env vars (names and value lengths only)", INFO, env.text or "none"),
        Check("7 approvals queued during tests", INFO, ", ".join(new_titles) or "none"),
    ]
