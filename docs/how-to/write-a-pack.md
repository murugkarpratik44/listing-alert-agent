# Add a country or listing type (write a pack)

A pack teaches the plugin about one country and one kind of listing:

- which sites send alert emails, and how users switch them on;
- how to read those emails;
- how to choose search places;
- optionally, open market averages.

The engine, scoring and emails stay the same.

## Steps

1. **Copy the template.** Copy `listing-alert-agent/packs/_template/` to `listing-alert-agent/packs/<country>-<domain>/`, for example `uk-rentals` or `ie-jobs`.
2. **Fill in `pack.yaml`.** Every path in it must exist.
3. **Check each site's terms of use.** Record the date in `terms_checked`. Leave out any site whose terms forbid reading its alert emails with software.
4. **Write the user steps** in `sources/<id>.md`: how to save a search and switch on email alerts, and what to do if none arrive.
5. **Write the parser notes** in `parsers/<id>.md`: where each listing field sits in the alert email. Mark the layout "to be confirmed" until you have seen real emails.
6. **Add a synthetic fixture email** that has the same structure as the real one. Its first line must start with `SYNTHETIC TEST EMAIL`. Add the listing JSON you expect from it in `fixtures/expected-extraction.json`.
7. **Optionally, add a benchmark file** from open data whose licence allows redistribution. Use the columns `location,property_type,bedrooms,value,n_periods`.
8. **Run the checks:**

   ```bash
   python tools/check_packs.py
   python -m unittest discover -s tests
   python tools/check_plugin_folder.py --write
   ```

9. **Open a pull request** using the "new pack" template.

The full rules and file reference are in [packs/_template/README.md](../../listing-alert-agent/packs/_template/README.md).

## Rules that are never relaxed

- **Email only.** A pack never tells Claude to visit, fetch or search a listing site.
- **No real personal data.** Never use names, phone numbers, email addresses or home addresses, in fixtures or anywhere else.
- **Date everything.** Every fact that can go out of date carries a checked date and a source link. The monthly maintenance check flags any older than 12 months.
