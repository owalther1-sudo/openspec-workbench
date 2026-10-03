# OpenSpec Workbench — local edition

## Start

1. Extract this ZIP.
2. Open a terminal in the extracted `openspec-workbench` folder.
3. Run one of these commands:

   macOS / Linux:
   ```sh
   python3 serve.py
   ```

   Windows:
   ```powershell
   py serve.py
   ```

4. Open **http://localhost:8765** in your browser.

Requires Python 3. No package installation, account, or internet connection is needed. Keep the terminal running while using the workspace. Press Ctrl+C to stop. If the port is busy, add `--port 8766` and open http://localhost:8766 instead.

## What works

- Issue kanban with drag-and-drop and editable plans
- Task checklists and progress
- Light, Dark, and System themes
- Quick, Balanced, and Deep thinking guidance in copied prompts
- Markdown import, reading, editing, and export
- Editable skill library and SKILL.md import/export
- Model-labelled conversations with pasted answers
- Review and summary handoffs between models

## Data and connections

Your workspace is saved in this browser's local storage. Use the same browser and URL each time. A different port or browser creates a separate workspace. Clearing browser data removes your saved workspace. Markdown and skills can be exported individually from the interface.

The hosted workspace and this local edition have separate storage; existing hosted edits do not transfer automatically. To bring documents and skills over, export them from the hosted workspace and import them locally.

The initial issues and conversation are sample data. Model selection does not call model APIs. Copy a prepared prompt into your chosen model's chat, then paste its answer back. Thinking complexity is prompt guidance, not a provider reasoning setting.

Connected repository files can be read and edited directly. Manually imported files remain browser-only and can be exported.

## Source

`index.html`, `style.css`, and `app.js` contain the complete UI. `serve.py` serves them on loopback only, so it does not expose the app to your network. The local edition uses system fonts and has no remote font dependency.

## Connected Git projects

Click **+ Project**, enter a name, and supply a Git URL or an existing checkout folder.

- **Local checkout:** enter the repository root (not its openspec subfolder). The app uses that folder directly, without copying the repository. The optional branch field is ignored; the current working tree is used.
- **Git URL:** HTTPS and SSH URLs work with your existing Git credential helper or SSH key. Authenticate in your terminal first (for example with your Git provider's CLI). Never put passwords or access tokens in the URL. The app keeps a persistent clone under `~/.openspec-workbench/repos`; Git URLs require a local checkout to read and edit files. Set `OPENSPEC_WORKBENCH_DATA` to change this location. An optional branch selects the initial clone branch.

Private repositories use the same credentials as your local Git installation. Interactive Git/SSH prompts are disabled in the server. If authentication fails, test `git ls-remote YOUR_URL` in your terminal and fix credentials there, or connect an existing checkout.

**Refresh checkout** reads the current openspec Markdown files, including external changes. **Pull from remote** performs a fast-forward-only pull and refresh; it refuses a dirty working tree. Commit or stash changes with your Git tools first. Nothing is committed or pushed automatically.

**Edit → Save to repository** writes an existing linked Markdown file directly to the checkout. It refuses to overwrite a file changed since it was loaded; refresh and edit again. Rename, create, and delete for repository files are not offered. New/manual files remain browser-only. Linked files cannot be removed through the UI.

Each `tasks.md` becomes an issue. Refresh and repository saves rebuild linked issue checklists from disk, preserving their IDs, while keeping manually created issues and conversations. Issue plan and board edits are workspace-only; edit the linked `tasks.md` to persist checklist changes. No background watcher is running: use Refresh to load changes.

Existing snapshot projects are preserved. To connect one, create a connected project with its checkout path. Empty openspec folders are supported. Limit: 400 Markdown files, 1 MB per file. Symlink files/folders are excluded. Start this app locally with `serve.py`; the connection is specific to this computer.
