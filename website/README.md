# Research Hub documentation

The documentation site is built with Docusaurus and published through the repository's GitHub Pages workflow.

## Local development

Install Node.js 20 or later before running the site commands.

Install the locked dependencies:

```bash
npm ci
```

Start the development server:

```bash
npm run start
```

## Validation

Before submitting documentation changes, run:

```bash
npm run typecheck
npm run build
```

The production build checks internal routes and generates the static site in `build/`.

## Deployment

Changes under `website/` are deployed from `main` by `.github/workflows/deploy-docs.yml`. Do not publish the site manually from a local branch.
