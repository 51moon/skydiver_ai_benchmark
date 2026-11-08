#!/usr/bin/env python3
"""
run_benchmark.py — "Skydiver" AI-agent benchmark comparing two models via OpenRouter/OpenCode.

  1. Reads task.md and evaluation.md (reference values + tolerances).
  2. Runs one `opencode run` agent per model in runs/<model>/.
  3. Scores each results.json against evaluation.md (max 20 points).
  4. Builds a self-contained HTML report at docs/index.html.

Usage:
  python3 run_benchmark.py              # run default models
  python3 run_benchmark.py --build-only # rebuild website from existing runs/
"""

import argparse, html, json, re, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASK_FILE, EVAL_FILE = ROOT / "task.md", ROOT / "evaluation.md"
RUNS_DIR, WEB_DIR = ROOT / "runs", ROOT / "docs"

DEFAULT_MODELS = [
    "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/cohere/north-mini-code:free",
]

PLOTS = ("velocity.jpg", "position.jpg")
MAX_PTS = 20
# Scoring tiers: (threshold, points) — first match wins.
T95_TIERS = [(0.05, 3), (0.5, 2), (2.0, 1)]
S95_TIERS = [(1.0, 3), (10.0, 2), (50.0, 1)]
NUM_T95_TOL, NUM_S95_TOL, MAXDEV_TOL, MIN_PLOT = 0.05, 1.0, 0.05, 5000
LIMIT_PATTERNS = ("lim", r"t\to\infty", "t → ∞", "t→∞", r"t \to \infty")

AGENT_PROMPT = """You are participating in the "Skydiver" AI-agent benchmark described in the attached task.md.
The file evaluation.md (next to task.md) contains the reference values and scoring tolerances. Do not use it.

WORKDIR = {workdir}

IMPORTANT: Create ALL files using ABSOLUTE paths under WORKDIR, e.g. {workdir}/solution/solution.md.
Do NOT rely on the shell's current directory and do NOT write anywhere outside WORKDIR.

Do the following:
1. Read task.md carefully.
2. Create the folder {workdir}/solution/ containing:
   - `solution.md`  — full analytical derivation (a)-(c), incl. stationarity argument (limit t->infinity), exact t95 and s95, and s(t).
   - `skydiver.py`  — standalone numerical simulation (numpy/scipy/matplotlib allowed). It must write
     `results.json`, `velocity.jpg` and `position.jpg` into the SAME folder as the script (i.e. {workdir}/solution/).
   - `results.json` — produced by running skydiver.py, schema exactly as in task.md section 4.
3. Run `python3 {workdir}/solution/skydiver.py` so that {workdir}/solution/results.json,
   {workdir}/solution/velocity.jpg and {workdir}/solution/position.jpg exist.
4. Finally run `find {workdir} -type f -not -path '*/.git/*'` and confirm that
   {workdir}/solution/ contains all 5 files.

At the end, reply with a short summary and the contents of results.json."""


def slug(model):
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


def fmt(v, nd=6):
    if v is None: return "—"
    if isinstance(v, float) and v != 0 and abs(v) < 1e-3: return f"{v:.2e}"
    return f"{v:.{nd}f}"


def tier(dev, tiers):
    for threshold, pts in tiers:
        if dev < threshold: return pts
    return 0


def parse_references():
    text = EVAL_FILE.read_text()
    t = re.search(r"t_\{95, ref\}\s*=\s*([\d]+[.,]\d+)", text)
    s = re.search(r"s_\{95, ref\}\s*=\s*([\d]+[.,]\d+)", text)
    if not t or not s: raise SystemExit("Could not parse reference values from evaluation.md.")
    return float(t.group(1).replace(",", ".")), float(s.group(1).replace(",", "."))


def run_model(model, timeout_s):
    """Run one OpenCode agent; return run metadata."""
    wd = RUNS_DIR / slug(model)
    if wd.exists(): shutil.rmtree(wd)
    wd.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=wd, check=True)  # mini repo = project root
    shutil.copy(TASK_FILE, wd / "task.md")
    shutil.copy(EVAL_FILE, wd / "evaluation.md")
    prompt = AGENT_PROMPT.format(workdir=wd)
    (wd / "PROMPT.md").write_text(prompt)

    cmd = ["opencode", "run", "--auto", "--standalone", "--format", "json",
           "-m", model, "--title", f"skydiver-{slug(model)}",
           "-f", str(wd / "task.md"), prompt]
    log = wd / "opencode_output.jsonl"
    print(f"\n=== Starting: {model}  (workdir: {wd}) ===", flush=True)
    start = datetime.now()
    with log.open("w") as f:
        proc = subprocess.run(cmd, cwd=wd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout_s)
    elapsed = (datetime.now() - start).total_seconds()
    print(f"=== Done: {model} (exit {proc.returncode}, {elapsed:.0f}s) ===", flush=True)
    return {"model": model, "slug": slug(model), "workdir": str(wd.relative_to(ROOT)),
            "exit_code": proc.returncode, "elapsed_s": round(elapsed, 1),
            "log": str(log.relative_to(ROOT))}


