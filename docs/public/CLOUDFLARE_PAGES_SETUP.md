# Chronicle Cloudflare Pages Setup

## Recommended Hosting Choice

For Chronicle's first public site, Cloudflare Pages is a good fit because the page is a static site with no backend requirement.

## Important Cloudflare Choice

Cloudflare currently supports both:

- Git integration
- Direct Upload

These are separate project styles. Pick one on purpose.

Recommended for Chronicle:

- use Git integration if you want the site to redeploy when the public repo changes
- use Direct Upload if you want the website to stay separate from GitHub changes and publish manually

## Chronicle Recommendation

For a first public launch, Git integration is usually easier if the public repo will contain the `docs/public/` website bundle while GitHub Releases hosts the actual Mac and Windows ZIP files.

Use:

- repository: the public Chronicle repo
- production branch: `main`
- build command: none
- build output directory: `docs/public`

## Why The Current Bundle Works

The Chronicle website bundle is already static and Cloudflare-friendly:

- `index.html` is the entrypoint
- `_headers` is included for response headers
- no build step is required
- showcase images live beside the page in `showcase_assets/`

## If You Want Manual Publishing Instead

Cloudflare Direct Upload also works for this site bundle.

You can upload the `docs/public/` folder directly after replacing the temporary Mac and Windows `mailto:` buttons with real hosted download URLs.

## Before You Publish

1. Open `docs/public/index.html`.
2. Confirm the GitHub release is published with:
   `Chronicle 1.0 mac.zip`
3. Confirm the GitHub release is published with:
   `Chronicle 1.0 windows.zip`
4. Keep the support and press email addresses as they are unless you introduce domain mail.
5. Test the page with keyboard-only navigation and browser zoom before final publish.
