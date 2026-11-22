# Portfolio demo best practice and frontend stack for an ML dashboard (November 2026)

Scope note: research done 2026-11-22. This covers public, general guidance only. Nothing here describes the host server's configuration or weak spots. Those stay in `private/`.

## What ML / fraud / data hiring managers notice in portfolio projects (2025-2026)

### Takeaway
I found no rigorous survey of hiring managers. What exists is named practitioners (Chip Huyen, Eugene Yan) plus a lot of career-blog opinion, and the blogs agree with each other: a deployed thing someone can click, an end-to-end repo with tests and CI, evaluation against a baseline, written-down failure cases and limits, and a README that explains the problem and result fast. When anyone can generate a demo in an afternoon, the demo alone proves little. The evaluation and the honesty are what set a project apart.

### Cited Findings
- Chip Huyen (Claypot AI) encourages candidates to "be creative with a side project, because we see a lot of value in having interesting ideas and showing the creativity of thinking". She values transferable skills over deep knowledge of one framework. — [VentureBeat](https://venturebeat.com/ai/4-ai-and-ml-job-hunting-tips-from-chip-huyen)
- Summary of Huyen's book: public work (in-depth technical blog posts, open source, hackathons) can weigh more than a resume. — [Cinnak blog summary](https://cinnak.github.io/cinnakblog/blog/2025/04/01/lessons-from-chip-huyen_mastering-ml-interviews-and-career-strategies/) (secondary source)
- Eugene Yan reportedly asks candidates how they evaluated a system, what error analysis they did, what trade-offs they made and what they would change. — [Data Root Labs](https://datarootlabs.com/blog/data-science-projects-for-portfolio) (secondary). His own essay treats hiring as a system that needs reliable, valid signals and calls data literacy an overlooked skill. — [eugeneyan.com](https://eugeneyan.com/writing/how-to-interview/)
- Yan's own site gives each prototype one line, a date, and links to code and a demo. Style example: short and linkable. — [jobroadmaps review](https://jobroadmaps.com/portfolios/eugene-yan) (third party)
- Career-blog claims, marked by the author as "illustrative scenario, not a measured universal review process": an initial skim of about 40 seconds; the README must make problem, approach and result clear in its first 200 words; a deployed link signals more seriousness than a notebook-only repo; Dockerfile, tests, CI and model versioning are ML-engineering signals; "most candidates have zero tests"; "honest evaluation including failure analysis" is high signal; benchmark accuracy and star counts are low signal; if a clone fails within three commands "the review is over". — [LetsDataScience](https://letsdatascience.com/blog/the-ml-portfolio-that-actually-gets-you-hired-in-2026)
- A "limitations and next steps" section signals self-awareness that employers value. Explaining the limits of your own work is more credible than showing only wins. — [MentorCruise](https://mentorcruise.com/blog/career-roadmap-how-to-build-an-ai-portfolio-that-gets-you-hired/); [Zen van Riel](https://zenvanriel.com/ai-engineer-blog/top-ai-portfolio-mistakes-engineers-make/)
- Include at least one concrete case where the model is wrong (a "maturity signal"). Use model cards, not notebooks. — [Slategit](https://slategit.com/blog/ai-ml-engineer-portfolio-model-cards-not-notebooks)
- Counterpoint: "when every candidate can generate a working demo in an afternoon, the demo stops being evidence". — [Towards AI](https://pub.towardsai.net/your-ai-portfolio-isnt-missing-projects-it-s-missing-proof-5d738b74995b) (member-only story; seen only as a search snippet)
- Recruiters want data, training, evaluation, deployment and monitoring in one repo, not a notebook with accuracy scores. A "boring, high-value business problem" solved with traditional ML can stand out against generic chatbot projects. — [search summary of 2026 career blogs incl. Dataquest](https://www.dataquest.io/blog/machine-learning-projects-for-beginners-to-advanced/) (opinion)
- "Tutorial clone" risk: credibility drops if the only justification for XGBoost is "the tutorial used it". — [search snippet, 2026 career blogs](https://www.techinterview.org/post/3233475399/ai-portfolio-built-with-ai-2026-interviews/?format=md)

### Inferences
- This project already has the scarce signals: a written leakage contract, a time split, a GNN that lost and is written up as a finding, precision@k, and a model-risk card planned. The interface should put that rigor on screen (a "how we measured this" panel, a FINDINGS link, a synthetic-data banner). The interface itself is not the differentiator.
- A reviewer may give the site under a minute. The landing view should show, without scrolling: what this is, that the data is synthetic, the headline metric against the baseline, and one live element.
- One honest failure case shown in the UI (a missed ring, a false positive with its explanation) probably beats a polished happy path.

### Gaps
- No survey data with sample sizes on recruiter behavior specific to ML or fraud portfolios. All the timing numbers above are self-declared illustrations.
- The search returned no Hacker News or Reddit threads with numbers, so I could not cite any. Fraud-specific hiring manager commentary was not found either.
- I found no source specific to the ideal video length for portfolio projects, as opposed to B2B product demos.

## Demo video structure, length, tooling and mistakes

### Takeaway
B2B data puts the sweet spot at roughly 30 s to 2.5 min. Under 30 s does worse. Show one workflow, not a feature tour. Don't open with setup. Assume the video plays muted, so captions and on-screen text must carry the story. Sources were marketing-oriented and none was specific to technical screencasts.

### Cited Findings
- A 2026 study of 1,750 B2B demo videos: anything from 30 s to 2.5 min performs about the same. Videos under 30 s reach the top quartile less than half as often. — [Motion the Agency study](https://www.motiontheagency.com/insight/b2b-product-demo-video-study)
- Length depends on where the video is placed: 15-30 s for paid social, 45-90 s for a landing page, 2-3 min for a sales follow-up, 3-10 min for docs and onboarding. Start near 2 min for a product-page demo. — [Velo benchmarks](https://usevelo.ai/blog/blog-product-demo-video-length/); [Demosmith](https://demosmith.ai/blog/how-long-should-demo-video-be)
- Mistakes: reusing one cut everywhere (cut short versions down from the full one); running long by adding features ("the fix is almost never faster editing, it is cutting scope: show one workflow instead of three"); opening with setup or a feature tour "before the viewer has any reason to care". — [Velo](https://usevelo.ai/blog/blog-product-demo-video-length/); [Versely](https://www.versely.studio/blog/product-demos-that-dont-bore); [Repoclip](https://repoclip.io/blog/product-demo-video-best-practices)
- Homepage hero videos are often muted autoplay, so the text has to carry the story. Captions are required for social. — [Rend](https://rend.ai/blog/product-demo-videos)

### Inferences
- Suggested ~2-minute structure (my synthesis, not from a source): 0:00-0:15 the problem plus a "synthetic data (IBM AMLworld)" card. 0:15-0:45 the live stream scoring transactions, latency visible. 0:45-1:15 the wow moment: an alert opens, the ring is drawn as a graph, and the explanation shows why. 1:15-1:40 evidence: precision@k against the baseline, the GNN-lost finding, the leakage contract. 1:40-2:00 honest limits and links to the repo and write-up.
- Tooling: record at a fixed browser size with large fonts, burn in captions (or ship a sidecar `.vtt`), and cut a 30-45 s version from the 2-min master for LinkedIn. I found no 2026 sources comparing specific screen recorders (OBS, Screen Studio, etc.). That is a gap.

### Gaps
- No sources specific to technical or developer screencasts (terminal readability, code on screen).
- No sourced comparison of recording or captioning tools as of 2026.

## Frontend stack for a data-heavy dashboard in 2026

### Takeaway
As of Nov 2026, the current Next.js line is 16.4 (released 2026-10-06, with React 19.3 features). The patched releases are 16.4.5 (Active LTS) and 15.5.29 (Maintenance LTS), from 2026-11-03. For this project, a static export (`output: 'export'`) served by the existing web server, with client components fetching from FastAPI and FastAPI's built-in SSE for live updates, gives no Node server process to run, cap or patch for server-side CVEs. shadcn/ui charts (Recharts 3) suit small KPI charts. ECharts (canvas) handles big or streaming series. TanStack Table handles the queue.

### Cited Findings
- Next.js release history: 16.0 (2025-10-21), 16.1 (2025-12-18), 16.2 (2026-03-18, stable Adapter API), 16.3 (2026-08-03, Instant Navigations), 16.4 (2026-10-06: lazy compilation, smaller Turbopack output, React 19.3 features, Cache Components improvements). — [Next.js blog](https://nextjs.org/blog)
- `output: 'export'` writes one HTML file per route to `out/`. Server Components run at build time. Client components fetch data in the browser (SWR suggested). GET Route Handlers can emit static JSON with `dynamic = 'force-static'`. — [Next.js static exports docs, updated 2026-08-09](https://nextjs.org/docs/app/guides/static-exports)
- Not supported under static export: dynamic routes without `generateStaticParams`, Route Handlers that read Request, cookies, rewrites, redirects, headers, Proxy (formerly middleware), ISR, default image optimization, Draft Mode, Server Actions, intercepting routes. The docs give an nginx `try_files $uri $uri.html $uri/ =404;` example. — [Next.js static exports docs](https://nextjs.org/docs/app/guides/static-exports)
- Memory of `next start` / standalone: no official idle figure. One GitHub repro (16.2.2, `cacheComponents: true`) started near 95 MB RSS and grew to about 3.4 GB under high-cardinality traffic. — [vercel/next.js#92287](https://github.com/vercel/next.js/issues/92287). The self-hosting docs warn that image optimization on glibc Linux may need extra config to avoid excessive memory use. — [Next.js self-hosting](https://nextjs.org/docs/app/guides/self-hosting); see also [Next.js memory-usage guide](https://nextjs.org/docs/app/guides/memory-usage)
- A Node process wrapper (`pnpm run start`) used almost as much memory as the Next server itself. Container memory readings can mislead. — [DEV: reduce memory of Node apps in Docker](https://dev.to/fbjorn/reduce-memory-usage-of-nodejs-apps-inside-docker-3588)
- FastAPI has built-in SSE since **0.135.0**: `response_class=EventSourceResponse` (from `fastapi.sse`) with `yield`. `ServerSentEvent(data, id, event, retry, comment)`. Automatic keep-alive `ping` comment every 15 s when idle. Sets `Cache-Control: no-cache` and `X-Accel-Buffering: no` (no nginx buffering). Resume on reconnect by reading the `Last-Event-ID` header. `data` is JSON-encoded via Pydantic. — [FastAPI SSE tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/); [reference](https://fastapi.tiangolo.com/reference/sse/)
- Charts: shadcn/ui chart components are built on Recharts and moved to Recharts 3 (reported March 2026). Recharts and visx are SVG and slow down at scale; one source says Recharts stutters past ~5 updates/s on charts with more than 1,000 points (rough, not benchmarked). ECharts renders to canvas by default, reportedly handles 50K+ points smoothly, is ~1.8 MB min / ~520 kB gzipped, and is used from React through the separate `echarts-for-react` wrapper. visx is low-level D3 primitives, "an order of magnitude more work" for standard charts. — [LogRocket 2026](https://blog.logrocket.com/best-react-chart-libraries-2026/); [PkgPulse 2026](https://www.pkgpulse.com/guides/recharts-vs-chartjs-vs-nivo-vs-visx-react-charting-2026); [chenguangliang comparison](https://chenguangliang.com/en/posts/blog152_react-chart-libraries-comparison/) (blog figures vary; treat as rough)

### Inferences
- Static export fits a read-only public demo. No `next start` process means no Node RAM under the ~4 GB cap, no default image optimizer (where the 2026 critical RCEs were), no Server Functions endpoint (React2Shell's attack surface), and no Proxy/middleware (CVE-2025-29927's surface). The live parts come from the Python backend, which already exists.
- SSE over WebSocket for this UI: the data flows one way (decisions to the browser). SSE is plain HTTP through the existing reverse proxy, the browser `EventSource` reconnects on its own, and `Last-Event-ID` maps onto Postgres decision ids or Kafka offsets. Use WebSocket only if the investigator agent needs two-way streaming, and even then POST plus SSE works.
- Suggested set: Next.js 16.4.x static export, TypeScript, Tailwind v4 plus shadcn/ui, TanStack Table (alert queue), shadcn charts / Recharts 3 for KPI cards, ECharts or a graph library (e.g. Cytoscape.js or Sigma.js; not researched here) for the ring view and dense time series. Pin versions at least 14 days old to match the repo's supply-chain rule.
- Tremor: I did not verify its 2026 status in this pass (it was acquired by Vercel in early 2025 per my own knowledge, unverified here). Prefer shadcn charts, which cover the same ground.

### Gaps
- No measured idle RSS for Next.js 16.4 standalone vs a static build. Measure with `docker stats` if server rendering is ever considered.
- TanStack Table, Tailwind v4 and shadcn current version numbers were not fetched in this pass. Verify on npm before pinning.
- Observable Plot and Tremor were not evaluated with 2026 sources.
- Graph-visualization libraries (rings and subgraphs) were not researched. Likely needed for Phase 7.

## Security for a public demo on a shared server

### Takeaway
Next.js has had a heavy 2026 advisory stream: a formal monthly security release program since July 2026, and critical RCEs in image optimization (Oct 14) and next/og (Sep 22). Running Next.js as a server means patching every month. A static export, plus a read-only, rate-limited Python API on its own database role or snapshot, removes most of that surface. CVE-2025-29927 explicitly does not affect static exports.

### Cited Findings
- **Formal Next.js security program (2026-07-13):** monthly pre-announced security releases with expected severity, plus ad-hoc patches for urgent or exploited issues. The cause cited is the rise of LLM-assisted vulnerability discovery. — [Next.js blog](https://nextjs.org/blog/next-security-release-program.md)
- **Supported lines:** 16.4 = Active LTS, 15.5 = Maintenance LTS. **Current safe versions: 16.4.5 and 15.5.29 (2026-11-03).** That release fixed 7 advisories: 1 High (cross-tenant cache disclosure with `unstable_cache` + `use cache`), 6 Medium (cache poisoning and disclosure in Cache Components, response injection behind HTTP/1.1 pipelining proxies when forwarding fetched Responses unchanged, an HttpOnly cookie leak through `x-middleware-set-cookie` on Edge routes, an SVG-rejection bypass in image optimization). — [Next.js Nov 2026 security release](https://nextjs.org/blog/november-2026-security-release.md); [GitHub advisories](https://github.com/vercel/next.js/security/advisories)
- **2026-10-14 out-of-band:** GHSA-2464-fhr4-w9xw, "Unauthenticated Remote Code Execution in Image Optimization API when SVG files are used", Critical. Fixed in 16.4.1 / 15.5.28 (affects 10.0.0-15.5.27 and 16.0.0-16.4.0; reportedly also needs sharp >= 0.35.5). — [GitHub advisories](https://github.com/vercel/next.js/security/advisories); [Next.js blog](https://nextjs.org/blog/nextjs-security-update-october-14-2026.md); version ranges from [turbostarter](https://www.turbostarter.dev/blog/nextjs-security-update-october-2026) (secondary; CVE IDs conflict across secondary sources, so trust the GHSA IDs)
- **2026-09-22:** GHSA-vcvr-r3jv-pc5j, RCE in `next/og` ImageResponse, Critical (planned in 16.3.6 / 15.5.26). Sep 30 release fixed in 16.3.8 / 15.5.27. — [GitHub advisories](https://github.com/vercel/next.js/security/advisories); [Next.js blog](https://nextjs.org/blog)
- Earlier 2026: July 20 (9 advisories, max High; 16.2.11 / 15.5.21), Aug 25 (AVIF optimization RCE reported; 16.3.3 / 15.5.24), May (13 advisories incl. middleware bypass, DoS, SSRF, XSS; 16.2.6 / 15.5.18). — [Vercel changelog May 2026](https://vercel.com/changelog/next-js-may-2026-security-release); [search summary of secondary trackers](https://fabwaseem.com/blog/nextjs-security-updates) (secondary; verify)
- Next.js on 2026-11-17: more advisories are appearing because of AI-assisted security work. — [Next.js blog](https://nextjs.org/blog/how-were-using-ai-to-make-nextjs-more-secure.md)
- **CVE-2025-29927 (Mar 2025)** middleware authorization bypass via a spoofed `x-middleware-subrequest` header. Fixed in 15.2.3, 14.2.25, 13.5.9, 12.3.5. **Static exports are not affected (middleware is not executed).** Mitigation: strip the header at the reverse proxy. Lesson: never use middleware as the only auth layer. — [Next.js CVE-2025-29927](https://nextjs.org/blog/cve-2025-29927); [Vercel postmortem](https://vercel.com/blog/postmortem-on-next-js-middleware-bypass)
- **CVE-2025-55182 "React2Shell" (Dec 2025)**, CVSS 10: unsafe deserialization at React Server Function endpoints in `react-server-dom-*` 19.0 / 19.1.0 / 19.1.1 / 19.2.0. Fixed in React 19.0.1 / 19.1.2 / 19.2.1 and Next.js 15.0.5, 15.1.9, 15.2.6, 15.3.6, 15.4.8, 15.5.7, 16.0.7. Actively exploited (Amazon threat intel). Next.js tracked it as CVE-2025-66478 (rejected as a duplicate). Two more RSC vulnerabilities followed on 2025-12-11. — [Vercel](https://vercel.com/changelog/cve-2025-55182); [Semgrep](https://semgrep.dev/blog/2025/remote-code-execution-security-bug-in-react-server-components-patched); [InfoQ](https://infoq.com/news/2025/12/CVE-2025-55182-react-server-func); [Next.js Dec 11 update](https://nextjs.org/blog/security-update-2025-12-11.md)
- FastAPI SSE sets `X-Accel-Buffering: no`, so nginx streams events without buffering. — [FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/)

### Inferences
- Even with static export, keep Next.js on the newest 16.4.x. Build-time code still runs, and `npm audit`/OSV will flag the dependency. Run it in CI under the repo's existing OSV-Scanner and 14-day pin rule.
- Demo API design (standard practice; no 2026-specific source fetched): GET-only public endpoints; a dedicated Postgres role with SELECT only on a demo schema or snapshot (never the live `stream` database's write role); per-IP rate limits at the reverse proxy and in the app; a cap on concurrent SSE connections per IP and overall (each SSE connection is a held socket, so this is the main DoS lever); response size limits and pagination; no secrets in `NEXT_PUBLIC_*` variables (anything in the client bundle is public); a strict CSP, `frame-ancestors 'none'`, `X-Content-Type-Options`, and HSTS set at the web server (static export cannot set headers itself); admin pages not in the public build at all, behind separate auth or reachable only over the private network. A CDN/proxy such as Cloudflare in front adds DDoS absorption and hides the origin, at the cost of buffering rules for `text/event-stream`, which need checking.
- Replayed demo traffic from the validation window (already label-free) keeps the public demo away from the champion's real decision path.

### Gaps
- OWASP and Cloudflare documentation on SSE behind a CDN and on rate-limit patterns was not fetched in this pass. The practices above come from my general knowledge, not cited.
- Exact affected ranges for the May-Aug 2026 advisories come from secondary trackers. Confirm on the GHSA pages before citing them publicly.

## Accessibility and dark mode basics for dashboards

### Takeaway
WCAG 2.2 SC 1.4.11 (AA) requires 3:1 contrast for chart lines, bars, segments and markers against their background and against adjacent series. Text needs 4.5:1. Charts and filters must be keyboard usable with visible focus, and the data should also be available as a table. No source found covered dark mode specifically. Re-check every palette against the dark background.

### Cited Findings
- SC 1.4.11 Non-text Contrast (AA): parts of graphics required to understand the content need 3:1. — [W3C Understanding 1.4.11](https://w3.org/WAI/WCAG22/Understanding/non-text-contrast)
- It applies to chart lines, bars, segments, data points and markers. A common failure is adjacent colors that pass alone but fail 3:1 against each other, and red-green pairs. Only 4 of 10 colors in Tableau's "colorblind-friendly" palette reach 3:1 on white, so dark borders between segments are an easy fix. — [Pearson guideline](https://www.pearson.com/accessibility-guidelines/perceivable-principle/non-text-contrast.html); [uxdesign.cc](https://uxdesign.cc/3-color-contrast-mistakes-designers-still-make-68cc224735b3)
- Make charts, tooltips and filters usable with a keyboard, include a data table when possible, and keep text and markers at 4.5:1. — [NHS Scotland Turas](https://www.turasdesignsystem.nhs.scot/design/data-visualisation/accessible-data/); [Oregon OHA guide](https://oregon.gov/oha/Digital-Accessibility/Pages/Accessible-Data-Visualizations-Quick-Guide.aspx)

### Inferences
- For an alert queue: never encode risk by color alone. Show the score number and the `cold_policy` label as text, and use shape or icon for the tier.
- Dark mode: define colors as CSS tokens, switch them with `prefers-color-scheme` plus a manual toggle, and run a contrast check on both themes in CI (e.g. axe/Playwright). shadcn/ui ships token-based themes that support this.
- An animated live stream should respect `prefers-reduced-motion`.

### Gaps
- No 2026 source on dark-mode chart palettes or `prefers-color-scheme` practice for data visualization was retrieved.
- No check of whether WCAG 3 drafts change chart guidance as of Nov 2026.
