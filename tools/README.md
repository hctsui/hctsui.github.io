# Website content manager

This tool adds bilingual records without changing the site's CSS or layout.

## Install in the repository

Copy these paths into the repository, preserving their folders:

- `tools/`
- `.github/workflows/update-site.yml`
- `index.html`
- `zh/index.html`

The two HTML files differ only by a hidden `data-entry-id` attribute on the current Upcoming item. It has no visual effect.

## Add an entry on macOS

Double-click:

`tools/run-site-manager.command`

The first launch creates a local Python environment and installs Beautiful Soup. Choose a record type, enter both English and Chinese data, and press **Save and update HTML**.

Supported types:

- Conference participation
- Talk
- Honor or award
- Academic visit

For conferences, talks, and visits, check **Show in Upcoming until the end date** when appropriate.

## Automatic rollover

`.github/workflows/update-site.yml` runs once per day. When today's date is later than an Upcoming entry's end date, the entry is removed from both homepages and inserted into the matching section:

- Conference participation → Conferences and workshops
- Talk → Presentations
- Academic visit → Academic visit
- Honor or award → Honors and Awards immediately

The workflow then commits the changed HTML files to the repository.

The current Number Theory Summer School entry is already registered. It remains in Upcoming through 2026-08-28 and moves to Conferences and workshops beginning 2026-08-29.

## Manual commands

```bash
python3 -m pip install -r tools/requirements.txt
python3 tools/site_manager.py --sync
```

Test rollover without waiting:

```bash
python3 tools/site_manager.py --sync --today 2026-08-29
```

List managed entries:

```bash
python3 tools/site_manager.py --list
```

## Important

Use the manager for new managed entries. Existing manually written records remain untouched. New records receive a `data-entry-id` attribute so repeated daily runs do not create duplicates.

## Push from the form

When the tool is running inside a cloned Git repository, **Save + push** stages only the managed content files, creates a commit, and pushes it to GitHub. Git must already be installed and authenticated. **Save locally** never runs Git commands.
