# Latent-Lens Web

This repository contains the source code for the LatentLens organization website. It is built as a highly optimized, statically generated site using custom Python build scripts, with zero heavy frontend frameworks (no React, Next.js, or Vue). It takes a lot of inspiration from the [as-folio Astro theme](https://github.com/dadangnh/as-folio).

The site compiles markdown data and live API metrics directly into static HTML, CSS, and JS, which is then deployed seamlessly to Cloudflare Pages.

## 🚀 Getting Started

To run the site locally and test changes, use the provided Python development server:

```bash
# Start the local server
python dev_server.py
```

This will spin up a local server (defaulting to port 8002). Open your browser and navigate to `http://127.0.0.1:8002` to view the site!

## 🛠️ Build Scripts

The site's dynamic content (like projects, publications, and real-time GitHub statistics) is pre-compiled via Python build scripts. You must run these scripts to update the static HTML before committing or deploying.

### 1. GitHub Statistics Builder
Fetches live organization and user statistics via the GitHub GraphQL API, formatting and injecting them directly into the repositories page. 
```bash
python build_github_stats.py
```
*Note: This script requires a valid `GITHUB_TOKEN` to run. You can provide this by either setting an environment variable, or by placing the token inside a `misc/.env` file. Do not commit your token!*

### 2. Projects & Publications Builder
Parses the markdown data files located in `data/` and injects them as structured HTML components into the site.
```bash
python build_projects.py
```

### Full Build Command
If you are modifying multiple components, you can run the full build pipeline sequentially:
```bash
python build_github_stats.py && python build_projects.py
```

## 📂 Project Structure

- `index.html`: The main homepage template.
- `pages/`: Contains all subpages (e.g., repositories, about, contact).
- `data/`: Markdown files holding structured data for projects, news, and publications.
- `public/`: Static assets such as images and fonts.
- `styles.css` / `script.js`: Global vanilla CSS and JavaScript files.
- `out/`: The final static directory generated for Cloudflare Pages deployment.