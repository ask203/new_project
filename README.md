# RoomSplit (Splitwise-like for roommates)

A locally deployable expense-sharing app inspired by Splitwise.

## Features in v1
- Roommate/user management
- Group creation
- Expense splitting: equal, exact amount, percentage, and shares
- Settle-up payments
- Current balances and simplified debt suggestions
- Monthly spend analytics with category breakdown chart
- SQLite storage (easy local hosting)

## Run locally (home Wi-Fi)
1. Install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Start server:
   ```bash
   python app.py
   ```
3. Open from devices on same Wi-Fi:
   - `http://<your-computer-lan-ip>:5000`
   - Example: `http://192.168.1.23:5000`

## Free deployment options (internet-access)

### Option A: Render (free tier)
1. Push this repo to GitHub.
2. Create a **Web Service** on Render.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add persistent disk if possible (or move to free Postgres/Supabase).

### Option B: Fly.io (generous free allowance)
1. Install flyctl and run `fly launch`.
2. Add `gunicorn` and set start command.
3. Attach volume for SQLite or use managed Postgres.

### Option C: Oracle Cloud Always Free VM
1. Host with Docker + Nginx + HTTPS.
2. Run app as systemd service.
3. Add Tailscale for secure private access.

## Hardening before public deployment
- Add authentication + invitation links
- Add HTTPS and custom domain
- Move DB to Postgres
- Add backups and audit logs
- Add export/import and notifications

## Next enhancements to match Splitwise more closely
- Recurring expenses
- Expense editing and delete audit trail
- Attach receipts/images
- Multi-group dashboard and filters
- Currency support and exchange rates
- Email/WhatsApp settlement reminders
