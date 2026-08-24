# What runs here, and why

Three files. You never run any of them by hand.

## site-check.yml (in .github/workflows/)
Fires on every push to `main`. Four steps:
1. Rebuild `sitemap.xml` from the files that actually exist, stamping each
   URL with its real last-commit date.
2. Commit that sitemap back if it changed.
3. Run the checks below.
4. Tell IndexNow what changed, so Bing/Yandex/Seznam/Naver recrawl.

Results appear in the **Actions** tab. A red X emails you.

## check_site.py
Every check exists because that problem actually shipped or nearly did.

BLOCKS (red X):
- unclosed or mismatched HTML tags
- em-dashes in visible copy (house style; ignores HTML comments)
- TODO/FIXME/placeholder text left in visible copy
- the unprovisioned Kevin@RoseFinancialManagement.com address
- JSON-LD that does not parse
- broken internal links and missing assets
- absolute self-links in <a>/<img>/<script> (the bug that 404'd the
  booking button at cutover; canonical and og:url are exempt, those
  are supposed to be absolute)
- forms posting to mailto:
- internal documents sitting in the web root
- junk paths from unexpanded shell globs
- missing deploy files, or a wrong CNAME

WARNS (still passes):
- missing canonical, description, or image alt text
- pages missing the Plausible script (a partial install produces
  silently wrong data, which is worse than none)
- sitemap entries that do not match files on disk

## indexnow_ping.py
Reads the key file at the site root, reads every URL from sitemap.xml,
submits them in one call. Google does not participate in IndexNow.

## Turning it off
Delete site-check.yml, or Actions tab -> Site check -> disable workflow.
Nothing here can take the site down: GitHub Pages deploys independently.
