# Windows preflight

Run `scripts/windows-preflight.ps1` on the Windows machine to check whether the locally installed Codex window and expected native UI modules are reachable. The script only inspects window structure and prints a short result; it does not read chat or project content.

From PowerShell in this repository:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows-preflight.ps1
```

If the result is `NO_DEBUG_PORT`, exit Codex normally. Then run `scripts/windows-start-for-test.ps1` to select the installed Codex executable, start it with local debugging enabled, and repeat the probe. Do not force-quit a running conversation.

`CONNECTABLE` confirms only the initial connection and shell structure. Continue with the actual page, card, composer, file action, and exit/restore checks in [Windows port](windows-port.md).
