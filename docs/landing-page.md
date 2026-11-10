# FlowRemote landing page

A self-contained product introduction page. It is served by the existing
`/static` mount, so the running product does not need any route, template,
stylesheet or behaviour change.

## What it is

- **URL:** `/static/landing.html`
- **Local preview:** `http://127.0.0.1:8000/static/landing.html`
- **Files:**
  - `src/flowremote/ui/static/landing.html`
  - `src/flowremote/ui/static/landing.css`
  - `src/flowremote/ui/static/img/` - supplied FlowRemote lockup, mark, favicons and OG card
- **Authentication:** none. The file is served directly by FastAPI's static mount.
- **Product access:** the page's buttons open the existing `/login` and
  `/signup` pages, so it works next to the unmodified application.

No existing product template, stylesheet, route, test or README file is
modified. The page is additive.

## Message hierarchy

The page answers the four questions in the brief, in this order:

1. **What is the product?** The supervision layer for AI-driven data
   processing across Excel, BI and OA. It validates a batch, explains every
   exception and requires a person before a write.
2. **Who is it for?** Operations teams, the approvers accountable for the write,
   and AI-RPA builders who need a control plane around their bot.
3. **Why is it worth using?** Autonomy without accountability is the risk.
   Evidence-backed suggestions, a single-use approval gate and an audit trail
   make the automation reviewable.
4. **How can someone access it?** Two demo accounts are printed on the page;
   the primary buttons open the live sign-in and sign-up forms.

## Page sections

| Section | Job | Primary content |
| --- | --- | --- |
| Hero | State the promise and give the first CTA | "Let AI run the workflow. Keep the final say." |
| Why FlowRemote | Name the three risks | Accountability, hidden exceptions, missing audit evidence |
| How it works | Show the loop | Upload, validate, review with AI, approve and watch execution |
| Features | Prove the guardrails | Evidence-or-no-suggestion, approval gate, explained exceptions, roles, mobile progress, audit export |
| Who it is for | Let a visitor self-identify | Operators, approvers, builders |
| Demo | Convert with minimal friction | Five-step walkthrough, operator and admin credentials |
| FAQ | Answer the honest objections | Simulated execution, AI is advisory, current connectors, local setup, data handling, source of evidence |
| Final CTA | Repeat the action | Live demo / create an account |
| Footer | Provide the route map | Product anchors, account links and the simulation disclaimer |

## Demo accounts shown on the page

| Account | Password | Sees |
| --- | --- | --- |
| `alex.morgan@example.com` | `123456` | only TASK-1001 (operator) |
| `admin@example.com` | `123456` | every task (admin) |

The page labels these as local coursework credentials and tells visitors to
remove them before a real deployment. It also states that OA and BI writes are
simulated while review, approval and audit state are real.

## Assets

| File | Use |
| --- | --- |
| `flowremote-lockup.png` | Header and footer, light wordmark for the dark page |
| `flowremote-mark.png` | Hero app mock and closing CTA |
| `favicon-64.png`, `favicon-180.png` | Browser tab and touch icon |
| `flowremote-og.png` | Open Graph link preview |

The supplied source artwork had a transparent background with a near-black
wordmark. The page's lockup keeps the teal mark and recolours only the wordmark
to the page's light ink; the mark geometry is unchanged.

After the app has a public domain, set `og:image` in `landing.html` to the
absolute URL of `flowremote-og.png` so link previews work on social platforms.

## Promotion report evidence

- **Landing page URL:** the deployed `/static/landing.html` address
- **Screenshot:** desktop hero, mobile hero and the demo panel all render from
  the same HTML; capture both widths from the running app.
- **Public access proof:** open the URL in a private window (no cookie) and keep
  the response headers/screenshot with the access timestamp.
- **Copy deck:** the section table above is the text inventory for the report.
- **No product change:** `git diff` for this commit contains only new files; the
  original application is the same as the preceding commit.
