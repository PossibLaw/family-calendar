# Family Calendar

Family Calendar turns activity files into Google Calendar events. Put an `.ics`
calendar file—or a supported Park District registration PDF—into the `inbox`
folder, and Family Calendar adds the events without creating a second copy every
time it runs.

You do not need to be a programmer. The **Start here** section walks through each
screen and tells you exactly what to click.

## What it does

- Reads standard `.ics` calendar files, including repeating events.
- Reads Active Communities/Park District PDFs that contain an official calendar link.
- Adds a popup reminder to events that do not already have one.
- Uses each event's permanent calendar ID to avoid duplicates.
- Updates an event when its details change.
- Adds every valid event in a trusted batch and reports anything it could not read.
- Never deletes a calendar event automatically.

## Important privacy warning

Family schedules can contain children's names, addresses, and routines.

**Create your family's copy as a private repository.** Do not upload real schedule
files, Google credentials, or addresses to a public repository or public fork. The
public Family Calendar repository contains only reusable code and fictional examples.

GitHub does not copy the template owner's Google secrets into your repository. Each
family connects its own Google account.

## Three ways to use Family Calendar

### 1. Tell your coding agent: “Add this schedule”

This is the simplest default. Give Codex, Claude, Gemini, or another coding agent the
private repository and attach or paste the schedule. The repository's `AGENTS.md`
tells it how to create stable events, remove booking secrets, run the checks, and
finish the sync. Your request to add the batch is the approval; nobody reviews dozens
of individual calendar entries.

Use this prompt:

> Read `AGENTS.md`, then add the attached schedule to my family calendar. Treat this
> request as approval for the whole batch. Preserve recurrences and local time zones,
> omit booking codes and unrelated personal information, add every valid event, and
> report only the items you could not place. Run the tests and complete the repository
> sync without asking me to approve each event.

Several family members can do this at once. Each source file is handled independently,
and calendar writes use stable IDs to prevent duplicates.

If you do not want automatic setup yet, the agent can instead create one `.ics` file
and import it through an already signed-in browser at **Google Calendar** →
**Settings** → **Import & export**. This one-time path needs no Google Cloud project.

### 2. Give the family calendar an email inbox

After the email option is enabled, anyone you trust can forward an `.ics` attachment
or supported registration PDF to a Gmail plus alias such as
`yourname+calendar@gmail.com`. Gmail delivers it to `yourname@gmail.com`; no second
mailbox is required.

The private repository checks that inbox every hour and can also be run immediately
from GitHub's **Actions** tab. Valid events are added automatically. Successfully
handled messages receive the `Family Calendar Processed` Gmail label. Messages with
no usable schedule receive `Family Calendar Needs Attention`; one bad message never
blocks later valid submissions.

### 3. Optional AI autopilot for ordinary emails and PDFs

Structured `.ics` files and supported PDFs do not need an AI API. To interpret the
body of an airline, hotel, school, or activity email—or an otherwise unsupported
text-based PDF—add an optional OpenAI, Anthropic, or Gemini API key. The scheduled
inbox processor then extracts valid events and adds them automatically.

A ChatGPT, Claude, or Gemini subscription is separate from API access. Autopilot is
optional; the coding-agent path above continues to work without an API key.

## Start here: automatic setup for a family

Allow about 20–30 minutes the first time. After setup, adding a schedule is simply:

1. Open your private Family Calendar repository.
2. Open the `inbox` folder.
3. Upload the new PDF or `.ics` file.
4. Wait for the green check mark under **Actions**.

If you want your coding agent to perform setup, give it the repository and say:

> Read `AI_SETUP.md` and set up Family Calendar for me. Keep credentials out of chat
> and Git, pause only when Google needs my consent, and finish by testing a dry run.

### Step 1: Make your private family repository

1. On the public Family Calendar page, click **Use this template**.
2. Click **Create a new repository**.
3. Give it a private name such as `smith-family-calendar`.
4. Under **Visibility**, select **Private**.
5. Click **Create repository**.

