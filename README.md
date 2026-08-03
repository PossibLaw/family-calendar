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
- Stops for review if an input is unsupported or ambiguous.
- Never deletes a calendar event automatically.

## Important privacy warning

Family schedules can contain children's names, addresses, and routines.

**Create your family's copy as a private repository.** Do not upload real schedule
files, Google credentials, or addresses to a public repository or public fork. The
public Family Calendar repository contains only reusable code and fictional examples.

GitHub does not copy the template owner's Google secrets into your repository. Each
family connects its own Google account.

## Choose the path that fits your family

You have two good options:

- **Fastest: use a coding agent and import once.** Ask an agent to turn the schedule
  into an `.ics` file, review its event summary, and import it through a browser that
  is already signed in to Google Calendar. You do not need Python, Google Cloud, OAuth,
  or a running Family Calendar app.
- **Best for ongoing family use: automatic syncing.** One person completes the Google
  Cloud setup below once. After that, family members can submit schedule details from
  ChatGPT or GitHub without downloading files or installing anything.

### Fastest path: coding agent and browser import

This is the same approach used for the first real Family Calendar deployment: a
coding agent created a reviewed iCalendar file, then imported it through an already
signed-in Google Calendar browser session. No Google credentials were placed in the
repository.

1. Give the coding agent this repository's URL and your schedule source. Use a private
   agent workspace when the source contains real family information.
2. Ask it to create a standards-compliant `.ics` file with stable UIDs, correct local
   time zones, locations, recurrence rules, and reminders.
3. Ask for a plain-language event list and review every date, time zone, location, and
   assumption before approving the import.
4. If the agent can control a browser you have already signed in to, allow it to open
   Google Calendar and perform the import. Otherwise, save the `.ics` file and open
   **Google Calendar** → **Settings** → **Import & export** → **Import**.
5. Choose the destination calendar, select the `.ics` file, and click **Import**.

You can start with this prompt:

> Use the Family Calendar repository at `[repository URL]` as your guide. Convert the
> attached or pasted schedule into one validated `.ics` file. Preserve recurring
> events, use the event's local time zone, add a 30-minute reminder, and use stable
> unique UIDs. List every event and any uncertainty for my approval before importing.
> Do not include account credentials, booking codes, loyalty numbers, payment data,
> or unrelated personal information.

Google's browser import is a one-time import, not a two-way connection. Do not import
the same file repeatedly, because Google may create duplicates. Use the automatic
setup below when several people will contribute schedules or when existing events
need safe updates.

## Start here: automatic setup for a family

Allow about 20–30 minutes the first time. After setup, adding a schedule is simply:

1. Open your private Family Calendar repository.
2. Open the `inbox` folder.
3. Upload the new PDF or `.ics` file.
4. Wait for the green check mark under **Actions**.

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
ones. Removing a file does not remove events from Google Calendar.

## Add a schedule without downloading anything

After automatic syncing is configured, a family member can contribute from a locked
down work computer using ChatGPT or GitHub. The repository must be private, and the
person—or their coding agent—must have access to it.

### Example: add a work flight and hotel through ChatGPT

1. In the itinerary, copy only the facts that belong on the family calendar: traveler
   name if needed, airline and flight number, departure and arrival airports, local
   dates and times, hotel name and address, and check-in/check-out dates.
2. Do not paste a boarding-pass barcode, QR code, reservation or ticket number,
   loyalty number, passport information, payment details, or the entire confirmation
   email. Everyone with access to the family calendar may see event details.
3. Open a coding-agent session from ChatGPT (such as Codex) and give it write access
   to the **private** family repository. Never send a real itinerary to the public
   template repository. If your ChatGPT session cannot write to GitHub, use the
   GitHub-only path below.
4. Paste the sanitized itinerary with the prompt below.
5. Have the agent create a branch, add an `.ics` file under `inbox`, run the repository
   checks, and open a pull request. It should stop and ask about ambiguous dates or time
   zones instead of guessing.
6. Review the agent's plain-language event summary. When it is correct, merge the pull
   request. The private repository's GitHub Action will sync the events.
7. Confirm the flight and hotel entries in Google Calendar.

Example prompt:

> In my private Family Calendar repository, add the work trip below. Create
> `inbox/work-trip-YYYY-MM.ics` on a new branch and open a pull request. Add separate
> events for each flight leg and the hotel stay. Use each airport's local time zone,
> include useful addresses, stable unique UIDs, and a 30-minute reminder. Exclude
> confirmation numbers, loyalty numbers, barcodes, payment data, and unrelated email
> text. Show me the proposed event list and mark anything unclear as `UNCONFIRMED`.
> Do not merge or write to Google Calendar until I approve.

### If the person can use GitHub but not ChatGPT

1. Open the private repository's **Issues** tab and create a new issue titled
   `Calendar request: work trip`.
2. Paste the same sanitized facts and identify any uncertain time zones.
3. Ask a family administrator or a coding agent with repository access to convert that
   private issue into an `.ics` pull request.
4. Review and merge the pull request; the automatic sync then adds the events.

Creating an issue alone does **not** add anything to Google Calendar. This deliberate
review step prevents untrusted free-form text from writing directly to the family
schedule.

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

Other PDFs stop safely instead of guessing dates. Export those activities as `.ics`,
or add a new provider parser through a contribution.

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
**Add to calendar** download from the activity provider.

### The same activity appears twice

Family Calendar stops when Google returns ambiguous duplicate IDs, but duplicates can
already exist from old manual imports. Delete the extra copy in Google Calendar once,
then run the workflow again.

## Safety and privacy design

- OAuth values are read from GitHub Secrets or the ignored local `.env` file.
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
.venv/bin/python -m family_schedule apply --dry-run
```

The main commands are:

- `authorize`: opens Google's authorization page and saves a private `.env` file.
- `build`: validates and combines schedule sources into one reviewed iCalendar file.
- `apply --dry-run`: reports how many records would be processed without writing.
- `apply`: creates, updates, or skips Google Calendar events idempotently.

Contributions for additional registration providers, examples, accessibility, and
setup improvements are welcome.
