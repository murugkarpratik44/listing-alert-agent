# State storage

Each user's settings and history live in storage they own. Three options; `profile.yaml` → `storage.type` records which one.

| Option | Best for | Scheduling | Notes |
|---|---|---|---|
| `github` (default) | Anyone with a GitHub account; cloud routines | Cloud routine, hourly | Full history in git; every run is a commit |
| `drive` | Users without GitHub | Cloud routine, hourly | Uses the Google Drive connector. Files are replaced by new versions; see the limits below |
| `local` | Claude Code or Cowork on the user's own computer | Desktop scheduled task (runs only while the computer is on and the app is open) | Put the folder inside Google Drive for desktop or OneDrive to back it up and see it on other devices |

Every option holds the same files (`config/`, `data/`, `SETUP-SUMMARY.md`), so a user can move between them by copying the folder.

## GitHub

The GitHub connector cannot create repositories, so the user does this once:

1. Open https://github.com/murugkarpratik44/listing-alert-agent-state-template
2. **Use this template → Create a new repository**, name it (for example `my-listing-alerts`), choose **Private**.
3. Give Claude access: GitHub → Settings → Applications → Installed GitHub Apps → Claude → Configure → Repository access → add the repository → Save. (Lesson from the first real setup: with "Only select repositories", a new repository is not included automatically.)

Each run: clone, run the engine in the clone, commit `Alert run <timestamp>: <n> reported`, fetch and rebase, push.

## Google Drive

### What the connector can and cannot do (checked 2026-10-17)

The Google Drive connector can create files, read and download them, and change a file's title or folder. It **cannot edit a file's content in place** and this plugin never deletes. So Drive storage works with versions:

- the current version of each file sits in the state folder;
- a run that changes a file uploads a new version and moves the old one into `archive/`;
- quiet runs (no listings, no unreadable emails, health already checked today) are not written at all (`--write-if-changed`), which keeps the archive to a handful of files a day. The user can empty `archive/` whenever they like.

CSV files are stored as CSV (no conversion), so Drive previews them as a table and "Open with Google Sheets" works.

### Create the folder (setup)

1. Create a folder named as the user chooses (default `Listing alerts`), with subfolders `config`, `data` and `archive`.
2. Upload the template files (from the plugin's state template) with `disableConversionToGoogleType: true` and the right content type (`text/plain` for YAML and Markdown, `text/csv` for CSV).
3. Record `storage: {type: drive, drive_folder: "<name>"}` in `profile.yaml`.

### Each run

1. Find the folder by name, then each current file by name inside `config` and `data` (ignore `archive`). If two files share a name, use the most recently modified and report it.
2. Download each file into a temporary local folder with the same layout and run the engine there, with `--write --write-if-changed`.
3. For each file the engine changed (compare before and after): upload the new version to the same subfolder, then move the previous version into `archive/` and rename it `<name> <timestamp>`.
4. Never delete anything.

## Local folder

1. The user creates or chooses a folder on their computer and connects it to Claude (Cowork "Add folder", or open it in Claude Code).
2. Copy the state template files into it.
3. Record `storage: {type: local, local_path: "<path>"}`.
4. Schedule with a desktop scheduled task using the run-alerts prompt from `scheduling.md`, pointing at the folder instead of a repository.

The engine reads and writes the folder directly; nothing is uploaded anywhere.

## Rules for every option

- Never write secrets.
- Never store landlord, agent or seller contact details.
- Append to `data/*.csv`; never rewrite history rows, except to correct an error the user agrees to, or when the engine adds new columns (it keeps all existing values).