Use a template rather than a public fork for your real schedule. A template creates
a separate repository and lets you choose **Private**. GitHub's illustrated guide is
[Creating a repository from a template](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template).

### Step 2: Create the Google connection

Google requires each family to approve calendar access once.

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. At the top of the page, open the project menu and select **New Project**.
3. Name it `Family Calendar`, then click **Create**.
4. Open **APIs & Services** → **Library**.
5. Search for `Google Calendar API`, open it, and click **Enable**.
   If you want the family email inbox, also enable `Gmail API`.
6. Open **Google Auth Platform** → **Branding** and click **Get Started**.
7. Use `Family Calendar` for the app name and enter your own email addresses.
8. For a personal Gmail account, choose **External** as the audience.
9. Under **Audience**, add the Gmail account whose calendar you will use as a test user.
10. Open **Google Auth Platform** → **Clients**.
11. Click **Create Client** and choose **Desktop app**.
12. Name it `Family Calendar computer setup`, then click **Create**.
13. Download the JSON file. Rename it exactly `credentials.json`.
14. Return to **Google Auth Platform** → **Audience** and move the app from
    **Testing** to **In production** before relying on unattended syncing.

Google limits refresh tokens for an External app left in **Testing** to seven days.
Moving your personal app to production avoids that testing-only expiration, although
Google may continue to display an unverified-app warning. Review Google's
[OAuth app state guide](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview)
before sharing the OAuth app with anyone outside your family.

