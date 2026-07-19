# Widget Responsive, Visual, and Release Readiness

TASK-065B4 completes the current functional widget experience for controlled pilot readiness. It hardens the existing iframe UI without changing backend APIs, SDK public APIs, token ownership, or conversation persistence policy.

## Responsive Implementation

The widget uses the SDK-owned iframe bounds plus iframe-internal responsive layout. The iframe app now synchronises a CSS variable from the Visual Viewport API where supported:

- `--yw-visual-viewport-height` is updated from `window.visualViewport.height` with `window.innerHeight` fallback.
- Visual Viewport `resize` and `scroll` events, plus `orientationchange`, update the internal available height.
- Listeners are removed when the widget root is destroyed.
- The value is used only for layout sizing; no user content or token data is logged.

Final layout matrix:

| Range | Panel model | Width | Height | Notes |
| --- | --- | --- | --- | --- |
| >= 1440px | Desktop floating | 400px target, bounded by viewport | 640px target, max visual viewport minus margins | Launcher label visible when space allows. |
| 1024-1439px | Desktop/laptop floating | 380-400px | 600-640px | Panel remains inward from launcher and never covers the full page. |
| 768-1023px | Tablet floating/near-full | min(400px, viewport minus safe margins) | visual viewport minus margins | Touch targets remain at least 44px. |
| 480-767px | Mobile near-full-screen | viewport minus 16px gutters | visual viewport minus safe areas | Header and footer remain reachable. |
| < 480px | Narrow mobile near-full-screen | viewport minus 12px gutters | visual viewport minus safe areas | Suggestions, messages, citations, and footer wrap. |
| Mobile landscape | Compact near-full-screen | viewport minus safe margins | visual viewport minus compact margins | Header density and composer height are constrained. |

The conversation viewport owns scrolling. Composer growth is capped internally and does not request unbounded iframe dimensions. Closed state remains non-blocking through the existing SDK pointer-events policy.

## Motion System

Motion remains restrained and token-driven:

- Launcher and panel use opacity/transform transitions.
- Message arrival, notices, jump-to-latest, and citation disclosure use short opacity/translate transitions.
- Assistant preparation uses bounded state motion only.
- No animation dependency was added.
- Motion does not drive lifecycle acknowledgement; protocol state remains authoritative.

Reduced-motion behavior:

- Panel, launcher, message, notice, citation, and scrolling effects become immediate or near-immediate.
- No pulsing/waveform behavior is required for operation.
- Smooth scroll is disabled for reduced-motion users.

## Forced Colours And High Contrast

Forced-colours mode uses system colours for text, surfaces, borders, buttons, focus outlines, and selected states. Answer states remain understandable through labels and structure, not colour alone. Focus remains visible and controls preserve minimum target sizes.

## Branding Extremes

Customer colours continue through the validated token pipeline introduced in TASK-065B1:

- Invalid colours fall back to the platform palette.
- Very light or dark accents receive accessible foreground selection.
- Warning, danger, fallback, low-confidence, and focus tokens are not replaced by brand colours.
- Extreme brand scenarios are covered in browser and visual tests.

## Visual Regression

Playwright visual scenarios are scoped and deterministic. Animations and caret rendering are disabled inside the iframe before screenshots. Baselines use fake content, fixed viewports, no timestamps, no remote assets, and no sensitive values.

Visual scenarios:

- Launcher closed desktop.
- Welcome desktop.
- Active conversation with citations desktop.
- Fallback and low-confidence states.
- Mobile welcome.
- Mobile conversation with citations.

Commands:

```bash
npm run widget:e2e:visual
npm run widget:e2e:visual:update
```

Baselines live in Playwright's standard snapshot directory next to the visual spec. Visual snapshots supplement functional and security assertions; they are not a substitute for them.

## Accessibility Evidence

| Requirement | Implementation | Automated evidence | Manual note | Status |
| --- | --- | --- | --- | --- |
| Keyboard operation | Launcher, suggestions, composer, citations, retry, privacy links, close, and Escape are keyboard reachable. | Browser release accessibility and functional specs. | Manual AT pass still required before GA. | Pilot-ready |
| No keyboard trap | Focus containment applies only while the panel is open and cycles within enabled iframe controls. | Focus tests in Chromium/browser suite. | Cross-origin host focus remains SDK-owned. | Pilot-ready |
| Focus visible | Tokenised focus ring plus forced-colours overrides. | Component and browser checks. | Verify on final production domain. | Pilot-ready |
| Reflow/zoom | Responsive viewport and long-content tests cover narrow/mobile layouts. | Responsive and visual specs. | 400% browser zoom requires manual confirmation per release. | Pilot-ready |
| Contrast | Token contrast utilities preserve WCAG AA targets for configured colours. | Unit and browser branding checks. | Customer assets still need review when enabled. | Pilot-ready |
| Target size | Primary controls meet 44px minimum on touch/coarse pointer layouts. | Browser accessibility release checks. | N/A | Pilot-ready |
| Status messages | Polite/assertive live-region strategy from B3 preserved. | Conversation/accessibility specs. | Screen-reader manual review required. | Pilot-ready |
| Error association | Composer validation and recovery notices are accessible and not colour-only. | Browser and unit specs. | N/A | Pilot-ready |
| Reduced motion | Transitions and scroll behavior disable or shorten under reduced motion. | Browser release checks. | N/A | Pilot-ready |
| Forced colours | System-colour overrides for controls, borders, focus, and surfaces. | Browser smoke checks. | Manual Windows high-contrast pass recommended. | Pilot-ready |

