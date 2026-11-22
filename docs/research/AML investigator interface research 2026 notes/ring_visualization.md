# Visualizing laundering rings in a React/Next.js investigator dashboard (Nov 2026)

Scope: draw laundering rings (~8 accounts, fan-out / pass-through / cycle, ~3 days, ordinary amounts) so a non-technical manager gets the shape at a glance. Data pulled live on 2026-11-22 from the npm registry (`registry.npmjs.org/<pkg>`), npm downloads API (last 30 days, 2026-10-22 to 2026-11-20), GitHub API (stars, last push, open issues) and bundlephobia (min / gzip for the latest version). Treat the numbers as a snapshot.

## Q1. Which library: license, maintenance, React, bundle, performance, temporal features, layouts, edge styling

### Takeaway
For a ring of about 8 to 50 nodes, raw performance doesn't matter. What matters is layout control and SVG-level styling and animation. **React Flow (@xyflow/react 13, MIT)** is the best fit for the hero "money flow" view: React-native nodes, the smallest bundle, dagre/ELK layouts, custom animated edges. **Cytoscape.js 3.35 (MIT)** is the best fit for the "explore the neighbourhood" view, since it has built-in circle/concentric/breadthfirst layouts, dagre/ELK extensions, and an optional WebGL renderer. Sigma.js + graphology is the open-source choice if the graph ever grows to thousands of nodes. AntV G6 v5 and reagraph are capable, but each weighs about 400 KB gzip. The commercial toolkits (KeyLines/ReGraph, Ogma) are quote-only and out of scope for a portfolio project.

### Cited findings

**Snapshot table (versions, dates, licenses from the npm registry; bundle from bundlephobia; stars/issues from GitHub API, 2026-11-22)**

| Library | Latest | Released | License | npm downloads / 30 d | Stars | Open issues | Last push | Min / gzip |
|---|---|---|---|---|---|---|---|---|
| cytoscape | 3.35.0 | 2026-11-10 | MIT | 113.8M | 11.3k | 31 | 2026-11-10 | 442 KB / 139 KB |
| sigma (+ graphology) | 4.0.6 | 2026-11-10 | MIT | 3.08M | 12.2k | 2 | 2026-11-10 | 376 KB / 97 KB |
| graphology | 0.26.0 | 2025-01-26 | MIT | — | — | — | — | — |
| @react-sigma/core | 6.0.0 | 2026-10-14 | MIT | — | — | — | — | — |
| @antv/g6 | 5.1.1 | 2026-05-08 | MIT | 1.41M | 12.4k | 337 | 2026-11-13 | 1,401 KB / 400 KB |
| @xyflow/react (React Flow) | 13.0.2 | 2026-11-17 | MIT | 90.7M | 39.1k | 141 | 2026-11-19 | 262 KB / 88 KB |
| vis-network | 10.1.5 | 2026-11-08 | Apache-2.0 OR MIT | 4.76M | 3.6k | 350 | 2026-11-21 | 414 KB / 118 KB |
| reagraph | 4.32.0 | 2026-06-25 | Apache-2.0 | 0.46M | 1.1k | 13 | 2026-06-25 | 1,380 KB / 385 KB |
| d3-force | 3.0.1 | 2026-11-03 | ISC | 161.5M | 2.0k | 23 | 2026-11-21 | (small; not measured) |
| react-force-graph-2d | 1.29.2 | 2026-09-29 | MIT | 5.61M | 3.4k (repo) | 218 | 2026-09-29 | not measured |
| cytoscape-dagre / cytoscape-elk | 4.1.0 / 2.4.0 | 2026-11-10 | MIT | — | — | — | — | — |
| @dagrejs/dagre | 3.1.3 | 2026-10-24 | MIT | — | — | — | — | — |
| elkjs | 0.12.1 | 2026-10-28 | **EPL-2.0 OR GPL-3.0-or-later** | — | 2.9k | 98 | 2026-11-09 | — |
| d3-sankey | 0.12.3 | **2019-09-02** | BSD-3-Clause | — | — | — | — | — |

