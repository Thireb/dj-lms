# Vendored frontend libraries (self-hosted)

| Library | Version | Path |
|---|---|---|
| HTMX | 2.0.4 | `static/vendor/htmx/htmx.min.js` |
| Alpine.js | 3.14.8 | `static/vendor/alpine/alpine.min.js` |
| Chart.js | 4.4.7 | `static/vendor/chart.js/chart.umd.min.js` |
| Lucide icons (sprite of the icons in `apps/ui/icons.py`) | 1.53.0 | `static/vendor/lucide/` |
| Familjen Grotesk (variable, latin and latin-ext) | Google Fonts v11 | `static/vendor/familjen-grotesk/` |

Lucide is licensed under ISC (`static/vendor/lucide/LICENSE`). Rebuild the sprite with `python scripts/build_icon_sprite.py <lucide-static package>`.

Familjen Grotesk is licensed under the SIL Open Font License 1.1 (`static/vendor/familjen-grotesk/OFL.txt`).

Tailwind CSS standalone CLI version is pinned in `static/css/TAILWIND_VERSION`.
