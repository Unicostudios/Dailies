# ReelStreak — v1 (personal use)

Core loop: pick a topic → get a hook/body/cta script (Claude) → mark it shot →
the day counts toward the current month's "chapter". Missing a day doesn't
break anything retroactively — each calendar month is its own fresh chapter,
so a bad week doesn't tank your motivation to keep going (this is the
deliberate alternative to a fragile Duolingo-style streak — see chapters.py).

## Setup

1. Create a Supabase project. In the SQL editor, run `schema.sql`.
2. Enable Email or magic-link auth in Supabase Auth settings (simplest for solo use).
3. Copy `.env.example` to `.env` and fill in:
   - SUPABASE_URL, SUPABASE_SERVICE_KEY (Project Settings → API)
   - SUPABASE_JWT_SECRET (Project Settings → API → JWT Settings)
   - ANTHROPIC_API_KEY
4. `pip install -r requirements.txt`
5. `uvicorn app.main:app --reload`

## Auth flow (no frontend yet)

Since there's no UI yet, sign in via Supabase's client SDK or REST directly to
get an access_token, then pass it as `Authorization: Bearer <token>` on every
request below.

Quick way to get a token without writing a frontend: use Supabase's REST auth
endpoint directly, e.g.

```
curl -X POST 'https://<project>.supabase.co/auth/v1/token?grant_type=password' \
  -H "apikey: <anon_key>" \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}'
```

(You'll need to create yourself as a user first — Supabase dashboard → Authentication → Add user.)

## Endpoints

- `POST /scripts/generate` `{"topic": "..."}` → generates + saves a script
- `GET /scripts` → list your scripts
- `PATCH /scripts/{id}/status?status=shot` → mark shot/posted/discarded
- `POST /progress/log` `{"script_id": "..."}` → logs today as done in the current chapter
- `GET /progress/chapter` → current month's chapter progress (completed_days / total_days)

## Not built yet (intentionally, for v1)

- Frontend/UI — this is API-only right now
- Voice personalization from your past captions (you chose to skip for v1)
- Notifications/reminders
- Multi-user features (invites, leaderboards) — schema supports it via RLS,
  but nothing's built on top yet

## Suggested next step

Once you've used the API loop for a week or two as yourself, the next most
valuable thing is probably a minimal frontend (even a single-page Next.js app
or just a Streamlit-style dashboard) so you're not curling endpoints daily.
Say when you want that and we'll build it.
