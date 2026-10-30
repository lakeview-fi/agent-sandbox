"""Checks 6, 7, 9, 10 (observations): raw TCP, secret-like env vars, denials in the log, sandbox settings. INFO only."""
import re

from .model import INFO, Check, Ctx
from .process import gsh, osh


def step_observations(ctx: Ctx) -> list[Check]:
    n = ctx.name
    tcp = gsh(n, 'timeout 5 bash -c "exec 3<>/dev/tcp/1.1.1.1/443" && echo CONNECTED || echo FAILED')
    flow = gsh(n, "curl --noproxy '*' -sk -m 8 -o /dev/null -w '%{http_code}' https://1.1.1.1 2>&1; true")
    env = gsh(n, "env | grep -Ei '^[^=]*(key|token|secret|passw|ssh_auth|credential)' | awk -F= '{print $1\" (value length \"length($0)-length($1)-1\")\"}' || echo none")
    logs = osh("logs", n, "--source", "sandbox", "--since", "15m", "-n", "400").text
    refused = len(re.findall(r"NET:REFUSE|DENIED", logs))
    proposals = re.findall(r"[^\n]*proposals?=[^\n]*", logs)[:3]
    settings = osh("settings", "get", n).text
    return [
        Check("6 raw TCP to 1.1.1.1:443 (connect / HTTP status, 000 = no data)", INFO, f"{tcp.text[-100:]} / {flow.text[-100:]}"),
        Check("7 secret-like env vars (names and value lengths only)", INFO, env.text or "none"),
        Check("9 denials in the sandbox log; Policy Advisor proposals", INFO, f"{refused} refused/denied lines; proposals: {proposals or 'none seen'}"),
        Check("10 sandbox settings (is Policy Advisor enabled?)", INFO, "\n".join(settings.splitlines()[:25])),
    ]
