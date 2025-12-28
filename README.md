# maccabi-bot
Checks for available appointments for Maccabi health care and sends Telegram notifications when earlier slots are found.

## Setup

1. Copy `config.example.yaml` to `config.yaml` and fill in your details
2. Make sure `run_maccabi.sh` is executable: `chmod +x run_maccabi.sh`
3. Install dependencies: `pip install -r requirements.txt`

## Running with Cron (macOS)

To automatically check for appointments, set up a cron job:

```bash
crontab -e
```

Add this line:
```
*/20 7-22 * * * cd ~/Documents/maccabi-bot && ./run_maccabi.sh
```

**What this schedule means:**
- `*/20` - runs every 20 minutes
- `7-22` - only between 7:00 AM and 10:40 PM
- `* * *` - every day of month, every month, every day of week

To verify the cron job is set:
```bash
crontab -l
```

## Disabling the Cron Job

When you no longer need the bot (e.g., appointment found), disable it:

```bash
crontab -e
```

Then either:
- **Comment out** the line by adding `#` at the beginning
- **Delete** the line entirely

Save and exit. Verify it's disabled with `crontab -l`.
