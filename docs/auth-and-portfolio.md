# Accounts, broker linking and portfolio: shared contract

Real user accounts replace the offline demo login. Signed-in users can link **Upstox** and/or
**Zerodha** accounts (read-only) and see a Portfolio dashboard with InvestIQ scores.

## Security rules (non-negotiable)

- Passwords: `crypto.scrypt` (N=16384, r=8, p=1, 64-byte key) with a random 16-byte salt per user;
  compare with `crypto.timingSafeEqual`. Never log or return password hashes.
- Sessions: HS256 JWT signed with `AUTH_JWT_SECRET` (built with Node `crypto`, no new packages),
  payload `{ sub: userId, email, iat, exp }`, 7-day expiry. Sent as `Authorization: Bearer <token>`;
  the frontend keeps it in `localStorage.token` (as today).
- Broker access tokens are encrypted at rest with AES-256-GCM using `BROKER_TOKEN_KEY`
  (64 hex chars = 32 bytes); store iv + auth tag + ciphertext. Never return them to the browser.
- InvestIQ never sees broker passwords: users log in on Upstox's / Zerodha's own page (OAuth-style).
- **Read-only**: only profile, holdings, positions and funds endpoints are called. No order,
  GTT, conversion or fund-transfer endpoint is ever called.
- OAuth `state` is signed (HMAC-SHA256 with `AUTH_JWT_SECRET`), contains the user id, purpose,
  a nonce and a 10-minute expiry, and is verified on callback.
- Basic brute-force protection on login (in-memory limit per IP+email; best effort on serverless).
- All SQL parameterised.

## Environment variables (backend)

| Name | Purpose |
|---|---|
| `AUTH_JWT_SECRET` | JWT + OAuth state signing (long random string) |
| `BROKER_TOKEN_KEY` | 64 hex chars, AES-256-GCM key for broker tokens |
| `FRONTEND_URL` | Where OAuth callbacks send the browser back, e.g. `http://127.0.0.1:5173` locally, the Vercel frontend URL in production |
| `UPSTOX_CLIENT_ID`, `UPSTOX_CLIENT_SECRET`, `UPSTOX_REDIRECT_URI` | Existing Upstox app (redirect `https://invest-backend.vercel.app/upstox/callback`) |
| `ZERODHA_API_KEY`, `ZERODHA_API_SECRET` | Kite Connect app (redirect URL in the Kite developer console: `https://invest-backend.vercel.app/brokers/zerodha/callback`) |

Missing broker env vars -> that broker's connect endpoint returns 503 `{ message: "Zerodha linking isn't configured yet" }`; the rest keeps working.

## Tables (created by the backend on first use, `CREATE TABLE IF NOT EXISTS`)

```sql
CREATE TABLE users (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,          -- stored lowercase
  username VARCHAR(80) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,          -- scrypt$<salt hex>$<key hex>
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_login_at DATETIME NULL
);

CREATE TABLE broker_connections (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  broker ENUM('upstox','zerodha') NOT NULL,
  broker_user_id VARCHAR(50) NULL,
  broker_user_name VARCHAR(120) NULL,
  access_token_enc TEXT NULL,                   -- AES-256-GCM, NULL after expiry/disconnect
  token_expires_at DATETIME NULL,               -- IST: Upstox 03:30 next day, Zerodha 06:00 next day
  connected_at DATETIME NOT NULL,
  last_synced_at DATETIME NULL,
  last_error VARCHAR(500) NULL,
  UNIQUE KEY uq_user_broker (user_id, broker)
);

CREATE TABLE portfolio_snapshots (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  broker ENUM('upstox','zerodha') NOT NULL,
  synced_at DATETIME NOT NULL,
  holdings JSON NOT NULL,      -- normalised holdings (below)
  positions JSON NOT NULL,
  funds JSON NULL,
  totals JSON NOT NULL,        -- {invested, current, pnl, day_change, count}
  KEY idx_user_time (user_id, synced_at)
);
```

Normalised holding: `{ symbol, isin, exchange, company_name, quantity, t1_quantity, average_price,
last_price, close_price, invested, current_value, pnl, pnl_pct, day_change, day_change_pct }`
(invested = qty x avg, current = qty x last; qty includes t1_quantity).
Normalised position: `{ symbol, exchange, product, quantity, average_price, last_price, pnl,
realised, unrealised }`. Funds: `{ available_cash, used_margin, total }` (best effort, nullable).

## API