This is evidence for a WCAG 2.2 AA target, not a certification claim.

## Security Evidence

| Boundary | Evidence |
| --- | --- |
| Token isolation | Existing B5 token tests plus B3/B4 parent leakage checks. |
| postMessage origin/source | Existing handshake/security browser tests remain required. |
| API ownership | Browser tests assert host page does not call config/session/message endpoints. |
| Storage isolation | Session token remains in iframe sessionStorage or private memory fallback only. |
| Console hygiene | Browser tests capture console output; production inspection checks normal console calls. |
| DOM rendering | Plain text renderer avoids raw HTML and Markdown execution. |
| Citation URL safety | Citation links remain absent unless backend provides validated HTTPS URLs. |
| CSP/sandbox | Browser CSP/sandbox tests and documentation remain in force. |
| Production hook exclusion | Production inspection rejects test harness names, test hosts, and fixture values. |
| Host CSS isolation | Cross-origin iframe and browser host-isolation tests protect widget internals. |
| Network origins | Browser tests assert no external fonts, icons, analytics, telemetry, or host-owned API calls. |

## Production Bundle Inspection

The widget production dist is inspected after a production build:

```bash
npm run widget:build
npm run widget:inspect:production
```

The inspection rejects test harness globals, test API host strings, localhost test ports, fixture tokens/messages, mock API text, and normal `console.log/debug/info` calls in built JavaScript assets. It intentionally avoids brittle checks against minifier internals.

## Performance And Bundle Budgets

Final B4 budgets:

- Preferred widget JS gzip: under 28 KB.
- Absolute release cap: 35 KB.
- Widget CSS gzip: under 8 KB.
- SDK global bundle should remain materially unchanged.
- No external fonts, Markdown parser, syntax highlighter, animation library, telemetry library, or large icon set.

Runtime goals are local-test goals only: launcher/open interactions should respond promptly, message/preparation paint should occur immediately after accepted send, and repeated open/close/destroy should not accumulate listeners or unbounded DOM.

## Embed Compatibility

Supported production-style snippet:

```html
<script
  src="https://WIDGET_HOST/sdk/v1/loader.js"
  data-widget-key="wpk_live_REPLACE_WITH_PUBLIC_KEY"
  data-environment="production"
  async
></script>
```

Supported optional attributes remain limited to approved SDK configuration fields such as `data-initial-open`, `data-mount-mode`, `data-locale`, and development-only `data-debug`. Do not include tenant IDs, API URLs, session tokens, arbitrary iframe URLs, raw HTML/CSS, model/provider settings, or security-policy overrides.

CSP placeholders:

```text
script-src 'self' https://WIDGET_SDK_HOST;
frame-src https://WIDGET_IFRAME_HOST;
connect-src 'self' https://PUBLIC_API_HOST;
img-src 'self' https: data:;
style-src 'self' 'unsafe-inline';
```

Tighten the example to the actual production hosts before pilot. The iframe application itself should continue to avoid external fonts/icons and unsafe eval.

## Known Limitations

- No persisted conversation history.
- No persisted draft.
- No streaming.
- No Markdown or rich HTML renderer.
- No file, voice, emoji, lead capture, human handoff, analytics, or telemetry.
- Citations have no external links unless the backend later provides validated public HTTPS URLs.
- Local performance tests do not represent real-world network latency.
- Mobile virtual-keyboard automation is approximate in Playwright.
- Browser accessibility automation does not replace manual assistive-technology testing.
- Optional real-backend e2e remains separate/absent unless explicitly added.

## Release Classification

Current classification: **release-ready for controlled pilot**.

General availability remains blocked pending production-domain/header configuration, real-backend smoke coverage, operational monitoring, customer asset policy completion, and manual accessibility review with target assistive technologies.

## Commands

```bash
npm run widget:install
npm run widget:test
npm run widget:lint
npm run widget:build
npm run widget-sdk:install
npm run widget-sdk:test
npm run widget-sdk:lint
npm run widget-sdk:build
npm run widget:inspect:production
npm run widget:bundle:check
npm run widget:e2e:chromium
npm run widget:e2e:a11y
npm run widget:e2e:visual
npm run widget:e2e:extended
npm run widget:release:verify
npm run verify
git diff --check
```
## TASK-066B1 Production Delivery Foundation

TASK-066B1 implements repository-local, provider-neutral release artifacts, origin validation, cache/header policy, manifest/checksum generation, production inspection, and versioned-loader browser smoke coverage. It does not deploy production infrastructure. See `docs/04_Engineering/Widget_Production_Delivery_Security_and_Versioning.md` and `docs/06_Operations/Widget_Deployment_Runbook.md`.
