# Chronicle website hosting

Chronicle's website provides direct Mac and Windows downloads, document examples, the user guide, and optional support links. Downloads remain on GitHub Releases.

## GitHub Pages

The public address is `https://harry6116.github.io/`. GitHub hosts it from the `harry6116.github.io` repository. Its Chronicle homepage workflow reads the website source from the public Chronicle repository and the latest stable release from GitHub Releases.

The `Chronicle homepage` workflow builds a dedicated static artifact with `tools/build_pages_site.py`. It includes the landing page, browser-readable examples and images, and the user guide. It does not publish the repository or the whole documentation folder.

To prepare a local copy:

```sh
python tools/build_pages_site.py --output /tmp/chronicle-site
```

The output directory must be new or empty. Serve that directory with a static web server to preview it.

In the website repository's **Settings > Pages**, select **GitHub Actions** as the build source. Run **Chronicle homepage** from its Actions tab. The workflow is maintained as `.github/workflows/homepage.yml` in Chronicle and copied to the website repository. The homepage repository contains hosting configuration; Chronicle remains the source of truth for the actual page.

Confirm the deployment succeeds, visit the page, and check both download links, the user guide, examples, keyboard navigation, screen-reader reading order, and support links.

## Release announcements and downloads

The Mac and Windows buttons use GitHub's `/releases/latest/download/` URLs. Keep the release asset names `Chronicle.mac.zip` and `Chronicle.windows.zip`; uploading differently named files would break those links. Upload both complete packages to a draft, verify them, then publish it as the latest stable release.

The local Chronicle release-publishing command requests a homepage deployment immediately after publishing. The homepage also checks for source and release changes twice an hour, covering releases published directly through GitHub. Scheduled runs can be delayed by GitHub, so use a manual homepage run when an immediate refresh is needed. The workflow checks out the current website from `main`, reads GitHub's latest stable release, and generates its version, publication date and up to three highlights. Full notes appear on a separate readable page, so visitors can read them without navigating GitHub. The website does not require browser JavaScript or visitor API access for announcements.

Both uploaded, nonempty platform ZIPs are required. Drafts and prereleases are not announced. If the API lookup or validation fails, deployment stops and the existing website remains in place; check the Actions result and rerun **Chronicle homepage** after fixing the release. A refresh after release removal uses the remaining latest release. An unpublished source commit or tag alone does not announce an app update.

The homepage deployment environment only needs the website repository's `main` branch. The separate `Chronicle website` workflow can optionally deploy a project mirror at `/Chronicle/` if Pages is enabled on that repository; release-triggered mirror deployments also need stable tags `v*` permitted. The root homepage does not depend on that mirror.

GitHub can disable scheduled workflows in a public repository after 60 days without repository activity. The release command's explicit homepage dispatch still works, and the homepage can be refreshed manually. Check its workflow status during release verification and re-enable scheduling if needed.

For a local preview with current release details:

```sh
gh api repos/harry6116/Chronicle/releases/latest > /tmp/chronicle-release.json
python tools/build_pages_site.py --release-json /tmp/chronicle-release.json --output /tmp/chronicle-site
```

Without release metadata, a local build displays a generic latest-release link rather than a fixed version number.

## Custom domains

GitHub Pages also supports a domain you own, such as `www.example.org`, or a subdomain such as `chronicle.example.org`. GitHub provides hosting; domain registration and renewal are separate.

1. Verify the domain in your GitHub account's **Settings > Pages** using the TXT record GitHub supplies. Keep that record.
2. Add the chosen hostname in the Chronicle repository's **Settings > Pages > Custom domain** before pointing DNS to GitHub.
3. For a subdomain, set its DNS CNAME target to `harry6116.github.io` (without `/Chronicle/`). For a root domain, use the A or ALIAS/ANAME records in GitHub's current documentation.
4. Wait for DNS and certificate provisioning, then enable **Enforce HTTPS** and check redirects and every local link.

With an Actions deployment, the custom domain is configured in repository settings; a source `CNAME` file is not required. Avoid wildcard DNS records. Domain verification, DNS and HTTPS can take time to settle.

Official instructions: [Managing a custom domain](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site) and [Verifying a custom domain](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages).

## Alternative hosting

The same generated static folder can be uploaded to Cloudflare Pages or another static host. No backend or website account is required for visitors to read the page or start a direct app download. GitHub sign-in is required for GitHub sponsorship and issue reporting.
