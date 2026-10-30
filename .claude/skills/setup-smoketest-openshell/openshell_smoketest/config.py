"""Paths and constants. REPO_ROOT is computed from this file: <repo>/.claude/skills/<skill>/openshell_smoketest/config.py."""
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SKILL_DIR.parents[2]  # <repo>/.claude/skills/<skill>
PULL_SCRIPT = REPO_ROOT / "scripts" / "pull_openshell_changes.py"
GIT_ID = "-c user.name=trial -c user.email=trial@example.invalid"
CLIENTS = {  # guest HTTP clients, preferred first: name -> command builder taking a host
    "node": lambda h: ["node", "-e", f"fetch('https://{h}').then(r=>console.log('HTTP',r.status)).catch(e=>console.log('BLOCKED',e.cause?.code||e.message))"],
    "curl": lambda h: ["sh", "-c", f"curl -s -m 15 -o /dev/null -w 'HTTP %{{http_code}}' https://{h} || echo BLOCKED"],
    "python3": lambda h: ["python3", "-c", f"import urllib.request as u\ntry: print('HTTP',u.urlopen('https://{h}',timeout=15).status)\nexcept Exception as e: print('BLOCKED',type(e).__name__)"],
}
OPENROUTER_JS = r"""
const H={authorization:'Bearer '+process.env.OPENROUTER_API_KEY,'content-type':'application/json'};
(async()=>{
 let models=['MODEL_PLACEHOLDER'].filter(Boolean);
 if(!models.length){const m=await (await fetch('https://openrouter.ai/api/v1/models')).json();
  models=(m.data||[]).filter(x=>String(x.id).endsWith(':free')).slice(0,3).map(x=>x.id);}  // free models can be empty or rate-limited: try three
 if(!models.length){console.log('NOMODEL');return;}
 for(const model of models){
  const r=await fetch('https://openrouter.ai/api/v1/chat/completions',{method:'POST',headers:H,
   body:JSON.stringify({model,max_tokens:128,messages:[{role:'user',content:'Reply with the single word OK'}]})});
  const j=await r.json().catch(()=>({}));
  const c=(j.choices&&j.choices[0]&&j.choices[0].message&&j.choices[0].message.content)||'';
  console.log('HTTP',r.status,'model',model,'reply',JSON.stringify(c).slice(0,60),'error',JSON.stringify((j.error&&j.error.message)||'').slice(0,120));
  if(r.status===200&&c.trim())return;
 }
})().catch(e=>console.log('BLOCKED',(e.cause&&e.cause.code)||e.message));
"""
