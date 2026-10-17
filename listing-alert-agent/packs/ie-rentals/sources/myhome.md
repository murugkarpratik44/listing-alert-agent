# MyHome.ie – setting up saved-search alerts

Status: tested 2026-10-16 · Terms of use checked 2026-10-16 · Sender confirmed: `notifications@myhome.ie`

The plugin never visits MyHome.ie. The user sets up saved searches and MyHome.ie emails new matches to the user's Gmail.

## Why email only

MyHome.ie's terms of use prohibit automated access to the site. Email alerts are a feature the site offers to signed-in users. Check the current terms yourself in the site footer before relying on this.

## Steps for the user

1. Sign in to MyHome.ie with the email address that Claude reads through the Gmail connector.
2. Go to **Rent** and choose the county from the county list. Do not type a place name into the web address: a plain name can match a place abroad (for example "roscommon" can resolve to Roscommon, Michigan). The county list gives the correct Irish area.
3. Narrow to a town if you want, then set bedrooms.
4. Leave the price open or slightly above your stretch limit; the plugin applies your budget tiers.
5. Select **Save search** (or **Create alert**) and choose **instant** email alerts.
6. Repeat for each county or town.

## Emails to ignore

`newsletter@myhome.ie` and other marketing emails are not alerts. They are not read and not labelled.

## If no alerts arrive

- Check Spam and Promotions; mark as "Not spam".
- Check the saved search is still active under your MyHome.ie account.
- The `doctor` skill warns after 72 hours without a MyHome.ie email.
