# SEPC: Software Engineering Programming Community

The problem-solving leaderboard of the Department of Software Engineering, UFTB.

```
SEPC/
├── backend/     Flask + SQLite   (PythonAnywhere)
├── frontend/    React + Vite     (Vercel)
└── doc/         ei file + API.md
```

Default login: **se@uftb.com / UFTB_SE@02** (change it in Settings after your first login).

---

## 1. Local e chalano (5 minute)

### Backend
```bash
cd backend
python -m venv venv
# Windows:  venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
python app.py
```
→ http://localhost:5000/api/health e `{"ok": true ...}` dekhabe. The database (`sepc.db`) is created automatically on the first run.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
→ http://localhost:5173. In dev mode the API URL comes from `frontend/.env.development` (`http://localhost:5000`).

### Test data
Login → **Settings** → **Load test data**. This adds 16 demo students (real public handles, e.g. tourist and lee215) with 60 days of generated history, so This Day / Last Week / Last Month / Growth / graphs all show data.
To see only your own data later, use **Clear test data** (it deletes only the demo students).
From a terminal: `python app.py demo`

---

## 2. PythonAnywhere (backend)

> Why the old project wasn't syncing: (1) in `app.py` the `if __name__ == "__main__"` block was commented out, so `python app.py sync` did nothing, and in `SYNC_MODE=queue` the sync stayed "queued" forever. (2) A free PythonAnywhere account can only reach sites on its allowlist: **codeforces.com** and **alfa-leetcode-api.onrender.com** are on it, but **leetcode.com and codechef.com are not**. The new code is built around both of these points.

### First-time setup
1. Push the code to GitHub. Then in a PythonAnywhere **Bash console**:
   ```bash
   git clone https://github.com/Irshad-11/SEPC.git SEPC
   cd SEPC/backend
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   (If `curl-cffi` fails to install, delete that line from requirements.txt. It's optional; Codeforces and LeetCode work without it.)
2. **Web** tab → *Add a new web app* → *Manual configuration* → Python 3.11.
3. **Virtualenv**: `/home/<username>/SEPC/backend/venv`
4. Open the **WSGI configuration file**, delete everything in it, and paste this:
   ```python
   import sys
   path = "/home/<username>/SEPC/backend"
   if path not in sys.path:
       sys.path.insert(0, path)
   from app import app as application
   ```
5. **Reload** → `https://<username>.pythonanywhere.com/api/health` → you should see `"on_pythonanywhere": true, "server_platforms": ["codeforces", "leetcode"]`.

### Updates later
```bash
cd ~/SEPC && git pull
```
Then Web tab → **Reload**. That's it.

### Daily automatic sync (optional, free account e 1ta task)
**Tasks** tab → Daily, time `17:50` (UTC = 23:50 Dhaka):
```
cd /home/<username>/SEPC/backend && venv/bin/python app.py sync
```