Google also maintains an illustrated
[Calendar API authorization guide](https://developers.google.com/workspace/calendar/api/quickstart/python).

### Step 3: Authorize your Google account

Install [Python 3.11 or newer](https://www.python.org/downloads/) if it is not already
on the computer. On Windows, select **Add Python to PATH** on the first installer
screen.

Download your private repository to your computer:

1. In GitHub, click the green **Code** button.
2. Click **Download ZIP**.
3. Open the downloaded ZIP file.
4. Move `credentials.json` into the unzipped Family Calendar folder.

Then open Terminal on macOS, or PowerShell on Windows, in that folder and paste the
commands for your computer.

**macOS or Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m family_schedule authorize
```

**Windows**

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install .
.venv\Scripts\python -m family_schedule authorize
```

A Google page opens. Select the calendar account and approve the requested access.
When it says Family Calendar is connected, return to the terminal. The program creates
a private file named `.env`.

Never email, upload, or commit `credentials.json` or `.env`.

### Step 4: Add the three private values to GitHub

Open `.env` with a text editor. It contains three lines. Add each value to your private
GitHub repository:

1. Open the repository on GitHub.
2. Click **Settings**.
3. In the left sidebar, click **Secrets and variables** → **Actions**.
4. On the **Secrets** tab, click **New repository secret**.
5. Add these names one at a time, copying only the text after the `=` sign:

   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REFRESH_TOKEN`

GitHub's illustrated reference is
[Using secrets in GitHub Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).

### Step 5: Turn on automatic syncing

Still on **Settings** → **Secrets and variables** → **Actions**:

1. Open the **Variables** tab.
2. Click **New repository variable**.
3. Enter `ENABLE_CALENDAR_SYNC` as the name.
4. Enter `true` as the value.
5. Save the variable.

The public template does nothing when this variable is absent. This prevents the
template itself, public forks, and ordinary pull requests from writing to a calendar.

### Step 6: Choose the calendar

The included `schedule.toml` uses `primary`, meaning the main calendar of the Google
account you authorized. Most families should leave it unchanged.

To use another calendar, edit the `id` line in `schedule.toml`. In Google Calendar,
open **Settings**, select the calendar, open **Integrate calendar**, and copy the
**Calendar ID**.

You can also change the default reminder:

```toml
[calendar]
id = "primary"
name = "Family Calendar"
timezone = "America/Chicago"
reminder_minutes = 30
```

### Step 7: Add your first schedule

1. Open your **private** family repository on GitHub.
2. Open the `inbox` folder.
3. Click **Add file** → **Upload files**.
4. Drop in an `.ics` file or supported registration PDF.
5. Click **Commit changes**.
6. Open the repository's **Actions** tab.
7. Open **Sync family calendar**. A green check mark means the sync finished.

The first run creates the events. Later runs skip unchanged events and update changed
ones. A normal push processes only the new or changed source batch, so unrelated
future imports do not continually overwrite a manual calendar correction or recreate
an event you deleted. The manual **Sync family calendar** workflow intentionally
reconciles every repository source when you need a full repair.

## Turn on the family email inbox

Complete the automatic calendar setup above first, then:

1. Choose a plus alias for the Gmail account you authorized, such as
   `yourname+calendar@gmail.com`.
2. Edit `schedule.toml`. Set `intake.address` to that alias. For a closed list, add
   exact sender addresses to `trusted_senders`. To accept anyone who knows the alias,
   set `allow_any_sender = true`.
3. Enable **Gmail API** in the same Google Cloud project.
4. Run the authorization command again with Gmail enabled:

   ```bash
   .venv/bin/python -m family_schedule authorize --with-gmail
   ```

   On Windows, use `.venv\Scripts\python` instead.
5. Replace the three existing Google repository secrets with the new `.env` values.
6. Under **Settings** → **Secrets and variables** → **Actions** → **Variables**, add
   `ENABLE_EMAIL_INTAKE` with the value `true`.
7. Forward a test `.ics` attachment to the alias. Run **Process family calendar inbox**
   from **Actions**, or wait for the hourly run.

Example configuration:

```toml
[calendar]
id = "primary"
name = "Family Calendar"
timezone = "America/Chicago"
reminder_minutes = 30

[intake]
address = "yourname+calendar@gmail.com"
trusted_senders = ["adult1@example.com", "adult2@example.com"]
allow_any_sender = false
```

## Turn on optional AI autopilot

Create an API key with the provider you choose. In the private repository's
**Settings** → **Secrets and variables** → **Actions**:

1. Add the repository secret `AI_API_KEY`.
2. Add the repository variable `AI_PROVIDER` with `openai`, `anthropic`, `gemini`, or
   `openrouter`.
3. Add the repository variable `AI_MODEL` using a current model ID from that provider.

For OpenRouter, create a key at [OpenRouter API Keys](https://openrouter.ai/settings/keys),
set `AI_PROVIDER` to `openrouter`, and copy an exact model slug from the
[OpenRouter model catalog](https://openrouter.ai/models) into `AI_MODEL`. The same
`AI_API_KEY` secret is used; no additional repository secret is needed.

The key is sent only to the selected provider. Email text is treated as untrusted data,
provider output is checked locally, unknown output fields are discarded, and API
errors never print the key. Autopilot keeps useful names, dates, times, flight numbers,
and locations while instructing the provider to omit confirmation numbers, loyalty
numbers, payment data, barcodes, and unrelated email text.

## Which files work?

### `.ics` files

Standard iCalendar files work best. Many schools, sports teams, lesson providers, and
registration sites have buttons labeled **Add to calendar**, **iCal**, or **Download
calendar**. Download that file and upload it to `inbox`.

Repeating rules inside the file are preserved. See the fictional
[`examples/weekly-activity.ics`](examples/weekly-activity.ics) file for an example.

### Registration PDFs

A PDF works automatically only when it contains an official Active Communities
calendar-download link hosted on `anprod.active.com`. Family Calendar extracts that
link, verifies the host, and downloads the official event data.

Without AI autopilot, other PDFs stop safely instead of guessing dates. Autopilot can
extract text-based PDFs, or a coding agent can convert them into `.ics` files.

## Easier manual option: no Google API setup

If automatic syncing feels like too much setup, Family Calendar can make one import
file for you. This option does not need Google credentials.

1. Put the schedule files inside the local `inbox` folder.
2. Install Family Calendar using the commands in Step 3, but do not run `authorize`.
3. Run:

   **macOS or Linux**

   ```bash
   .venv/bin/python -m family_schedule build
   ```

   **Windows**

   ```powershell
   .venv\Scripts\python -m family_schedule build
   ```

4. In Google Calendar, open **Settings** → **Import & export**.
5. Import `build/family-schedule.ics` into the calendar you want.

Do not import the same generated file repeatedly. Use automatic syncing if you want
safe, repeatable updates.

## Troubleshooting

### The workflow has a gray “skipped” result

The `ENABLE_CALENDAR_SYNC` repository variable is missing or is not exactly `true`.
Repeat Step 5.

For **Process family calendar inbox**, also confirm that `ENABLE_EMAIL_INTAKE` is
exactly `true`.

### “Missing Google OAuth environment variables”

One of the three GitHub secrets in Step 4 is missing or its name is misspelled. Secret
names use underscores and contain no spaces.

### Google says the app is not verified

For a personal app, Google may show an unverified-app warning. Confirm that the Cloud
project is the one you created and that the permission requested is Google Calendar
events. If the app is still in **Testing**, make sure your Google account is listed as
a test user under **Google Auth Platform** → **Audience**. Never publish your OAuth
client credentials.

### Sync worked for a week and then stopped

An External OAuth app left in **Testing** receives a refresh token that expires after
seven days. Move the app to **In production** under **Google Auth Platform** →
**Audience**, run `authorize` again, and replace the three GitHub secrets.

### “No .ics or .pdf schedule sources found”

The `inbox` folder has no supported file. Upload the source inside `inbox`, not beside
the folder.

### “PDF has no trusted Park District calendar feed”

The PDF does not contain a supported official calendar link. Look for an `.ics` or
**Add to calendar** download, use a coding agent, or configure AI autopilot.

### An email is labeled “Family Calendar Needs Attention”

The sender was not trusted, the attachment was unsupported, or the message contained
no event with a usable date and time. Correct `schedule.toml`, add AI autopilot, or
remove the label after fixing the source to retry it.

### The same activity appears twice

Family Calendar stops when Google returns ambiguous duplicate IDs, but duplicates can
already exist from old manual imports. Delete the extra copy in Google Calendar once,
then run the workflow again.

## Safety and privacy design

- OAuth values are read from GitHub Secrets or the ignored local `.env` file.
- Email polling is disabled until `ENABLE_EMAIL_INTAKE` is explicitly set to `true`.
- Senders must be listed or `allow_any_sender` must be deliberately enabled.
- Free-form text is sent to an AI provider only when all three AI settings are present.
- AI output is schema-checked and cannot copy arbitrary email fields into events.
- `credentials.json`, `.env`, build output, and private deployment files are ignored.
- Remote calendar downloads require HTTPS and an explicit host allow-list.
- Remote calendar downloads have a 5 MB limit and a 30-second timeout; local source
  files have a 20 MB limit.
- Event writes use stable iCalendar UIDs and private content hashes.
- Unknown PDFs fail before any Google Calendar write.
- The importer never deletes calendar events.

## For developers

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m family_schedule build
.venv/bin/python -m family_schedule sync --dry-run
.venv/bin/python -m family_schedule apply --dry-run
```

The main commands are:

- `authorize`: opens Google's authorization page and saves a private `.env` file.
- `build`: validates and combines schedule sources into one iCalendar file.
- `sync`: builds and applies one trusted batch; `--changed-since` limits a push to its
  new or modified sources.
- `process-inbox`: processes trusted Gmail batches and labels each message afterward.
- `apply --dry-run`: reports how many records would be processed without writing.
- `apply`: creates, updates, or skips Google Calendar events idempotently.

Contributions for additional registration providers, examples, accessibility, and
setup improvements are welcome.
