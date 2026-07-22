# UI translations (gettext)

The bot's UI strings live here as standard gettext catalogs, one per
language: `<lang>/LC_MESSAGES/messages.po` (source, edit this) compiles to
`<lang>/LC_MESSAGES/messages.mo` (binary, what the app actually reads at
runtime via `aiogram.utils.i18n`). This mirrors how the Telegram-Cars project
does UI i18n.

Keys are dot-paths (e.g. `booking.notification.accepted`) kept from the
project's previous JSON-based i18n system on purpose, so application code
never refers to gettext-specific concepts - `get_text("booking.notification.accepted", lang)`
and the `_("...")` closure injected by `I18nMiddleware` work exactly as
before (see `app/core/i18n/loader.py`).

## Editing a translation

1. Edit the `msgstr` for the relevant `msgid` in `<lang>/LC_MESSAGES/messages.po`
   directly (any text editor, or a PO editor like Poedit).
2. Recompile:
   ```bash
   cd backend
   pybabel compile -d locales -D messages
   ```
   (Docker images do this automatically at build time - see `Dockerfile`.)
3. Restart the bot (or rebuild the container) to pick up the new `.mo`.

## Adding a new key

Add a `msgid "your.new.key"` / `msgstr "..."` pair to **every** language's
`.po` file (missing keys fall back to displaying the raw key), then
recompile as above.

## Adding a new language

1. `mkdir -p locales/<lang>/LC_MESSAGES`
2. Copy an existing `messages.po`, translate every `msgstr`, keep every
   `msgid` identical.
3. Add `<lang>` to `SUPPORTED_LANGUAGES` in `backend/.env`.
4. Recompile as above.
