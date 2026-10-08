# Project instructions

This is source for a local Codex project navigator. Keep the user's Codex database and session files read-only. Store each user's project records in that user's own `.project-library/record.json`.

The current desktop integration is verified only on macOS. For Windows work, read `docs/windows-port.md`, run the read-only preflight first, and verify the actual installed desktop build before adapting selectors or native components. A reachable debug port alone is not a complete UI test.

Use an empty test project for validation. Avoid committing user data, machine-specific paths, generated files, or local configuration. Run relevant tests once after changes; inspect the real window for UI changes. Preserve enough error context to explain failed connections.

The official plugin UI is under `experimental/project-navigator/`. `npm run setup` generates machine-local plugin configuration under ignored `data/`; do not hard-code developer paths or project IDs. macOS has a launcher/install workflow; Windows and Linux have a plugin/service setup path, but desktop integration still requires platform-specific acceptance. Do not identify a draft project-field readback as successful routing: verify the actual working directory and project of a user-submitted test chat.

When checking desktop updates, prioritize the six compatibility areas in `docs/Codex更新兼容检查.md`: network routing, image upload bridges, navigation, record maintenance, context settings, and launcher/icon integration. Check only features enabled on the actual machine; distinguish static contracts from real-use acceptance.
