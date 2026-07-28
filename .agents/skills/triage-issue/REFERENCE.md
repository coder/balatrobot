# HTML Report Reference

## Palette (Tokyo Night)

Include this `<style>` block in the report. It provides a dark theme with semantic color variables. Compose the rest of the report freely — choose whatever sections, layout, and HTML elements best explain the issue.

```css
:root {
  --bg: #1a1b26; --surface: #24283b; --border: #3b4261;
  --text: #c0caf5; --muted: #565f89; --accent: #7aa2f7;
  --green: #9ece6a; --red: #f7768e; --yellow: #e0af68; --purple: #bb9af7;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.65;
  padding: 2.5rem; max-width: 860px; margin: 0 auto; font-size: 0.9rem;
}
h2 { color: var(--accent); margin: 2rem 0 0.5rem; }
code { background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 0.1rem 0.35rem; }
pre { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; overflow-x: auto; font-size: 0.82rem; }
a { color: var(--accent); }
hr { border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }
```

## Verdict badges

```css
.badge { display: inline-block; padding: 0.2rem 0.65rem; border-radius: 20px; font-size: 0.78rem; font-weight: 600; }
.badge-green  { background: rgba(158,206,106,0.15); color: var(--green);  border: 1px solid rgba(158,206,106,0.3); }
.badge-red    { background: rgba(247,118,142,0.15); color: var(--red);    border: 1px solid rgba(247,118,142,0.3); }
.badge-yellow { background: rgba(224,175,104,0.15); color: var(--yellow); border: 1px solid rgba(224,175,104,0.3); }
```

| Verdict | Class | Color |
|---------|-------|-------|
| Reproduced / bug confirmed | `badge-red` | `--red` |
| Already fixed / no action needed | `badge-green` | `--green` |
| Needs manual review / inconclusive | `badge-yellow` | `--yellow` |

## Required header

Every report must start with:

```html
<h1>{issue title}</h1>
<p class="meta">
  <code>{scope}</code> &middot;
  <a href="https://github.com/coder/balatrobot/issues/{NNN}">#{NNN}</a> &middot;
  coder/balatrobot &middot;
  <span class="badge badge-{color}">{VERDICT}</span>
</p>
```

The link to the original issue on GitHub is mandatory.

## Guidelines

- **Compose freely.** The LLM decides which sections (`<h2>`) to include based on what best explains the issue. There is no fixed template beyond the header.
- **Use the palette variables** for all colors. Use `--red`/`--green` for diff highlights, `--accent` for headings and links, `--muted` for secondary text.
- **Keep it simple.** Plain HTML. No frameworks, no JavaScript. The report is a static file opened in a browser.
- **Save to** `/tmp/balatrobot/issues/{NNN}/report.html`
