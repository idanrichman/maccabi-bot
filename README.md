# maccabi-bot
Checks for available appointments for maccabi health care

on macos. type `crontab -e` and insert this line
`*/20 7-22 * * * cd ~/Documents/maccabi-bot && ./run_maccabi.sh`

* make sure `run_maccabi.sh` is executable (with `chmod +x`)
then to check type: `crontab -l`
