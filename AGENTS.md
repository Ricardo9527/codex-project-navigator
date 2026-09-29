# Project instructions

This is source for a local Codex project navigator. Keep the user's Codex database and session files read-only. Store each user's project records in that user's own `.project-library/record.json`.

The current desktop integration is verified only on macOS. For Windows work, read `docs/windows-port.md`, run the read-only preflight first, and verify the actual installed desktop build before adapting selectors or native components. A reachable debug port alone is not a complete UI test.

Use an empty test project for validation. Avoid committing user data, machine-specific paths, generated files, or local configuration. Run relevant tests once after changes; inspect the real window for UI changes. Preserve enough error context to explain failed connections.
