# JLCPCB Authentication Skill

## What this plugin provides

Three tools for authenticating with JLCPCB. Credentials are managed
securely — **you never see or handle the username or password**.

| Tool | When to call |
|---|---|
| `jlcpcb_login()` | Before any JLCPCB browser task that requires authentication |
| `jlcpcb_auth_status()` | To check if already logged in before redundant logins |
| `jlcpcb_logout()` | After completing a session if explicitly asked |

## Workflow pattern

```
1. jlcpcb_auth_status()           → check if already logged in
2. if not logged in: jlcpcb_login()
3. browser_navigate to target JLCPCB page
4. perform the task
5. jlcpcb_logout() (only if asked)
```

## Key facts

- `jlcpcb_login()` takes **no arguments** — do not try to pass credentials
- Login page: `https://passport.jlcpcb.com/#/login`
- The page is a JavaScript SPA — use `browser_snapshot` after navigation
- JLCPCB has two tabs on the login page: **Sign In** and **Create Account**
  The plugin automatically selects Sign In — you do not need to handle this
- Session persists in the browser for ~1 hour; `jlcpcb_auth_status` tracks age
- If login fails, the tool returns `{status: "error", message: "..."}` — report
  the message to the user but do not retry more than twice

## Common tasks

**Place an order:**
```
jlcpcb_auth_status → jlcpcb_login → browser_navigate("https://jlcpcb.com/quote") → ...
```

**Check order history:**
```
jlcpcb_login → browser_navigate("https://jlcpcb.com/order") → browser_snapshot → ...
```

**Upload Gerber files:**
```
jlcpcb_login → browser_navigate("https://jlcpcb.com/quote") → browser_snapshot → ...
```

## If credentials are not configured

The tools return a clear error message. Direct the user to the
**JLCPCB Auth** panel in the Hermes dashboard to set credentials.