Sources: [npm registry](https://registry.npmjs.org/cytoscape), [npm downloads API](https://api.npmjs.org/downloads/point/last-month/cytoscape), [GitHub API](https://api.github.com/repos/xyflow/xyflow), [bundlephobia](https://bundlephobia.com/package/@xyflow/react). The same query was run for each package. Download counts are inflated by transitive use: cytoscape, for example, is pulled in by other tools. Treat them as a "widely used" signal, not a popularity ranking.

**Cytoscape.js**
- Cytoscape.js has had a WebGL renderer since 3.31 (Jan 2025 preview), enabled with `renderer: { name: 'canvas', webgl: true }`. On an M1 MacBook it measured about 1,200 nodes / 16,000 edges at ~20 FPS with canvas versus >100 FPS with WebGL, and about 3,200 nodes / 68,000 edges at ~3 FPS versus ~10 FPS — [Cytoscape.js blog, WebGL preview](https://blog.js.cytoscape.org/2025/01/13/webgl-preview/)
- The WebGL mode has limits: no dashed edges, no overlays or underlays, triangle arrows only, a single centre label on edges, and solid colours only (no gradients). Taxi and segmented edges fall back to bezier — [same post](https://blog.js.cytoscape.org/2025/01/13/webgl-preview/). Dashed "pending" edges and taxi routing therefore need the default canvas renderer, which is fine at ring scale.
- Release history: 3.31 (2025-01-13), 3.32 (2025-05-01), 3.33 (2025-07-28) are on the blog — [blog](https://blog.js.cytoscape.org/). Zenodo archives show v3.33.2 on 2026-04-06 and v3.34.0 on 2026-06-02 — [Zenodo](https://zenodo.org/records/891013/latest). The registry shows 3.35.0 on 2026-11-10 (table above).

**Sigma.js + graphology**
- Sigma is WebGL, built on graphology, and installed as `npm install sigma graphology`. v3 added instanced rendering and GPU picking — [sigma README v3.0.3](https://unpkg.com/sigma@3.0.3/README.md)
- v4.0.6 is current on sigmajs.org, which advertises React/Angular/Vue/vanilla support and relies on graphology for layouts, metrics and community detection. The page gives no benchmarks — [sigmajs.org](https://www.sigmajs.org/). @react-sigma/core 6.0.0 was released 2026-10-14 (registry).
- Its graphology companion layout package, graphology-layout-forceatlas2, last shipped a stable release (0.10.1) on 2022-10-17 (registry). It is mature, but it is not moving.

**AntV G6 v5**
- React nodes come through a separate package, `@antv/g6-extension-react`. WebGL is available via `@antv/g-webgl`, and high-performance layouts need `@antv/layout-wasm`. A built-in `OptimizeViewportTransform` behaviour helps with large graphs — [G6 v5 README](https://raw.githubusercontent.com/antvis/G6/v5/README.md), [G6 docs](https://g6.antv.antgroup.com/en/manual/behavior/optimize-viewport-transform)
- Earlier v5 issues reported React 18 friction — [GitHub issue #5700](https://www.Github.com/antvis/G6/issues/5700) — and lag when many nodes are box-selected and dragged — [G6 issues](https://github.com/antvis/G6/issues). At 337, it has the most open issues in the open-source set (table).

**React Flow (xyflow)**
- Custom edges can animate a marker along the path with SVG `<animateMotion>`. A node can also travel along an edge via CSS `offsetPath` + `offsetDistance` with the Web Animations API, and there is a simple built-in animation for the default edge — [React Flow, animating edges example](https://reactflow.dev/examples/edges/animating-edges)

**reagraph**
- It is a WebGL network graph library for React, licensed Apache-2.0 (npm and GitHub agree; one third-party site says MIT) — [npm](https://npmjs.com/package/reagraph), [GitHub](https://www.Github.com/reaviz/reagraph). No release since 2026-06-25 (registry).

**Commercial: KeyLines / ReGraph (Cambridge Intelligence), Ogma (Linkurious)**
- KeyLines (JS) and ReGraph (React) are commercially licensed SDKs, priced on request and usually sold as subscriptions. A bundle also includes KronoGraph (timeline) and MapWeave — [G2](https://www.g2.com/products/keylines-graph-visualization-toolkit/pricing), [Cambridge Intelligence procurement FAQ](https://cambridge-intelligence.com/pricing/procurement/), [Capterra ReGraph](https://www.capterra.com/p/202755/ReGraph-graph-visualization-for-React-developers/)
- Ogma is Linkurious's WebGL JS library, with an HTML5 Canvas fallback. It is commercial with no public price, and it is the engine under Linkurious Enterprise — [Neo4j blog on Linkurious](https://neo4j.com/blog/financial-services/detect-investigate-financial-crime-patterns-linkurious/), [Capterra Ogma](https://www.capterra.com/p/10011703/Ogma/). `@linkurious/ogma` is not on the public npm registry (lookup returned nothing).

**Graphistry**
- Graphistry is a GPU server-side visual graph engine. PyGraphistry (BSD-3-Clause, 2.6k stars, pushed 2026-11-22) is the Python client, positioned for "investigating fraud" — [PyPI](https://pypi.org/project/graphistry/0.34.14), [GitHub API](https://api.github.com/repos/graphistry/pygraphistry). Its closest fraud-ring demo runs a TigerGraph circle-detection query and plots the result — [PyGraphistry TigerGraph fraud demo](https://pygraphistry.readthedocs.io/en/0.52.1/demos/demos_databases_apis/tigergraph/fraud_raw_REST_calls.html)

### Inferences
- **Recommended pairing:**
  - (a) React Flow + `@dagrejs/dagre` for the alert's ring, laid out left to right by time. Each account is a real React component (name, risk badge, score), edges are custom SVG, and the animation is simple.
  - (b) Cytoscape.js (MIT, `cytoscape-dagre`) for the expandable 1–2-hop ego network, where built-in `circle`, `concentric` and `breadthfirst` layouts plus graph algorithms such as cycle-finding help.
  - One library is possible. Cytoscape alone covers both views but gives up React-component nodes. React Flow alone covers both but has no built-in force or circular layout, so that would be about 20 lines of geometry.
- **React Flow vs Cytoscape:** React Flow uses DOM/SVG per node, so it is not meant for thousands of nodes. Rings are about 8 nodes and ego nets about 50, which is well within range. Cytoscape canvas handles 1k+ nodes (WebGL figures above).
- **ELK license:** elkjs is EPL-2.0 OR GPL-3.0. EPL-2.0 is weak copyleft and fine to depend on unmodified, but it is not "permissive" in the MIT sense. dagre (MIT) is enough for a left-to-right layered layout of a ring. Use ELK only if dagre's edge routing looks messy.
- **d3-sankey** hasn't been released since 2019, and Sankey diagrams can't draw cycles (they need a DAG). For a cycle ring, use time-ordered layered layout with a back edge rather than a true Sankey.
- **Sigma** is the right escalation if Phase 10 (180M transactions) wants a "whole-network" overview. Its WebGL edge styling is more limited than SVG, which matters for amount-weighted arrows and labels.

### Gaps
- No independent 2026 benchmark comparing these libraries head to head was found. Performance numbers are vendor or library self-reports (Cytoscape) or absent (sigma v4, G6).
- No sigma v4 changelog or feature list vs v3 (edge programs, curved edges) was verified. The site doesn't describe the differences.
- I did not verify React Flow v13 breaking changes vs v12, or G6 v5.1's React 19 status.
- Built-in time-slider features: I found no source confirming that any open-source option ships a time bar. KeyLines' time bar and KronoGraph are commercial. In open source this would be custom (a range slider filtering edges by timestamp). I did not verify vis-network's or G6's timebar plugin in this pass.

## Q2. Layouts and encodings for money flow; vendor and academic examples

### Takeaway
Analyst practice (Linkurious, Neo4j Bloom) and AML visual-analytics research (Feedzai 2026, WireVis, VIS4AUI, EVA, NEVA) point the same way. Start from the alerted account or transaction. Lay out the trail as a sequence (accounts as nodes, transactions as directed edges, often grouped by bank), colour by risk, and declutter by grouping on amount and time. For a manager, use a time-ordered left-to-right layered layout with the alerted transaction highlighted and edge width = amount. Draw a cycle as a circle only when the ring is a true round trip.

### Cited findings
- **Feedzai, "The Balance between Nuance and Clarity: Decluttering Tabular Sequential Graphs to Counter Money Laundering"** (Esteves, Costa, Fallon, Bizarro; arXiv 2605.10522, v2 camera-ready 2026-07-02; author PDF labelled IEEE VIS) — [arXiv](https://arxiv.org/abs/2605.10522), [Feedzai PDF](https://research.feedzai.com/oshuzuxa/2026/07/IEEEVis__The_Balance_between_Nuance_and_Clarity__Decluttering_Tabular_Sequential_Graphs_to_Counter_Money_Laundering.pdf)
  - The "tabular sequential graph" follows transactions (edges) from the victim account that triggered the alert through accounts (nodes), with banks as rows.
  - Clutter is reduced by amount-based, time-based or combined (amount + order) grouping.
  - In an expert user study, the method that reduced the most nodes was not necessarily the most useful for analysis, and more granular graphs traded manual work against interpretation time.
- **WireVis** (IEEE VAST 2007, with Bank of America's AML division) used coordinated views over wire transactions and search-by-example for accounts with similar transaction patterns — [Chang et al. VAST 2007 PDF](https://illusioneering.cs.umn.edu/papers/chang-vast2007.pdf)
- **Other AML/fraud visual-analytics systems** — [found via search; abstracts only](https://www.scitepress.org/Papers/2012/39334)
  - VIS4AUI (Didimo, Liotta, Montecchiani 2012), on Italian AML archives
  - EVA (Leite et al., IEEE TVCG 2018), for fraud investigation and reducing false positives
  - NEVA (Computer Graphics Forum 2020), for bank-transaction fraud networks
- **Linkurious' investigation model:** individuals, companies and bank accounts are entities, money flows between accounts, and people or companies control the accounts. The graph doubles as the way to explain a case to banks and prosecutors — [Linkurious blog](https://linkurious.com/blog/investigating-money-laundering-scheme/)
- **Neo4j/Bloom AML example** (2020) — [Neo4j blog](https://neo4j.com/blog/fraud-detection/combating-money-laundering-graph-data-visualizations/)
  - Risk is colour-coded (red high, tan medium, yellow low) within circular payment flows.
  - A layering chain is drawn from the suspicious entity at the upper left outward.
  - Colour intensity encodes suspicion.
  - Executives get red/amber/green KPI dashboards rather than graphs.
- **Real-world use:** the FinCEN Files investigation used Neo4j + Linkurious over 400+ spreadsheets / 100k transactions — [Neo4j](https://neo4j.com/blog/fraud-detection/analyzing-fincen-files-data-neo4j). A vendor case study claims Ria cut investigation time by up to 80% (unverified, vendor-published) — [The Paypers](https://thepaypers.com/case-study/ria-accelerates-aml-investigations-5x-with-graph-technology--1262198)

### Inferences
- **Recommended "ring card" encoding for GraphGuard:**
  - Layout: dagre `rankdir: LR`, with rank = hop order, or a column per day across the 3-day span. The alerted transaction gets a thick accent outline or halo.
  - Edge width: a sqrt or log scale of amount, because amounts are "ordinary". A linear scale would make every hop look the same, and that sameness is itself the story: no single hop looks suspicious. Put the amount + timestamp on each edge label.
  - Node colour: model score or known status (laundering label / unknown / clean), with a shape or icon as a second channel.
  - Cycle: if the subgraph contains a cycle back to the origin, offer a "circle" toggle (Cytoscape `circle` layout, or nodes placed on a circle in React Flow) so the round trip reads as a loop.
- The Feedzai finding argues for a toggle between grouped and granular views rather than maximum decluttering.
- For the manager audience, follow Neo4j's split: a RAG summary plus one small, clean ring picture, not an explorable hairball.

### Gaps
- **Quantexa:** found no public, citable description of its graph UI encodings in this pass.
- Neo4j Bloom 2026 features (time slider, rule-based styling) were not verified; the cited Neo4j article is from 2020.
- Graphistry has no public AML-specific demo (only the TigerGraph cycle-detection notebook and a 2019 GTC talk) — [NVIDIA GTC 2019](https://developer.nvidia.com/gtc/2019/video/s9813)
- The Feedzai paper's exact visual encodings (whether time runs left to right, how amount is encoded) and its participant count were not in the abstract. The PDF linked above needs reading.

## Q3. Pitfalls (hairballs, hubs, readability, accessibility, dark mode) and animating money for a demo

### Takeaway
Hairballs come from showing too much context. Hubs come from high-degree accounts such as exchanges or merchants. The fixes are standard: start from the alert, expand 1–2 hops on demand, cap or aggregate hubs into a "+N more" node, group by amount and time (Feedzai), and use the classic canvas or SVG renderers when dashed edges or special arrows are needed. For animation, React Flow's `<animateMotion>` or `offsetPath` along edges, driven in timestamp order, gives a "money moving" demo with no extra library.

### Cited findings
- **Clutter reduction:** grouping by amount, time, or both is the studied way to reduce clutter in AML sequential graphs, and over-aggregation hurts analysis — [Feedzai / arXiv 2605.10522](https://arxiv.org/abs/2605.10522)
- **Renderer limits:** Cytoscape's WebGL renderer drops dashed edges, overlays and non-triangle arrows, and has a load delay for sprite-sheet pre-rendering with no progress indicator — [Cytoscape WebGL preview](https://blog.js.cytoscape.org/2025/01/13/webgl-preview/)
- **Animation techniques:** an SVG `<animateMotion>` dot on a custom edge, or a node moved along the edge path via `offsetPath` / `offsetDistance` with the Web Animations API (set `draggable: false` while animating; put path and animation in separate effects so the animation survives path recalculation) — [React Flow animating edges](https://reactflow.dev/examples/edges/animating-edges)
- **Scale limits:** Cytoscape canvas falls to ~3 FPS at ~3.2k nodes / 68k edges — [Cytoscape](https://blog.js.cytoscape.org/2025/01/13/webgl-preview/). A ring view should never approach this. If it does, that is a design bug (hub not capped), not a library problem.

### Inferences (design guidance, not separately sourced)
- **Hub cap:** in the ego view, if an account has more than about 15 neighbours in the window, collapse the rest into one aggregate node ("+132 counterparties, EUR 1.2M total"), expandable on click. GraphGuard already knows degree as of time T from its feature store, so use the same as-of degree to stay consistent with the leakage contract. Never show neighbours from after the alert time in a replay.
- **Readability:**
  - Keep a max of about 30 visible nodes by default.
  - Label nodes with short masked account IDs plus bank.
  - Put amounts on edges with tabular numerals.
  - Show time either as column headers (Day 1 / Day 2 / Day 3) or on edge labels.
- **Accessibility:**
  - Don't encode suspicious vs clean with red/green alone. Add shape or icon and a pattern (for example a dashed outline for "unknown label").
  - Keep 3:1 contrast for edges against the background.
  - Provide a table view of the same transactions (screen readers can't read a canvas). React Flow's DOM nodes are focusable, while canvas/WebGL libraries are opaque to assistive tech.
  - Respect `prefers-reduced-motion` and skip or step the animation.
- **Dark mode:** define node, edge and highlight colours as CSS variables (React Flow styles via CSS). For canvas libraries (Cytoscape, sigma), re-apply the stylesheet when the theme changes, because they don't read CSS variables automatically.
- **Demo-video animation recipe:**
  1. Sort the ring's edges by timestamp.
  2. Fade in edges one by one, or animate a dot with `<animateMotion dur>` proportional to the time gap (compressed).
  3. Show a running clock and running total.
  4. End on the cycle closing back to origin, with the alerted transaction pulsing.
  5. Record with the browser at fixed 1080p, or drive it with Playwright for repeatable frames.
  Cytoscape offers `ele.animate()` for style and position, but moving a particle along an edge is easier in SVG (React Flow).

### Gaps
- No user study was found on which ring layout (circle vs layered) managers grasp fastest. The recommendation rests on analyst-tool practice and the Feedzai sequential-graph work, not a manager-specific study.
- No sourced accessibility guidance specific to graph visualization libraries was collected in this pass (WCAG contrast and reduced-motion are general web standards).
- I did not verify the built-in time-bar or timeline plugins of G6 v5 or vis-network.
