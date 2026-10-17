# Quick start: Claude app (web, desktop, mobile)

About 15 minutes. For people who use Claude at claude.ai or in the Claude desktop or mobile app. If you work in a terminal, see [quickstart-claude-code.md](quickstart-claude-code.md).

## What you need

- A Claude Pro, Max, Team or Enterprise plan. Scheduled runs (routines) need one of these.
- The Gmail account that receives your listing-site alerts.
- A GitHub account (free) to hold your settings and history in a private repository.
- Optional: a free [openrouteservice.org](https://openrouteservice.org) key for real travel times. Without it, setup can still run but travel times are left out.

## 1. Create your private state repository

1. Open the [state template](https://github.com/murugkarpratik44/listing-alert-agent-state-template).
2. Select **Use this template → Create a new repository**.
3. Name it, for example `my-listing-alerts`, and choose **Private**.

## 2. Connect Gmail and GitHub

1. In Claude, open **Customize → Connectors**.
2. Connect **Gmail** and **GitHub**.
3. When GitHub asks which repositories Claude may use, include the one you just created.

## 3. Add the plugin

1. Open **Customize → Plugins**.
2. Select **Add → Add marketplace** and enter `murugkarpratik44/listing-alert-agent`.
3. Find **Listing Alert Agent** in the list and select **Add**.

Once the plugin is in the plugin directory, you can also find it under **Discover** on the same page.

The plugin is added to your account, so it is also available in Claude Code on any computer where you sign in with the same account.

## 4. Run setup

In a new conversation, type:

> Set up listing alerts using my repository `<your-github-name>/my-listing-alerts`.

Setup asks about the following:

1. What you are looking for and by when.
2. Sizes, must-haves, nice-to-haves and deal-breakers.
3. The places that matter to you (work, school, family) and how often you travel there.
4. Which areas to watch.
5. Your budget, and whether you share costs.
6. When you want phone notifications and the weekly summary.
7. Which listing sites you use. It shows you how to create saved-search alerts on each one: [how-to/set-up-site-alerts.md](how-to/set-up-site-alerts.md).

It then:

- builds your travel-time table;
- writes your settings to your repository;
- sends you a `[TEST]` alert.

## 5. Create the schedule

Setup gives you two prompts, one for the hourly alert run and one for the weekly summary. Create them as routines at [claude.ai/code/routines](https://claude.ai/code/routines) and turn on push notifications. Step by step: [how-to/create-the-schedule.md](how-to/create-the-schedule.md).

## 6. Day to day

| You want to | Say to Claude |
|---|---|
| Check now instead of waiting for the hour | "Run my listing alerts now" |
| Put two to five listings side by side | "Compare Example Court and Riverside Mews" |
| Prepare for a viewing | "Viewing pack for Example Court" |
| Record a decision | "Not for me – too far" or "Mark Example Court as viewing" |
| Adjust your rules from your decisions | "Tune my alerts" |
| See an overview | "Create my listing dashboard" |
| Find out why alerts stopped | "Run the listing alert doctor" |

## What works where

Chat in the Claude app loads the plugin's skills, which is all the plugin needs. Its optional `alert-runner` agent is used only in Claude Code and in tasks on the desktop app, so nothing is lost without it. Source: [Plugin feature support across platforms](https://claude.com/docs/plugins/platform-support), checked 2026-10-17.

## Costs

The plugin is free. Runs use your Claude plan's usage, and scheduled runs count against your plan's limits. The openrouteservice free plan covers setup.
