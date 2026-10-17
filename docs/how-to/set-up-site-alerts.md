# Set up saved-search alerts on a listing site

The plugin only reads the alert emails a site sends you. It never opens the site. So the first job is yours: save a search on each site and switch on email alerts.

## General steps (any site)

1. **Sign in with the right email.** Use the email address that Claude reads through the Gmail connector.
2. **Search.** Pick locations from the site's own suggestions rather than typing them.
3. **Set only the filters you are sure of**, such as bedrooms or property type.
4. **Leave the price open, or set it a little above your stretch limit.** The plugin applies your budget tiers itself and tells you about near misses.
5. **Save the search and switch on email alerts.** Choose instant alerts where offered.
6. **Repeat for each separate area.**
7. **Tell Claude when you're done.** Setup records each site's exact sender address from the first alert that arrives.

## Site-specific steps

Each pack has a page per site, with the exact menu names and what to do if no alerts arrive:

| Pack | Site | Steps |
|---|---|---|
| Ireland rentals | Daft.ie | [sources/daft.md](../../listing-alert-agent/packs/ie-rentals/sources/daft.md) |
| Ireland rentals | MyHome.ie | [sources/myhome.md](../../listing-alert-agent/packs/ie-rentals/sources/myhome.md) |

## If no alerts arrive

- **Check where the emails land.** Look in Spam, Promotions and Updates. Mark the email "Not spam" and add the sender to your contacts.
- **Check the saved searches.** Open the site's saved-search list and confirm email alerts are on for each one.
- **Check the address.** Your account email on the site must match the Gmail account Claude reads.
- **Allow for quiet periods.** A narrow search may genuinely have no new listings for days. The `doctor` skill warns when a site has been silent longer than its `silence_hours` (48 hours by default).
- **Ask the site's support.** If listings appear on the site that should have matched but no email came, contact them.

## Why not just check the website?

Listing sites' terms of use generally forbid automated access, including scraping, crawling and software that browses for you. Alert emails are a feature the sites offer, sent to your own inbox, so reading them stays within normal use. Check each site's current terms yourself; they change.