Auth (`/auth`):
| Route | Body / result |
|---|---|
| `POST /auth/register` | `{ username, email, password }` (password >= 8 chars) -> `{ token, user }`; 409 if email exists |
| `POST /auth/login` | `{ email, password }` -> `{ token, user }`; 401 `{ message: "Invalid email or password" }` |
| `GET /auth/me` | -> `{ user }` (`{ id, username, email, created_at }`); 401 if token missing/invalid/expired |
| `PATCH /auth/me` | `{ username?, email? }` -> `{ user }`; 409 if email taken |
| `POST /auth/password` | `{ current_password, new_password }` -> `{ success: true }` |
| `DELETE /auth/me` | `{ password }` -> deletes user, broker connections (disconnecting them) and snapshots |

Brokers (`/brokers`, all require auth except callbacks):
| Route | Result |
|---|---|
| `GET /brokers` | `[{ broker, connected, broker_user_name, broker_user_id, token_valid, token_expires_at, connected_at, last_synced_at, last_error, configured }]` for both brokers |
| `POST /brokers/:broker/connect` | `{ url }` to open in the browser (signed state inside) |
| `GET /upstox/callback` (existing route) | Distinguishes state: the existing admin market-data login (unchanged behaviour) vs a user link (state purpose `link`). For a link: exchange code, save encrypted token + profile, run a first sync, redirect to `${FRONTEND_URL}/portfolio?linked=upstox` (or `?error=<short code>`) |
| `GET /brokers/zerodha/callback` | Kite redirects with `request_token`, `status` and our `state` (passed via Kite's `redirect_params`). Exchange with checksum SHA-256(api_key + request_token + api_secret), save, first sync, redirect as above |
| `POST /brokers/:broker/sync` | Fetch holdings, positions, funds with the stored token, save a snapshot -> `{ synced_at, totals }`; 409 `{ code: "TOKEN_EXPIRED" }` when the token has expired (user must reconnect) |
| `DELETE /brokers/:broker` | Invalidate the broker session (Kite `DELETE /session/token`; Upstox logout), delete the connection; `?delete_data=1` also deletes that broker's snapshots |

Portfolio:
| Route | Result |
|---|---|
| `GET /portfolio` | `{ connections: [...as /brokers], summary: { invested, current, pnl, pnl_pct, day_change, day_change_pct, holdings_count, last_synced_at }, holdings: [holding + { broker, company_id, name, sector, sector_slug, industry, growth_score, growth_label, rank_overall }], positions: [...], funds: { upstox, zerodha }, insights: { weighted_score, strong_count, weak_count, unrated_count, top_sector, top_sector_pct, sector_allocation: [{sector, value, pct}], flagged: [{symbol, risks}] }, history: [{ date, current, invested }] }` from each broker's latest snapshot (history = latest snapshot per day, last 180 days) |

Holdings are matched to `companies` by ISIN (fallback symbol) and to the latest `company_rankings` snapshot.

Broker APIs used (read-only):
- Upstox v2 (`Authorization: Bearer <token>`): `GET /v2/portfolio/long-term-holdings`,
  `GET /v2/portfolio/short-term-positions`, `GET /v2/user/get-funds-and-margin?segment=SEC`,
  `GET /v2/user/profile`; token via `POST /v2/login/authorization/token`; logout `DELETE /v2/logout`.
- Zerodha Kite Connect v3 (`X-Kite-Version: 3`, `Authorization: token <api_key>:<access_token>`):
  login `https://kite.zerodha.com/connect/login?v=3&api_key=...&redirect_params=<urlencoded state=...>`,
  `POST /session/token`, `GET /user/profile`, `GET /portfolio/holdings`, `GET /portfolio/positions`,
  `GET /user/margins`, logout `DELETE /session/token`.

## Frontend

- Remove the offline "accept any password" fallback from AuthContext; login/register/me/profile
  use the API; show real error messages. Profile edits go to `PATCH /auth/me`.
- Navbar + profile menu: "Portfolio" link when signed in.
- `/portfolio` (PrivateRoute): no linked brokers -> connect cards (Upstox, Zerodha) with a consent
  note ("read-only: InvestIQ can't place orders or move money; you log in on the broker's site;
  broker sessions expire daily"). Linked -> dashboard: summary cards, holdings table with InvestIQ
  score/label (row -> `/company/:symbol`), insights (weighted score, weak/strong counts, sector
  allocation, flagged holdings), positions tab, funds, value history chart, per-broker status chip
  (Synced 09:14 / Session expired -> Reconnect), Sync now, Disconnect (confirm dialog).
  Handles `?linked=` and `?error=` query params with a toast.
- Settings: Profile (API), Change password, Linked brokers (connect/disconnect), Delete account.
