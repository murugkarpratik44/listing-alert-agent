# Quick start: Claude Code

About 15 minutes. For people who use Claude Code in a terminal, an IDE or the desktop app's **Code** tab. If you use Claude at claude.ai, see [quickstart-claude-app.md](quickstart-claude-app.md).

## What you need

- Claude Code v2.1.275 or later, signed in with a Claude Pro, Max, Team or Enterprise plan. Routines need a claude.ai sign-in, not an API key.
- Python 3.10+ with PyYAML (`pip install pyyaml`). Without it, Claude follows the same rules by hand, more slowly.
- The Gmail account that receives your listing-site alerts.
- A GitHub account.
- Optional: a free [openrouteservice.org](https://openrouteservice.org) key.

## 1. Create your private state repository

Use the [state template](https://github.com/murugkarpratik44/listing-alert-agent-state-template): **Use this template → Create a new repository → Private**. Clone it:

```bash
git clone https://github.com/<your-github-name>/my-listing-alerts.git
cd my-listing-alerts
```

## 2. Connect Gmail

Gmail is a claude.ai connector. Connect it once at [claude.ai/customize/connectors](https://claude.ai/customize/connectors). Claude Code sessions signed in with the same account can then use it.

## 3. Install the plugin

In a session:

```text
/plugin install listing-alert-agent --marketplace murugkarpratik44/listing-alert-agent
```

Claude Code asks you to confirm the new marketplace, then shows what the plugin adds. Choose **Install for you (user scope)**.

From your shell instead (Claude Code v2.1.292 or later):

```bash
claude plugin install listing-alert-agent --marketplace murugkarpratik44/listing-alert-agent
```

Check it worked: type `/listing-alert-agent:` and the plugin's skills appear.

The state template's `.claude/settings.json` also turns the plugin on for that repository, so Claude Code offers to install it when you trust the folder.

## 4. Add your travel-time key (optional)

Put the key in your shell environment, not in any file in the repository:

```bash
export ORS_API_KEY=<your key>
```

The plugin reads it only during setup, to build the travel-time table, and never writes it to a file.

## 5. Run setup

```text
/listing-alert-agent:setup
```

Or ask: "Set up listing alerts using this repository." Setup:

1. interviews you;
2. shows you how to create saved-search alerts on each site you use ([how-to/set-up-site-alerts.md](how-to/set-up-site-alerts.md));
3. builds the travel-time table;
4. writes and validates your settings;
5. sends a `[TEST]` alert;
6. commits to your repository.

## 6. Create the schedule

```text
/schedule
```

Give it the two prompts setup printed: the hourly alert run, and the weekly summary at the time you chose. Include both repositories and the Gmail connector. Details and the exact prompts: [how-to/create-the-schedule.md](how-to/create-the-schedule.md).

## 7. Day to day

| Command | Does |
|---|---|
| `/listing-alert-agent:run-alerts` | One alert pass now |
| `/listing-alert-agent:compare` | Two to five listings side by side |
| `/listing-alert-agent:viewing-pack` | Enquiry draft, questions, documents, red flags |
| `/listing-alert-agent:tune` | Rule changes suggested from your verdicts |
| `/listing-alert-agent:dashboard` | Create or refresh the private dashboard |
| `/listing-alert-agent:doctor` | Explain what is wrong when alerts stop |

Try the engine without Gmail on the pack's made-up emails:

```text
/listing-alert-agent:run-alerts --dry-run
```

## Update

```bash
claude plugin update listing-alert-agent@listing-alert-agent
```

Third-party marketplaces do not update automatically by default. To turn that on, open `/plugin`, go to the **Marketplaces** tab and choose **Enable auto-update**.

Sources: [Install and manage plugins](https://code.claude.com/docs/en/plugins/install) and [Routines](https://code.claude.com/docs/en/routines), checked 2026-10-17.
