# Horizon

Public GitHub Pages site for Horizon Daily, an AI-curated daily digest of tech and research news.

## What it is

- Static site published at `https://mizelan.github.io/Horizon/`; `index.html` carries the Jekyll-generated landing page and canonical URL.
- 22 daily pages at `2026/05/<DD>/summary.html`, covering 2026-05-09 through 2026-05-30. Pages are Korean digests, except `2026-05-28`, which is marked `LLM-native`.
- `index.html` links 21 of the 22 summaries; the remaining day is reachable by URL.
- Styling and behavior live in `assets/css/` and `assets/js/` (about 132 KB total), with favicons in `assets/images/`.
- The content is produced by the full pipeline in the separate `horizon-src` repository. This checkout is site-only: the deploy script records that `horizon` cannot run here (`No module named src`).

## Features

- Per-day ranked briefing with a numeric score and score reason for every item.
- Source tabs and compact item lists, a date menu with per-day counts, and collapsible non-curated sections.
- Static HTML for each day, so GitHub Pages serves the archive without a build step in this repository.

## Tools

| Tool | What it does |
|---|---|
| `deploy-horizon-2026-05-28-29.sh` | Checks 2026-05-28/29 files, prints canonical `horizon analysis record` commands for a full source checkout, and prints the git deploy steps |
| `assets/css/horizon.css`, `style.css` | Site theme and GitHub Pages base styles |

There is no `package.json`, Makefile, or test suite in this repository.

## Layout

| Path | Contents |
|---|---|
| `2026/05/<DD>/summary.html` | One generated daily briefing per day |
| `index.html` | Landing page |

## Run

Serve or open the static site directly; GitHub Pages publishes the repository root.

```bash
open index.html
```

To regenerate content, run the CLI from a full `horizon-src` checkout, as the deploy script instructs:

```bash
cd /path/to/horizon-src && source .venv/bin/activate
horizon analysis record --date 2026-05-29 --source "llm-native /horizon-deploy skill" \
  --score 9.5 --topic "horizon-deploy skill + GlobalSkills canonical" \
  --tags "LLM-native,GlobalSkills,SQLiteSSOT,identical-schema"
```

To print the deployment steps for the two most recent pages:

```bash
./deploy-horizon-2026-05-28-29.sh
```

## Status

The archive ends at 2026-05-30 and `index.html` links 21 of the 22 pages. Deployment requires the full source checkout; the site-only checkout cannot run the Horizon CLI.
