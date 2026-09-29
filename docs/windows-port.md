# Windows port: acceptance target

Adapt the existing project navigator to the installed Windows Codex desktop build. Begin with the read-only preflight; record the observed version and result. Use an empty Git project and disposable records for all behavior checks.

The macOS launcher, launchd service, Unix paths, `fcntl`, `open -a`, and Finder actions need Windows equivalents. Keep project data in each user's own project; use Windows file paths and Explorer for file reveal. Do not assume the current macOS React export names or DOM structure match Windows. Reuse shared backend, record rules, and UI code where they actually work.

The first usable version passes these checks on Windows:

1. A local user can install and start it without editing source paths by hand.
2. The project navigation entry opens the correct project and displays a card and its file preview.
3. A new chat started from a card belongs to that card's project and receives the intended context.
4. Closing navigation restores the original chat and its usable input area.
5. File preview, source-message navigation, and Explorer reveal point to the correct resource.
6. Project records, adoption decisions, and manual updates survive restart; no personal data is committed or sent elsewhere.

Run the relevant backend tests and inspect the real desktop window. Report any Codex-version dependency or behavior that could not be verified.
