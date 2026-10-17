# Daft.ie – setting up saved-search alerts

Status: tested 2026-10-16 · Terms of use checked 2026-10-16

The plugin never visits Daft.ie. The user sets up saved searches on the site, and Daft.ie emails new matches to the user's Gmail. The plugin reads those emails.

## Why email only

Daft.ie's terms of use prohibit automated access to the site (scraping, crawling and similar). Email alerts are a feature the site offers to signed-in users, so reading them in your own inbox is within normal use. Check the current terms yourself in the site footer before relying on this; terms change.

## Steps for the user

1. Sign in to Daft.ie (create a free account if needed). Use the same email address that Claude reads through the Gmail connector.
2. Search "To Rent". Choose the location from the location box suggestions rather than typing a web address: Daft's location names are specific (for example the county town of Roscommon is "Roscommon Town, Roscommon") and a mistyped address shows an error page.
3. You can add several locations to one search. For a distance search around one town, pick the town and set the distance option.
4. Set the filters you are sure about, such as bedrooms. Leave price open or set it a little above your stretch limit: the plugin applies your budget tiers itself and will tell you about near misses.
5. Select **Save search** and switch on email alerts. Choose instant alerts if offered.
6. Repeat for each separate area.
7. Tell Claude when done. Setup records the exact sender address from the first alert email; until then any `@daft.ie` address is accepted and reported.

## If no alerts arrive

- Check Spam, Promotions and Updates in Gmail; mark the email as "Not spam" and add the sender to contacts.
- In Daft.ie, open **Saved searches** and check that email alerts are on for each search.
- Check the account email address matches the Gmail account Claude reads.
- Some searches produce few matches. The `doctor` skill warns after 48 hours without a Daft.ie email (`silence_hours` in `sources.yaml`).