def parse_usage(wd):
    """Sum token usage and cost from all step_finish entries in the opencode JSONL log."""
    log = wd / "opencode_output.jsonl"
    usage = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    cost = 0.0
    if not log.exists(): return usage, cost
    for line in log.read_text(errors="replace").splitlines():
        try: e = json.loads(line)
        except Exception: continue
        if e.get("type") != "step_finish": continue
        part = e.get("part", {})
        t = part.get("tokens", {})
        usage["input"] += t.get("input", 0)
        usage["output"] += t.get("output", 0)
        usage["reasoning"] += t.get("reasoning", 0)
        cache = t.get("cache", {})
        usage["cache_read"] += cache.get("read", 0)
        usage["cache_write"] += cache.get("write", 0)
        cost += part.get("cost", 0) or 0
    return usage, cost


def parse_log_meta(wd):
    """Recover elapsed time, exit code and log path from the opencode JSONL log (used in --build-only)."""
    log = wd / "opencode_output.jsonl"
    meta = {"exit_code": "?", "elapsed_s": 0, "log": ""}
    if not log.exists():
        return meta
    meta["log"] = str(log.relative_to(ROOT))
    ts, had_error = [], False
    for line in log.read_text(errors="replace").splitlines():
        try: e = json.loads(line)
        except Exception: continue
        if e.get("timestamp"): ts.append(e["timestamp"])
        if e.get("error") or (e.get("part") or {}).get("error"): had_error = True
    if len(ts) >= 2:
        meta["elapsed_s"] = round((max(ts) - min(ts)) / 1000, 1)
    meta["exit_code"] = 1 if had_error else 0
    return meta


def rescue_stray_files(wd):
    """Move ROOT/solution/* into the run dir if the agent wrote to the wrong place."""
    stray = ROOT / "solution"
    if not stray.exists(): return
    dest = wd / "solution"; dest.mkdir(exist_ok=True)
    for f in stray.iterdir():
        t = dest / f.name
        if t.exists(): f.unlink()
        else: shutil.move(str(f), str(t))
    try: stray.rmdir()
    except OSError: pass


