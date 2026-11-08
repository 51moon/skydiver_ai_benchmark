You are participating in the "Skydiver" AI-agent benchmark described in the attached task.md.
The file evaluation.md (next to task.md) contains the reference values and scoring tolerances. Do not use it.

WORKDIR = /home/olush/Nextcloud_xfiles/Maths_Physics_Coding/GitHub/ai_challenge/runs/openrouter-nvidia-nemotron-3-ultra-550b-a55b-free

IMPORTANT: Create ALL files using ABSOLUTE paths under WORKDIR, e.g. /home/olush/Nextcloud_xfiles/Maths_Physics_Coding/GitHub/ai_challenge/runs/openrouter-nvidia-nemotron-3-ultra-550b-a55b-free/solution/solution.md.
Do NOT rely on the shell's current directory and do NOT write anywhere outside WORKDIR.

Do the following:
1. Read task.md carefully.
2. Create the folder /home/olush/Nextcloud_xfiles/Maths_Physics_Coding/GitHub/ai_challenge/runs/openrouter-nvidia-nemotron-3-ultra-550b-a55b-free/solution/ containing:
   - `solution.md`  — full analytical derivation (a)-(c), incl. stationarity argument (limit t->infinity), exact t95 and s95, and s(t).
   - `skydiver.py`  — standalone numerical simulation (numpy/scipy/matplotlib allowed). It must write
     `results.json`, `velocity.jpg` and `position.jpg` into the SAME folder as the script (i.e. /home/olush/Nextcloud_xfiles/Maths_Physics_Coding/GitHub/ai_challenge/runs/openrouter-nvidia-nemotron-3-ultra-550b-a55b-free/solution/).
   - `results.json` — produced by running skydiver.py, schema exactly as in task.md section 4.
3. Run `python3 /home/olush/Nextcloud_xfiles/Maths_Physics_Coding/GitHub/ai_challenge/runs/openrouter-nvidia-nemotron-3-ultra-550b-a55b-free/solution/skydiver.py` so that /home/olush/Nextcloud_xfiles/Maths_Physics_Coding/GitHub/ai_challenge/runs/openrouter-nvidia-nemotron-3-ultra-550b-a55b-free/solution/results.json,
   /home/olush/Nextcloud_xfiles/Maths_Physics_Coding/GitHub/ai_challenge/runs/openrouter-nvidia-nemotron-3-ultra-550b-a55b-free/solution/velocity.jpg and /home/olush/Nextcloud_xfiles/Maths_Physics_Coding/GitHub/ai_challenge/runs/openrouter-nvidia-nemotron-3-ultra-550b-a55b-free/solution/position.jpg exist.
4. Finally run `find /home/olush/Nextcloud_xfiles/Maths_Physics_Coding/GitHub/ai_challenge/runs/openrouter-nvidia-nemotron-3-ultra-550b-a55b-free -type f -not -path '*/.git/*'` and confirm that
   /home/olush/Nextcloud_xfiles/Maths_Physics_Coding/GitHub/ai_challenge/runs/openrouter-nvidia-nemotron-3-ultra-550b-a55b-free/solution/ contains all 5 files.

At the end, reply with a short summary and the contents of results.json.