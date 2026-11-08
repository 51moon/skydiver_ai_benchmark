#!/usr/bin/env python3
"""
run_benchmark.py — "Skydiver" AI-agent benchmark comparing two models via OpenRouter/OpenCode.

  1. Reads task.md and evaluation.md (reference values + tolerances).
  2. Runs one `opencode run` agent per model in runs/<model>/.
  3. Scores each results.json against evaluation.md (max 20 points).
  4. Builds a self-contained HTML report at website/index.html.

Usage:
  python3 run_benchmark.py              # run default models
  python3 run_benchmark.py --build-only # rebuild website from existing runs/
"""

import argparse, html, json, re, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASK_FILE, EVAL_FILE = ROOT / "task.md", ROOT / "evaluation.md"
RUNS_DIR, WEB_DIR = ROOT / "runs", ROOT / "website"

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

CSS = """ body{font-family:system-ui,sans-serif;margin:2rem;background:#0f1420;color:#e8eaf2}
h1{color:#7cc7ff} table{border-collapse:collapse;margin:1rem 0}
th,td{border:1px solid #33405c;padding:.35rem .7rem;text-align:left} th{background:#1b2438}
.cmp td:first-child{font-weight:600}
.card{background:#161e30;border:1px solid #2a3652;border-radius:10px;padding:1rem 1.5rem;margin:1.5rem 0}
.bar{position:relative;background:#0c1220;border-radius:6px;height:1.6rem;margin:.5rem 0 1rem}
.fill{background:linear-gradient(90deg,#3fa9f5,#7cc7ff);height:100%;border-radius:6px}
.barlabel{position:absolute;inset:0;text-align:center;line-height:1.6rem;font-weight:700}
.plots{display:flex;gap:1rem;flex-wrap:wrap}
.plot img{max-width:480px;border:1px solid #33405c;border-radius:6px;background:#fff}
.meta{color:#9aa7c7;font-size:.85rem}
pre{background:#0c1220;padding:.8rem;border-radius:6px;overflow:auto;max-height:300px}
code{color:#7cc7ff}"""

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
        snip = html.escape(Path(run["solution_md"]).read_text(errors="replace")[:8000])
        sol_html = f'<details><summary>solution.md ({html.escape(s)})</summary><pre>{snip}</pre></details>'
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
    return f"""<div class="card"><h2>{html.escape(run['model'])}</h2>
<div class="bar"><div class="fill" style="width:{pct:.1f}%"></div><span class="barlabel">{p['total']} / {MAX_PTS} points</span></div>
<table class="metrics"><tr><th>Metric</th><th>Value</th><th>Reference</th><th>Deviation</th></tr>{mrows}</table>
<table class="points"><tr>{hdr}</tr><tr>{cells}</tr></table>
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
        rows = "".join(f"<tr><td>{l}</td><td>{p1[k]}</td><td>{p2[k]}</td></tr>" for k, l in POINT_LABELS)
        rows += (f"<tr><td>Tokens (total)</td><td>{r1.get('tokens_total', 0):,}</td><td>{r2.get('tokens_total', 0):,}</td></tr>"
                 f"<tr><td>Time [s]</td><td>{r1.get('elapsed_s', 0)}</td><td>{r2.get('elapsed_s', 0)}</td></tr>"
                 f"<tr><td>Cost [USD]</td><td>${r1.get('cost_usd', 0):.4f}</td><td>${r2.get('cost_usd', 0):.4f}</td></tr>")
        cmp = f'<table class="cmp"><tr><th>Criterion</th><th>{html.escape(r1["model"])}</th><th>{html.escape(r2["model"])}</th></tr>{rows}</table>'
    else:
        cmp = "<p>Only one run available — comparison needs two models.</p>"
    page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Skydiver Benchmark — Model Comparison</title><style>{CSS}</style></head><body>
<h1>🪂 Skydiver Benchmark — Model Comparison</h1>
<p>References: t95,ref = {ref_t} s · s95,ref = {ref_s} m · generated {datetime.now():%Y-%m-%d %H:%M:%S}</p>
<h2>Comparison</h2>{cmp}<h2>Details per model</h2>{cards}</body></html>"""
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
        runs = [{"model": wd.name, "slug": wd.name, "workdir": str(wd),
                 "exit_code": "?", "elapsed_s": 0, "log": ""}
                for wd in sorted(RUNS_DIR.glob("*")) if wd.is_dir()]
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
    print("Done. Summary: website/summary.json")


if __name__ == "__main__":
    main()