### How sync works (no thread, no queue)
Settings → **Sync now**. The browser keeps calling `/api/sync/step`. Each call fetches a few accounts (~5 seconds' worth) and returns log lines. The log shows which account was fetched, how many were solved, how long it took, and **the exact reason for any error** (for example, "Blocked by PythonAnywhere proxy…"). Keep the page open until it finishes. If you close the tab midway, it's marked "stopped" after 3 minutes, and Sync now starts again.

---

## 3. Local fallback: one command (`local_sync.py`)

On PythonAnywhere free, CodeChef and Beecrowd can't be fetched (and if LeetCode/Codeforces ever fail too), so run this on your own PC:

```bash
cd backend
venv\Scripts\activate            # or: source venv/bin/activate
python local_sync.py             # fetches all 4 platforms and pushes them to PythonAnywhere
python local_sync.py codechef beecrowd     # only these two
```
- It sends data to `BACKEND_URL` in `backend/.env` (default `https://MahbubSifat.pythonanywhere.com`).
- The `INGEST_SECRET` in your local `.env` must match the one on the server (since it's the same `.env` file, it already does).
- **Beecrowd** needs `pip install playwright` once, plus Brave or Chrome installed. `beecrowd.py` is unchanged and works as before (if the Cloudflare check appears, click it once).
- Each push shows up in Settings → Recent syncs as `local:<platform>`.

**Run it automatically every day:**
- Simplest: `python local_sync.py --daily 23:30` (keep the window open)
- Windows Task Scheduler → Action: `C:\path\SEPC\backend\venv\Scripts\python.exe`, Arguments: `local_sync.py`, Start in: `C:\path\SEPC\backend`
- Linux cron: `30 23 * * * cd /path/SEPC/backend && venv/bin/python local_sync.py`

---

## 4. Vercel (frontend)

1. Vercel → New Project → import the GitHub repo.
2. **Root Directory: `frontend`**. Framework: Vite (auto-detected). Build command `npm run build`, output `dist`.
3. Deploy. There are no env variables to set. The API URL comes from `frontend/.env.production`.
   If your PythonAnywhere username is different, change this one line:
   `VITE_API_URL=https://<username>.pythonanywhere.com`
4. `vercel.json` sends every URL (`/student/5`, `/settings`…) to `index.html`, so a refresh never shows a 404.

CORS: in `backend/.env`, `FRONTEND_ORIGINS=*`. Login uses a Bearer token (not cookies), so this is safe and works on any domain. To restrict it: `FRONTEND_ORIGINS=https://your-app.vercel.app,http://localhost:5173`

---

## 5. Using it

| Page | URL | Who |
|---|---|---|
| Leaderboard | `/` | everyone |
| Student profile | `/student/<id>` | everyone |
| Login | `/login` | — |
| Manage Student | `/manage` | logged-in users: add/edit/delete students, Excel bulk import |
| Settings | `/settings` | sync + log, test data, login users, password |

- **Solved | Rank**: Solved = problems solved in the selected period (the small number = that platform's total). Rank = contest rating (Codeforces + LeetCode + CodeChef added together), with the change in that period. Beecrowd shows its own site rank.
- **Growth** = compared with the previous period of the same length (This Day vs the day before, Last Week vs the week before…).
- The highest value in each platform column is marked in gold.
- **Developer role**: in Manage Student → Add/Edit → Role = Developer → a `</>` badge appears in the table and on the profile. The default is Student.
- **Photo**: if a student has no Photo URL, their Codeforces/LeetCode profile photo is used automatically after a sync. If there's none, a placeholder is shown.
- **Excel import**: Manage Student → *Excel template* → fill it in → *Bulk import* → preview → Import. If a Student ID already exists, that student is updated.
  Columns: `student_id, name, batch, department, email, avatar_url, github_url, linkedin_url, role, codeforces, leetcode, codechef, beecrowd` (aliases like `ID`, `CF`, `beecrowed` also work).
- **New login user**: Settings → Login users → Add (admin only). From a terminal: `python app.py add-user name@uftb.com PASSWORD developer`

### Quick tests from a terminal
```bash
python platforms.py codeforces tourist
python platforms.py leetcode lee215
python platforms.py codechef gennady.korotkevich
```

## 6. Files

**backend/**
- `app.py`: the whole API, database, sync, demo data
- `platforms.py`: Codeforces / LeetCode / CodeChef fetchers (with clear error messages)
- `beecrowd.py`: Beecrowd scraper (unchanged)
- `local_sync.py`: the local fallback
- `.env`: all settings and secrets (the same file works locally and on PythonAnywhere)

**frontend/src/**
- `pages/`: Leaderboard, Profile, Login, Manage, Settings
- `components/`: table, avatar + medal, chart, header, footer, logo, form
- `assets/`: department logo, medal/dev badges (SVG)
- `api.js`: API calls + ranking helpers

> ⚠️ `backend/.env` holds the secret keys. Keep the GitHub repo **private**. If you make it public, add `.env` to `backend/.gitignore` and on PythonAnywhere create `.env` by hand (copy-paste the same 6 lines).
