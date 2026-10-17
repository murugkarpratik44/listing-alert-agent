# Get instant notice with a Gmail filter

The plugin runs at most hourly. For the fastest notice, let Gmail flag a site's own alert the moment it arrives. The plugin's hourly email then adds the ranking, travel times and market comparison.

1. In Gmail on the web, select **Show search options** in the search box.
2. In **From**, enter the alert senders separated by ` OR `, for example `noreply@example-site.com OR alerts@other-site.com`. Use the exact addresses in your `config/sources.yaml`.
3. Select **Create filter**.
4. Tick these options:
   - **Never send it to Spam**
   - **Always mark it as important**
   - optionally **Star it**
5. Select **Create filter**.
6. In the Gmail phone app, set notifications to **High priority only** if you want only important mail to buzz.

The filter only marks the emails. It doesn't change what the plugin reads, and it doesn't affect the plugin's own labels, `Listing Alerts/Processed` and `Listing Alerts/Could not read`.
