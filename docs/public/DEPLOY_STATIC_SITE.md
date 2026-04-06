# Chronicle Static Site Deployment

## What This Gives You

`docs/public/index.html` is now a launch-ready single-page site entrypoint for free static hosting.

It already includes:

- Chronicle positioning and pricing
- Mac and Windows download sections
- your active public contact addresses
- benchmark showcase images
- responsive layout and keyboard-accessible showcase tabs

## Best Free Launch Setup

Recommended split:

- host the page on Cloudflare Pages
- host the app download files on GitHub Releases

Why this split works well:

- the website stays simple and free
- large Mac and Windows downloads do not need to live inside the static site
- you can update release files without redesigning the page

## What To Upload

Publish the contents of `docs/public/` as the site root.

The important files are:

- `index.html`
- `showcase_assets/chronicle-showcase-war-diary.png`
- `showcase_assets/chronicle-showcase-newspaper.png`

## How To Launch Fast

### Option 1: Cloudflare Pages

1. Create a new Pages project.
2. Point it at the Chronicle repo, or upload the `docs/public` folder.
3. Set the output directory to `docs/public`.
4. No build command is required for this static page.

### Option 2: GitHub Pages

1. Put the contents of `docs/public` into a publishable branch or `/docs` site root.
2. Enable GitHub Pages in the repository settings.
3. Serve from the branch/folder that contains `index.html`.

## Download Link Swap

The current Mac and Windows buttons now point at the live GitHub Releases asset names.

When the real files are published:

1. publish the GitHub release assets
2. confirm the downloads work from the `releases/latest/download/...` links
3. redeploy the static folder if you changed any copy around those links

GitHub Releases is a good first home for those files because direct release asset links are stable enough for a launch page.
