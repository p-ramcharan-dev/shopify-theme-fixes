# Shopify theme fixes

Small, self-contained Liquid snippets for problems I keep finding when I audit Shopify storefronts, plus the script I use to run a first-pass audit.

Everything here uses standard Shopify Liquid, so it works on vintage themes (Debut, Supply, Minimal, Pop) as well as Online Store 2.0 themes. Each snippet has install notes in its header comment.

## Snippets

| Snippet | Problem it fixes |
|---|---|
| [`heading-outline.liquid`](snippets/heading-outline.liquid) | Several `<h1>` tags on the homepage (logo, collection tiles, featured products), leaving no single page title for search engines or screen readers |
| [`social-meta.liquid`](snippets/social-meta.liquid) | Links to the store share without a picture because the page has no `og:image` |
| [`pdp-shipping-returns.liquid`](snippets/pdp-shipping-returns.liquid) | Product pages that say nothing about delivery or returns near the buy button |
| [`responsive-image.liquid`](snippets/responsive-image.liquid) | Images loaded eagerly at one fixed size; alt text broken by quote marks in product titles |
| [`product-json-ld.liquid`](snippets/product-json-ld.liquid) | Product data exposed only as old-style microdata, or not at all |

## Audit script

[`audit/audit.py`](audit/audit.py) makes three or four ordinary page requests to a public storefront (homepage, one product page, `products.json`, contact page) and reports:

- theme name and version
- heading count, share image, skip link
- image alt text and sizing
- script count and render-blocking scripts
- catalogue stats: photos per product, description length, lead image width

```
python audit/audit.py example-store.com another-store.com > results.json
```

It needs Python 3.9+ and no third-party packages. It reads public pages only: no logins, no form submissions. Treat its output as leads to check by hand, not as conclusions. Pattern matching on HTML produces false positives.

## How I install a fix

1. Duplicate the live theme (Online Store > Themes > Duplicate).
2. Add the snippet to the duplicate and add the `render` line from its header comment.
3. Preview on a phone and a desktop.
4. Send the store owner the preview link. Publish only after they approve.

## Not covered by a snippet

- **Moving off a retired theme.** Debut, Supply, Minimal and Pop no longer receive updates. Migrating to a current theme is a per-store job: duplicate, rebuild the homepage sections, carry over branding and navigation, test, publish.
- **Old jQuery.** Usually disappears with a theme migration; otherwise the theme's own scripts need checking one by one.
- **Catalogue content.** Single-photo listings and thin descriptions are the owner's content, but a template and metafield structure can make them quick to fill in.

## Demos

Working concept stores that show the end result: https://p-ramcharan-dev.github.io/shopify-storefront-demos/

## License

MIT. See [LICENSE](LICENSE).
