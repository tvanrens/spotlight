# Ideas That Matter — research spotlight website

A responsive static website featuring recent Warwick outputs, longer readable summaries, source links, and an automatically changing weekly spotlight. Includes GitHub Actions workflows for monthly updates and weekly email drafts for LinkedIn, X and Bluesky.

## Preview

Run `python -m http.server 8000` from this folder and open http://localhost:8000. The site needs an HTTP server to fetch its JSON. Images use external Unsplash URLs as topical illustrations; they **are not figures from the original papers**. Confirm licensing and replace with approved images before public deployment. If an image fails to load, its background stays neutral.

## Publish

1. Create a GitHub repository and upload all files **including `.github/workflows/`**. Enable GitHub Pages (Settings → Pages → Deploy from a branch → `main` / root). Set the repository **Actions variable** `SITE_URL` to the public Pages URL, e.g. `https://YOUR-USERNAME.github.io/research-spotlight`.
2. Enable Actions workflows in the repository. `monthly-refresh.yml` runs on the 1st of each month (07:15 UTC), retrieves records from the Warwick profile with Playwright, preserves articles already written, discards records older than two years, and commits changes. The site reads the latest JSON automatically. A dynamic weekly spotlight changes based on the current UTC date every Monday without editing the HTML or redeploying.
3. Add the repository **secret** `OPENAI_API_KEY` to enable drafting new 500–1,000-word articles. Without it, new items appear only as clearly marked metadata briefs; **no unsupported results are invented**. Generated articles carry `ai-draft-needs-review` and should be fact-checked before treating them as published communications. The bot does not overwrite initial reviewed summaries. The generator intentionally skips sources where it cannot obtain enough evidence.
4. To email weekly posts to **tvanrens@gmail.com**, add repository secrets `SMTP_HOST`, `SMTP_PORT` (default 465), `SMTP_USERNAME`, `SMTP_PASSWORD`, optionally `EMAIL_FROM`. For a Gmail sender, use `smtp.gmail.com` port `465` with an appropriately secured Gmail app password or a transactional SMTP provider. Never commit credentials. `weekly-social.yml` runs Mondays at 08:00 UTC, emails three platform-specific **drafts** and the feature link, and does not automatically post to social media.
5. Run both workflows manually once from GitHub → Actions to verify network access, scraper parsing and email credentials. Scheduled GitHub Actions may be delayed; sending cannot be guaranteed to occur at an exact minute.

## Current contents and limitations

The initial snapshot covers items dated **14 October 2024 through 14 October 2026** found on page one of the Warwick profile. Four outputs have original 500–1,000 word source-grounded editorial features in `data/articles.json`. Nine additional items have short descriptions with transparent 'full feature pending' status. Some entries only link to the outlet's home page where the precise deep link was unavailable; replace these with permanent URLs before launch. Several output types (media coverage, presentations or proceedings) overlap; the monthly scraper tries to deduplicate by DOI/title.

The live Warwick pages are rendered in JavaScript and can change structure: parsing and pagination are best-effort, and site terms, access controls, limits and robots guidance should be respected. This starter is not a promise of 100% crawl coverage. A monthly run that cannot access source text **retains existing entries** rather than inventing new articles. Source text is sent to an OpenAI API account only if `OPENAI_API_KEY` is supplied; review the applicable publisher permissions and your data handling before enabling.

The weekly featured rotation uses only records that have a full article. All indexed outputs are still visible as tiles; incomplete entries are transparently labelled as briefs.

## Publishing control

For a researcher's public-facing website, a useful safety step is to require editorial review before publishing machine-drafted features. The sample monthly job commits drafts automatically, but it marks them for review. To instead enforce approval, change the monthly workflow to create a pull request rather than push directly to `main`.

## Editorial approval (updated October 2026)

The **monthly-refresh** workflow now prepares a pull request rather than pushing changes to the public branch. Under **GitHub → Pull requests**, open **Review monthly research updates**, inspect the changed JSON, publication links, and new stories, and click **Merge pull request** only after approval. GitHub Pages must be configured to deploy from the `main` branch; never configure Pages to deploy from `proposed-monthly-refresh`. If automated PR creation fails, in repository **Settings → Actions → General → Workflow permissions**, allow GitHub Actions to create and approve pull requests (and give workflow read/write permissions as needed).

The weekly email continues to use approved content from `main`. It generates social-media **drafts only** and will not publish social posts.

## Source verification for previously incomplete stories

Direct records have been located for the 2026 food-pantry conference abstract, both 2025 Society for Social Medicine conference abstracts, House of Lords evidence, the Springer Nature blog and the Sky News article. All six have been expanded into 500–1,000-word editorial articles using the published abstracts or accessible primary-source material, with limitations identified in the text. The other three pieces remain marked as briefs until sufficient source content is extracted and reviewed. The University of Oxford SALIENT page and Warwick Plate to Planet page did not expose usable article bodies through the available public retrieval. The podcast link does not provide a verified transcript. Do not automatically invent their contents.

Once your OpenAI API key is configured, monthly updates attempt to produce grounded drafts for any uncompleted records with enough accessible source text, ready for your approval via pull request. To generate a substantial story from a podcast or inaccessible institutional page, provide a transcript or source document and add it to the content workflow.

## Local preview in VS Code (October 2026 fix)

Open `index.html` directly, or use VS Code Live Server / Live Preview. `data/site-data.js` now carries the initial articles and publication data, avoiding the `fetch()` restrictions on local `file://` pages. Keep that file alongside `data/publications.json` and `data/articles.json`. The close (×) button, backdrop click, and Escape key are connected before content loading. Monthly GitHub updates regenerate `data/site-data.js` and include it in the approval pull request. Do not edit this generated file manually.

### Local images

The story tiles use locally stored, photographic-style WebP images with no topic labels embedded in them. These are editorial illustrations, not original publication figures. The files are in `images/` and can be replaced independently. Newly discovered publications default to `images/market-feature.webp` until reviewed.
