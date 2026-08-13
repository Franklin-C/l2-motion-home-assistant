# L2 Motion Windows bridge

This bridge keeps Bluetooth on the Windows host and exposes only the verified L2 Motion bed commands to Home Assistant over the private LAN. It is intended for Home Assistant installations running inside VirtualBox, where Bluetooth USB passthrough is unreliable.

## Install

Close the L2 Motion phone app, then run from PowerShell:

```powershell
.\install.ps1
```

The installer creates an isolated Python environment, generates a 256-bit bearer token, writes its configuration under `%LOCALAPPDATA%\L2MotionBridge`, and starts a limited user-level scheduled task at Windows sign-in.

If Windows Firewall prompts for access, allow **Private networks** only. Home Assistant must be able to reach TCP port `8765` on this Windows computer.

## Desktop test app

With the bridge installed, launch the safe desktop tester with:

```powershell
.\.venv\Scripts\pythonw.exe .\test_app.py
```

It can scan for the bed and toggle only the under-bed light. It reads the protected bridge configuration locally and does not show the bearer token. Motor controls are intentionally excluded.

## API

All requests require `Authorization: Bearer <token>`.

- `GET /health` checks the bridge process without connecting to the bed.
- `POST /scan` performs a read-only scan for `HHC0051745CDEF`.
- `POST /command` accepts `{ "command": "home" }` and other verified one-shot commands.
- `POST /move` accepts `{ "section": "head", "direction": "up", "duration": 0.5 }`.
- `POST /profile` homes the bed and replays saved movement timings.

Motor durations are capped at 30 seconds. On release, the bridge sends the official app's five `$b` stop writes.