def extract_from_log(wd):
    """Fallback: parse results.json from the agent's last chat reply in the JSONL log."""
    log = wd / "opencode_output.jsonl"
    if not log.exists(): return None, None
    texts = []
    for line in log.read_text(errors="replace").splitlines():
        try: e = json.loads(line)
        except Exception: continue
        if e.get("type") == "text":
            t = (e.get("part") or e).get("text", "")
            if t: texts.append(t)
    if not texts: return None, None
    final = texts[-1]
    # Try ```json … ``` block first, then raw JSON from "t95_analytic_s" onward.
    blocks = list(re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", final, re.S))
    for m in blocks:
        try:
            c = json.loads(m.group(1))
            if "results" in c and "t95_analytic_s" in c["results"]:
                return _save_extracted(wd, c, final)
        except Exception: continue
    m = re.search(r'"t95_analytic_s"\s*:\s*[\d.]+', final)
    if m:
        try:
            raw = "{" + final[m.start():].split("```")[0].rstrip().rstrip("}") + "}"
            return _save_extracted(wd, {"agent_name": "(from chat)", "results": json.loads(raw)}, final)
        except Exception: pass
    return None, None


def _save_extracted(wd, results, raw):
    sol = wd / "solution"; sol.mkdir(exist_ok=True)
    (sol / "results.json").write_text(json.dumps(results, indent=2))
    md = sol / "solution.md"
    md.write_text("# Extracted from chat reply (agent did not write a file)\n\n" + raw)
    return results, md


def find_artifacts(wd):
    """Find results.json, plots, solution.md in a run dir (shallowest results.json wins)."""
    cands = sorted(wd.rglob("results.json"), key=lambda p: (len(p.parts), str(p)))
    results = None
    if cands:
        try: results = json.loads(cands[0].read_text())
        except Exception: pass
    fallback_md = None
    if results is None:
        results, fallback_md = extract_from_log(wd)
    plots = {n: f[0] for n in PLOTS if (f := sorted(wd.rglob(n)))}
    mds = sorted(wd.rglob("solution.md"))
    return results, plots, (mds[0] if mds else fallback_md)


def score_run(results, plots, sol_md, ref_t, ref_s):
    """Score one run per evaluation.md rules (max 20 pts)."""
    r = (results or {}).get("results", {})
    t95a, t95n = r.get("t95_analytic_s"), r.get("t95_numeric_s")
    s95a, s95n = r.get("s95_analytic_m"), r.get("s95_numeric_m")
    maxdev = r.get("max_v_deviation_ms")

    pts = {
        "a_derivation": 0,
        "b_t95": tier(abs(t95a - ref_t), T95_TIERS) if t95a is not None else 0,
        "c_s95": tier(abs(s95a - ref_s), S95_TIERS) if s95a is not None else 0,
        "num_t95": 2 if t95a is not None and t95n is not None and abs(t95n - t95a) < NUM_T95_TOL else 0,
        "num_s95": 2 if s95a is not None and s95n is not None and abs(s95n - s95a) < NUM_S95_TOL else 0,
        "num_maxdev": 2 if maxdev is not None and maxdev < MAXDEV_TOL else 0,
        "plots": 2 if set(plots) == set(PLOTS) and all(p.stat().st_size > MIN_PLOT for p in plots.values()) else 0,
    }
    if sol_md is not None:
        txt = sol_md.read_text(errors="replace").lower()
        if "tanh" in txt and any(k in txt for k in ("sqrt", "mg", "artanh")): pts["a_derivation"] = 4
        if any(p in txt for p in LIMIT_PATTERNS): pts["a_derivation"] += 2
    pts["total"] = sum(v for k, v in pts.items())

    metrics = {"t95_analytic_s": t95a, "t95_numeric_s": t95n, "s95_analytic_m": s95a,
               "s95_numeric_m": s95n, "max_v_deviation_ms": maxdev,
               "dev_t95_vs_ref_s": abs(t95a - ref_t) if t95a is not None else None,
               "dev_s95_vs_ref_m": abs(s95a - ref_s) if s95a is not None else None}
    return {"results": r, "metrics": metrics, "points": pts, "plots_found": sorted(plots)}


# ── HTML report ──────────────────────────────────────────────────────────────

CSS = """:root{--bg:#faf9f5;--panel:#ffffff;--panel2:#f4f1ea;--border:#e9e5dc;--border2:#dcd7cb;--txt:#262625;--muted:#6f6a61;--accent:#d97757;--accent-dark:#c15f3c;--grad:linear-gradient(135deg,#d97757 0%,#ec9a6d 60%,#f2b98a 100%);--codebg:#f4f1ea;--shadow:0 10px 30px rgba(38,38,37,.07)}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:'Inter',system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--txt);line-height:1.6;-webkit-font-smoothing:antialiased}
::selection{background:rgba(217,119,87,.25)}
.topnav{position:sticky;top:0;z-index:50;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.65rem 1.5rem;background:rgba(250,249,245,.88);backdrop-filter:blur(10px);border-bottom:1px solid var(--border)}
.brand{font-weight:800;font-size:1.02rem;color:var(--txt);text-decoration:none;display:flex;align-items:center;gap:.55rem;letter-spacing:-.01em}
.brand .dot{width:.8rem;height:.8rem;border-radius:50%;background:var(--accent);display:inline-block;box-shadow:0 2px 8px rgba(217,119,87,.45)}
.navlinks{display:flex;gap:1.1rem}
.navlinks a{color:var(--muted);text-decoration:none;font-weight:600;font-size:.88rem}
.navlinks a:hover{color:var(--accent-dark)}
.hero{background:linear-gradient(160deg,#262625 0%,#37332e 100%);color:#faf9f5;padding:4rem 1.5rem 4.4rem;text-align:center;position:relative;overflow:hidden}
.hero::after{content:"";position:absolute;inset:0;background:radial-gradient(640px 260px at 50% 125%,rgba(217,119,87,.3),transparent 70%);pointer-events:none}
.hero h1{margin:0;font-weight:800;font-size:clamp(1.9rem,4.5vw,2.8rem);letter-spacing:-.02em;color:#faf9f5}
.divider{display:flex;align-items:center;justify-content:center;gap:.8rem;margin:1.1rem 0 .9rem}
.divider span{height:2px;width:64px;background:rgba(250,249,245,.35);border-radius:2px}
.divider i{font-style:normal;font-size:1.05rem;color:var(--accent)}
.hero .lead{margin:0 auto;max-width:740px;color:rgba(250,249,245,.85);font-size:1.04rem}
.chips{display:flex;flex-wrap:wrap;gap:.5rem;justify-content:center;margin-top:1.5rem;position:relative;z-index:1}
.chip{background:rgba(250,249,245,.08);border:1px solid rgba(250,249,245,.25);color:#f5f2ec;border-radius:999px;padding:.32rem .95rem;font-size:.84rem;font-weight:600}
main{max-width:1080px;margin:0 auto;padding:2.6rem 1.5rem 3.5rem}
h2{font-weight:700;color:var(--txt);text-transform:uppercase;letter-spacing:.08em;font-size:.95rem;border-bottom:2px solid var(--border);padding-bottom:.55rem;margin:2.6rem 0 1.1rem}
a{color:var(--accent-dark)}
.tblwrap{overflow-x:auto;max-width:100%;border-radius:12px;border:1px solid var(--border);background:var(--panel);box-shadow:var(--shadow)}
table{border-collapse:collapse;margin:0;width:100%;min-width:480px}
th,td{padding:.55rem .85rem;text-align:left;border-bottom:1px solid var(--border)}
th{background:var(--panel2);color:var(--txt);font-weight:700;font-size:.86rem}
tbody tr:nth-child(even){background:#f7f5f0}
tbody tr:hover{background:#f6ede6}
tbody tr:last-child td{border-bottom:none}
.cmp td:first-child{font-weight:600}
.cmp tr.total td{background:rgba(217,119,87,.12);font-weight:800}
.card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:1.3rem 1.6rem;margin:1.5rem 0;box-shadow:var(--shadow)}
.card-head{display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;margin-bottom:.3rem}
.card-head h2{margin:0;border:none;padding:0;font-size:1.18rem;text-transform:none;letter-spacing:-.01em}
.pill{background:var(--accent);color:#fff;font-weight:700;font-size:.84rem;border-radius:999px;padding:.32rem .95rem;white-space:nowrap;box-shadow:0 3px 10px rgba(217,119,87,.3)}
.bar{position:relative;background:var(--codebg);border-radius:999px;height:1.7rem;margin:.6rem 0 1.1rem;overflow:hidden}
.fill{background:var(--grad);height:100%;border-radius:999px}
.barlabel{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.9rem;color:#fff;text-shadow:0 1px 3px rgba(0,0,0,.4)}
.plots{display:flex;gap:1.1rem;flex-wrap:wrap;margin:.9rem 0}
.plot{flex:1 1 320px;max-width:520px}
.plot img{width:100%;border:1px solid var(--border2);border-radius:12px;background:#fff;display:block;box-shadow:var(--shadow)}
.plot h4{margin:.2rem 0 .55rem;color:var(--muted);font-weight:600;font-size:.82rem;text-transform:uppercase;letter-spacing:.06em}
.meta{color:var(--muted);font-size:.85rem}
details{background:var(--codebg);border:1px solid var(--border);border-radius:10px;margin:.6rem 0;padding:.45rem .9rem}
summary{cursor:pointer;color:var(--accent-dark);font-weight:600}
pre{background:var(--codebg);padding:.9rem;border-radius:10px;overflow:auto;max-height:320px;font-size:.85rem}
code{color:var(--accent-dark);background:rgba(217,119,87,.09);padding:.05rem .35rem;border-radius:5px;font-size:.9em}
pre code{background:none;padding:0;color:var(--txt)}
.btn{background:var(--accent);border:none;color:#fff;padding:.5rem 1.1rem;border-radius:8px;cursor:pointer;font-size:.9rem;font-weight:700;font-family:inherit;box-shadow:0 4px 14px rgba(217,119,87,.3);transition:background .12s ease,transform .12s ease}
.btn:hover{background:var(--accent-dark);transform:translateY(-1px)}
.btn:focus-visible{outline:2px solid var(--accent-dark);outline-offset:2px}
.modal{position:fixed;inset:0;z-index:60;display:flex;align-items:center;justify-content:center;padding:1.2rem}
.modal[hidden]{display:none}
.modal-backdrop{position:absolute;inset:0;background:rgba(38,38,37,.5);backdrop-filter:blur(4px)}
.modal-dialog{position:relative;width:min(980px,100%);height:min(86vh,920px);background:var(--panel);border:1px solid var(--border2);border-radius:16px;display:flex;flex-direction:column;box-shadow:0 24px 70px rgba(38,38,37,.3)}
.modal-head{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.7rem 1rem;border-bottom:1px solid var(--border)}
.modal-title{font-weight:700;color:var(--txt);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.modal-actions{display:flex;gap:.45rem;align-items:center;flex-shrink:0}
.seg{background:var(--panel2);border:1px solid var(--border2);color:var(--txt);padding:.4rem .95rem;border-radius:8px;cursor:pointer;font-size:.85rem;font-weight:600;font-family:inherit}
.seg.active{background:var(--accent);color:#fff;border-color:transparent;box-shadow:0 3px 10px rgba(217,119,87,.3)}
.modal-close{background:var(--panel2);border:1px solid var(--border2);color:var(--muted);padding:.4rem .75rem;border-radius:8px;cursor:pointer;font-size:.85rem;font-weight:700;font-family:inherit}
.modal-close:hover{color:var(--txt)}
.modal-body{overflow:auto;padding:1.3rem 1.7rem;flex:1}
.md-raw{max-height:none;white-space:pre-wrap;word-break:break-word;margin:0;color:var(--txt)}
.md-view{max-width:840px;margin:0 auto;color:var(--txt)}
.md-view h1{font-size:1.45rem;border-bottom:1px solid var(--border);padding-bottom:.3rem;font-weight:800;color:var(--txt)}
.md-view h2{font-size:1.22rem;margin:1.7rem 0 .5rem;border-bottom:1px solid var(--border);padding-bottom:.2rem;text-transform:none;letter-spacing:0;color:var(--txt)}
.md-view h3{font-size:1.05rem;margin:1.3rem 0 .4rem;color:var(--txt)}
.md-view p{margin:.65rem 0}
.md-view ul,.md-view ol{padding-left:1.5rem;margin:.6rem 0}
.md-view li{margin:.25rem 0}
.md-view table{min-width:0;margin:.8rem 0;width:auto}
.md-view th,.md-view td{border:1px solid var(--border2)}
.md-view blockquote{border-left:3px solid var(--accent);margin:.9rem 0;padding:.15rem 1rem;color:var(--muted);background:rgba(217,119,87,.06);border-radius:0 6px 6px 0}
.md-view hr{border:none;border-top:1px solid var(--border);margin:1.3rem 0}
.md-view img{max-width:100%;border-radius:6px}
.md-view pre{max-height:440px}
.md-view .katex{font-size:1.06em}
.katex-display{overflow-x:auto;overflow-y:hidden;padding:.35rem 0}
footer{border-top:1px solid var(--border);padding:1.6rem 1.5rem 2.4rem;text-align:center;color:var(--muted);font-size:.85rem}
@media (max-width:640px){.modal{padding:.4rem}.modal-body{padding:1rem}.hero{padding:3rem 1rem 3.4rem}.navlinks{gap:.7rem}}"""

# Modal markup injected once per page; JS renders solution.md with marked + KaTeX (CDN, SRI-pinned).
# If the CDN is unreachable, the viewer falls back to the raw markdown in <pre>.
MODAL = """<div class="modal" id="md-modal" hidden>
<div class="modal-backdrop" data-close></div>
<div class="modal-dialog" role="dialog" aria-modal="true" aria-label="solution.md preview">
<div class="modal-head"><span class="modal-title">solution.md</span>
<div class="modal-actions">
<button type="button" class="btn seg active" data-view="rendered">✓ Rendered</button>
<button type="button" class="btn seg" data-view="raw">Raw</button>
<button type="button" class="btn modal-close" data-close title="Close (Esc)">✕</button>
</div></div>
<div class="modal-body"><div class="md-view"></div><pre class="md-raw" hidden></pre></div>
</div></div>"""

JS = r"""(function(){
"use strict";
// Protect $...$, $$...$$, \(...\), \[...\] from the markdown parser (underscores etc. inside
// math would otherwise be mangled), then restore them and let KaTeX auto-render typeset them.
var MATH_RE=/(\$\$[\s\S]+?\$\$)|(\\\[[\s\S]+?\\\])|(\\\([\s\S]+?\\\))|(\$[^\n$]+?\$)/g;
var SLOT_RE=/MATHSLOT(\d+)XEND/g;
var DELIMS=[{left:"$$",right:"$$",display:true},{left:"\\[",right:"\\]",display:true},
            {left:"\\(",right:"\\)",display:false},{left:"$",right:"$",display:false}];
function renderMarkdown(src){
  if(!window.marked||typeof window.marked.parse!=="function")return null;
  var store=[];
  var ph=src.replace(MATH_RE,function(m){store.push(m);return "MATHSLOT"+(store.length-1)+"XEND";});
  var out;
  try{out=window.marked.parse(ph,{gfm:true,breaks:false});}catch(e){return null;}
  return out.replace(SLOT_RE,function(_,i){return store[+i];});
}
var modal,mTitle,mView,mRaw,lastFocus=null;
function setSeg(which){
  var segs=modal.querySelectorAll(".seg");
  for(var i=0;i<segs.length;i++)segs[i].classList.toggle("active",segs[i].getAttribute("data-view")===which);
  mView.hidden=(which!=="rendered");
  mRaw.hidden=(which!=="raw");
}
function openModal(srcEl,title){
  var raw=srcEl.textContent||"";
  mTitle.textContent=title;
  mRaw.textContent=raw;
  var html=renderMarkdown(raw);
  mView.innerHTML=html||"";
  if(html!==null&&window.renderMathInElement){
    try{window.renderMathInElement(mView,{delimiters:DELIMS,throwOnError:false});}catch(e){}
  }
  setSeg(html!==null?"rendered":"raw");
  lastFocus=document.activeElement;
  modal.hidden=false;
  document.body.style.overflow="hidden";
  var c=modal.querySelector(".modal-close");if(c)c.focus();
}
function closeModal(){
  modal.hidden=true;
  document.body.style.overflow="";
  if(lastFocus&&lastFocus.focus)lastFocus.focus();
}
function init(){
  modal=document.getElementById("md-modal");
  if(!modal)return;
  mTitle=modal.querySelector(".modal-title");
  mView=modal.querySelector(".md-view");
  mRaw=modal.querySelector(".md-raw");
  var btns=document.querySelectorAll(".md-open");
  for(var i=0;i<btns.length;i++)(function(btn){
    btn.addEventListener("click",function(){
      var src=document.getElementById(btn.getAttribute("data-src"));
      if(src)openModal(src,btn.getAttribute("data-title")||"solution.md");
    });
  })(btns[i]);
  var closers=modal.querySelectorAll("[data-close]");
  for(var j=0;j<closers.length;j++)closers[j].addEventListener("click",closeModal);
  var segs=modal.querySelectorAll(".seg");
  for(var k=0;k<segs.length;k++)segs[k].addEventListener("click",function(){setSeg(this.getAttribute("data-view"));});
  document.addEventListener("keydown",function(e){if(e.key==="Escape"&&modal&&!modal.hidden)closeModal();});
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();"""

POINT_LABELS = [("a_derivation", "(a) Derivation (6)"), ("b_t95", "(b) t95 (3)"),
                ("c_s95", "(c) s95 (3)"), ("num_t95", "num↔ana t95 (2)"),
                ("num_s95", "num↔ana s95 (2)"), ("num_maxdev", "max_v_dev (2)"),
                ("plots", "Plots (2)"), ("total", "TOTAL (20)")]


def _card(run, ref_t, ref_s, assets):
    sc, m, p = run["score"], run["score"]["metrics"], run["score"]["points"]
    s = run["slug"]
    imgs = ""
    for n in PLOTS:
        src = run.get("plot_paths", {}).get(n)
        if src and Path(src).exists():
            shutil.copy(src, assets / f"{s}_{n}")
            imgs += f'<div class="plot"><h4>{n}</h4><img src="assets/{s}_{n}"></div>'
    sol_html = ""
    if run.get("solution_md") and Path(run["solution_md"]).exists():
        shutil.copy(run["solution_md"], assets / f"{s}_solution.md")
        md = Path(run["solution_md"]).read_text(errors="replace")[:200_000]
        src_id = f"mdsrc-{s}"
        sol_html = (f'<p style="margin:.8rem 0"><button type="button" class="btn md-open" data-src="{src_id}" '
                    f'data-title="solution.md — {html.escape(run["model"])}">📄 View solution.md (rendered)</button></p>'
                    f'<div id="{src_id}" hidden>{html.escape(md)}</div>')
    d95 = abs(m["t95_numeric_s"] - m["t95_analytic_s"]) if m["t95_numeric_s"] is not None and m["t95_analytic_s"] is not None else None
    d95s = abs(m["s95_numeric_m"] - m["s95_analytic_m"]) if m["s95_numeric_m"] is not None and m["s95_analytic_m"] is not None else None
    dev_ok = "OK" if m["max_v_deviation_ms"] is not None and m["max_v_deviation_ms"] < MAXDEV_TOL else "FAIL"
    mrows = (f"<tr><td>t95 analytic [s]</td><td>{fmt(m['t95_analytic_s'])}</td><td>{ref_t}</td><td>{fmt(m['dev_t95_vs_ref_s'])}</td></tr>"
             f"<tr><td>t95 numeric [s]</td><td>{fmt(m['t95_numeric_s'])}</td><td>—</td><td>num↔ana: {fmt(d95)}</td></tr>"
             f"<tr><td>s95 analytic [m]</td><td>{fmt(m['s95_analytic_m'],4)}</td><td>{ref_s}</td><td>{fmt(m['dev_s95_vs_ref_m'],4)}</td></tr>"
             f"<tr><td>s95 numeric [m]</td><td>{fmt(m['s95_numeric_m'],4)}</td><td>—</td><td>num↔ana: {fmt(d95s)}</td></tr>"
             f"<tr><td>max_v_deviation [m/s]</td><td>{fmt(m['max_v_deviation_ms'],10)}</td><td>&lt;0.05</td><td>{dev_ok}</td></tr>")
    hdr = "".join(f"<th>{l}</th>" for _, l in POINT_LABELS)
    cells = "".join(f"<td>{p[k]}</td>" for k, _ in POINT_LABELS)
    pct = p["total"] / MAX_PTS * 100
    rj = json.dumps(sc["results"], indent=2) if sc["results"] else "{}"
    tk = run.get("tokens", {})
    tok_str = (f"{run.get('tokens_total', 0):,} total "
               f"(in {tk.get('input', 0):,} / out {tk.get('output', 0):,} / "
               f"reason {tk.get('reasoning', 0):,} / cache {tk.get('cache_read', 0):,}+{tk.get('cache_write', 0):,})")
    return f"""<div class="card"><div class="card-head"><h2>{html.escape(run['model'])}</h2><span class="pill">{p['total']} / {MAX_PTS} pts</span></div>
<div class="bar"><div class="fill" style="width:{pct:.1f}%"></div><span class="barlabel">{p['total']} / {MAX_PTS} points</span></div>
<div class="tblwrap"><table class="metrics"><tr><th>Metric</th><th>Value</th><th>Reference</th><th>Deviation</th></tr>{mrows}</table></div>
<div class="tblwrap"><table class="points"><tr>{hdr}</tr><tr>{cells}</tr></table></div>
<p class="meta">⏱ {run['elapsed_s']}s · 🪙 {tok_str} · 💰 ${run.get('cost_usd', 0):.4f} ·
Exit {run['exit_code']} · Log: <code>{html.escape(run['log'])}</code> · Plots: {html.escape(', '.join(sc['plots_found']) or 'none')}</p>
<div class="plots">{imgs}</div>
<details><summary>results.json</summary><pre>{html.escape(rj)}</pre></details>{sol_html}</div>"""


def build_website(runs, ref_t, ref_s):
    WEB_DIR.mkdir(exist_ok=True)
    assets = WEB_DIR / "assets"; assets.mkdir(exist_ok=True)
    cards = "".join(_card(r, ref_t, ref_s, assets) for r in runs)
    if len(runs) >= 2:
        r1, r2 = runs[0], runs[1]
        p1, p2 = r1["score"]["points"], r2["score"]["points"]
        rows = ""
        for k, l in POINT_LABELS:
            cls = ' class="total"' if k == "total" else ""
            rows += f"<tr{cls}><td>{l}</td><td>{p1[k]}</td><td>{p2[k]}</td></tr>"
        rows += (f"<tr><td>Tokens (total)</td><td>{r1.get('tokens_total', 0):,}</td><td>{r2.get('tokens_total', 0):,}</td></tr>"
                 f"<tr><td>Time [s]</td><td>{r1.get('elapsed_s', 0)}</td><td>{r2.get('elapsed_s', 0)}</td></tr>"
                 f"<tr><td>Cost [USD]</td><td>${r1.get('cost_usd', 0):.4f}</td><td>${r2.get('cost_usd', 0):.4f}</td></tr>")
        cmp = f'<table class="cmp"><tr><th>Criterion</th><th>{html.escape(r1["model"])}</th><th>{html.escape(r2["model"])}</th></tr>{rows}</table>'
    else:
        cmp = "<p>Only one run available — comparison needs two models.</p>"
    page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Skydiver Benchmark — AI model comparison via OpenRouter + OpenCode: analytical vs numerical solutions of a physics problem.">
<title>Skydiver Benchmark — Model Comparison</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css" integrity="sha384-nB0miv6/jRmo5UMMR1wu3Gz6NLsoTkbqJghGIsx//Rlm+ZU03BU6SQNC66uf4l5+" crossorigin="anonymous">
<style>{CSS}</style>
<script defer src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js" integrity="sha384-/TQbtLCAerC3jgaim+N78RZSDYV7ryeoBCVqTuzRrFec2akfBkHS7ACQ3PQhvMVi" crossorigin="anonymous"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js" integrity="sha384-7zkQWkzuo3B5mTepMUcHkMB5jZaolc2xDwL6VFqjFALcbeS9Ggm/Yr2r3Dy4lfFg" crossorigin="anonymous"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js" integrity="sha384-43gviWU0YVjaDtb/GhzOouOXtZMP/7XUzwPTstBeZFe/+rCMvRwr4yROQP43s0Xk" crossorigin="anonymous"></script>
</head><body>
<nav class="topnav"><a class="brand" href="#"><span class="dot"></span>Skydiver Benchmark</a>
<div class="navlinks"><a href="#comparison">Comparison</a><a href="#details">Details</a><a href="https://github.com/51moon/skydiver_ai_benchmark">GitHub ↗</a></div></nav>
<header class="hero">
<h1>🪂 Skydiver Benchmark</h1>
<div class="divider"><span></span><i>✦</i><span></span></div>
<p class="lead">How well do different AI models solve a physics problem end-to-end — analytically and numerically — and cross-check the two against each other?</p>
<div class="chips"><span class="chip">t95,ref = {ref_t} s</span><span class="chip">s95,ref = {ref_s} m</span><span class="chip">max score = {MAX_PTS} pts</span><span class="chip">generated {datetime.now():%Y-%m-%d %H:%M:%S}</span></div>
</header>
<main>
<h2 id="comparison">Comparison</h2><div class="tblwrap">{cmp}</div>
<h2 id="details">Details per model</h2>{cards}
</main>
<footer>Generated by <code>run_benchmark.py</code> · Skydiver AI Benchmark · <a href="https://github.com/51moon/skydiver_ai_benchmark">source on GitHub</a></footer>
{MODAL}
<script>{JS}</script>
</body></html>"""
    (WEB_DIR / "index.html").write_text(page)
    print(f"Website written: {WEB_DIR / 'index.html'}")


TIMEOUT_S = 600


def main():
    ap = argparse.ArgumentParser(description="Skydiver AI-agent benchmark")
    ap.add_argument("--build-only", action="store_true", help="rebuild website from existing runs/")
    args = ap.parse_args()

    ref_t, ref_s = parse_references()
    print(f"References: t95,ref = {ref_t} s, s95,ref = {ref_s} m")

    runs = []
    if args.build_only:
        runs = []
        for wd in sorted(RUNS_DIR.glob("*")):
            if not wd.is_dir(): continue
            runs.append({"model": wd.name, "slug": wd.name, "workdir": str(wd), **parse_log_meta(wd)})
    else:
        for model in DEFAULT_MODELS[:2]:
            try:
                run = run_model(model, TIMEOUT_S)
                rescue_stray_files(RUNS_DIR / slug(model))
            except subprocess.TimeoutExpired:
                print(f"TIMEOUT for {model}", file=sys.stderr)
                run = {"model": model, "slug": slug(model),
                       "workdir": str(RUNS_DIR / slug(model)),
                       "exit_code": "timeout", "elapsed_s": TIMEOUT_S, "log": ""}
            runs.append(run)

    for run in runs:
        wd = ROOT / run["workdir"]
        results, plots, sol_md = find_artifacts(wd)
        run["score"] = score_run(results, plots, sol_md, ref_t, ref_s)
        run["plot_paths"] = {k: str(v) for k, v in plots.items()}
        run["solution_md"] = str(sol_md) if sol_md else None
        run["tokens"], run["cost_usd"] = parse_usage(wd)
        t = run["tokens"]
        run["tokens_total"] = t["input"] + t["output"] + t["reasoning"]
        print(f"{run['model']}: {run['score']['points']['total']}/{MAX_PTS} pts "
              f"(t95a={run['score']['metrics']['t95_analytic_s']}, s95a={run['score']['metrics']['s95_analytic_m']}) "
              f"· {run['tokens_total']:,} tok · ${run['cost_usd']:.4f} · {run['elapsed_s']}s")

    build_website(runs, ref_t, ref_s)
    summary = {"generated": datetime.now().isoformat(timespec="seconds"),
               "ref_t95_s": ref_t, "ref_s95_m": ref_s,
               "runs": [{"model": r["model"], "points": r["score"]["points"],
                         "metrics": r["score"]["metrics"], "tokens": r["tokens"],
                         "tokens_total": r["tokens_total"], "cost_usd": r["cost_usd"],
                         "elapsed_s": r["elapsed_s"]} for r in runs]}
    (WEB_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    print("Done. Summary: docs/summary.json")


if __name__ == "__main__":
    main()
