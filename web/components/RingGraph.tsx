import dagre from "@dagrejs/dagre";
import { Background, BaseEdge, Controls, EdgeLabelRenderer, getBezierPath, Handle, MarkerType, Position, ReactFlow } from "@xyflow/react";
import type { Edge, EdgeProps, Node, NodeProps } from "@xyflow/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { money, nodeRole, playOrder, roleText, stepCaption, stepNumbers, toFlow } from "../lib/caseLogic.js";
import Explain from "./Explain";
import s from "./RingGraph.module.css";

// The ring as of the alert (S7.5 data), left to right in time. Accounts are nodes, payments
// are edges. Play reveals the money in time order; a table holds the same payments.
type Graph = Parameters<typeof toFlow>[0];
type AccountData = { name: string; bank: string; kind: string };
const NW = 160, NH = 64; // room for the role line on the sender and receiver (S7.14)
const MIN_READABLE = 0.75; // below this the 11-12 px labels are unreadable (screenshot #21)

function AccountNode({ data }: NodeProps<Node<AccountData>>) {
  return (
    <div className={`${s.node} ${s[data.kind] ?? ""}`}>
      <Handle type="target" position={Position.Left} className={s.handle} />
      {nodeRole(data.kind) && <div className={s.role}>{nodeRole(data.kind)}</div>}
      <div className={s.name}>{data.name}</div>
      <div className={s.bank}>{data.bank}</div>
      <Handle type="source" position={Position.Right} className={s.handle} />
    </div>
  );
}
const nodeTypes = { account: AccountNode };

// S8b.1: amounts drawn in their own layer above every arrow (in the SVG, a later arrow was
// painted over an earlier arrow's amount and both testers could not read them).
function MoneyEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style, markerEnd, label }: EdgeProps) {
  const [path, x, y] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
  return (
    <>
      <BaseEdge id={id} path={path} style={style} markerEnd={markerEnd} />
      {label && (
        <EdgeLabelRenderer>
          <div className={s.edgeLabel} style={{ transform: `translate(-50%, -50%) translate(${x}px, ${y}px)` }}>{label}</div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
const edgeTypes = { money: MoneyEdge };

function layout(flow: ReturnType<typeof toFlow>) {
  const g = new dagre.graphlib.Graph();
  // ranksep leaves room for an amount label between columns (labels ran into boxes at 110)
  // and stays narrow enough that a 5-column ring is still readable (180 made #21 tiny)
  g.setGraph({ rankdir: "LR", nodesep: 26, ranksep: 140, marginx: 10, marginy: 10 });
  g.setDefaultEdgeLabel(() => ({}));
  flow.nodes.forEach((n: { id: string }) => g.setNode(n.id, { width: NW, height: NH }));
  flow.edges.forEach((e: { source: string; target: string }) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  const size = { w: g.graph().width ?? 600, h: g.graph().height ?? 300 };
  const nodes = flow.nodes.map((n: { id: string; name: string; bank: string; kind: string }) => {
    const p = g.node(n.id);
    return { id: n.id, type: "account", position: { x: p.x - NW / 2, y: p.y - NH / 2 },
      data: { name: n.name, bank: n.bank, kind: n.kind } } as Node<AccountData>;
  });
  return { nodes, size };
}

/** Canvas height that keeps text readable: a tall ring gets a tall canvas (case #1 shrank
 *  to unreadable in 420 px), within 320-760 px. */
function canvasHeight(h: number) {
  return Math.round(Math.min(760, Math.max(320, h * 0.85 + 40)));
}

// `compact` (S7.18, the tour): one short how-to line, no window caption, the table closed.
export default function RingGraph({ graph, ringTx, compact = false }: { graph: Graph; ringTx: Set<number> | null; compact?: boolean }) {
  const flow = useMemo(() => toFlow(graph), [graph]);
  const { nodes, size } = useMemo(() => layout(flow), [flow]);
  const [dark, setDark] = useState(true);
  // Never open below a readable zoom: a wide ring opens centred, with a note to pan or fit.
  const box = useRef<HTMLDivElement>(null);
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const w = box.current?.clientWidth ?? 0;
    setWide(w > 0 && (w / size.w) < MIN_READABLE);
  }, [size.w]);
  useEffect(() => {
    // S8b.4b: dark unless the visitor chose light; follows the header switch at once
    const root = document.documentElement;
    const read = () => setDark(root.dataset.theme !== "light");
    read();
    const watch = new MutationObserver(read);
    watch.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
    return () => watch.disconnect();
  }, []);
  const order = useMemo(() => playOrder(flow.edges), [flow]);
  const [shown, setShown] = useState<number>(order.length);
  const [playing, setPlaying] = useState(false);
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (!playing) return;
    if (shown >= order.length) { setPlaying(false); return; }
    const t = setTimeout(() => setShown(shown + 1), 700);
    return () => clearTimeout(t);
  }, [playing, shown, order.length]);

  const visible = new Set(order.slice(0, shown));
  const steps = useMemo(() => stepNumbers(flow.edges), [flow]);
  const stepping = shown < order.length; // a step is in focus: show it moving
  const current = shown > 0 ? order[shown - 1] : null;
  const edges: Edge[] = flow.edges.map((e: ReturnType<typeof toFlow>["edges"][number]) => {
    const inRing = ringTx !== null && e.tx !== null && ringTx.has(e.tx);
    const on = e.tx === null || visible.has(e.id);
    // the alert stays blue even when it is in the scheme: you must still see which one was flagged
    const color = e.alert ? "var(--accent)" : inRing ? "var(--ring-hl)" : "var(--edge)";
    return {
      id: e.id, source: e.source, target: e.target, type: "money",
      label: e.amount !== null ? `${steps.get(e.id)} · ${money(e.amount, e.currency)}` : undefined,
      style: { stroke: color, strokeWidth: e.alert || inRing ? 3 : 1.5,
        strokeDasharray: e.role === "more" ? "4 4" : undefined, opacity: on ? 1 : 0.12 },
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
      animated: (playing || stepping) && current === e.id,
    };
  });

  function play() {
    if (reduced) { setShown(order.length); return; }
    setShown(0);
    setPlaying(true);
  }
  // Step through (S7.14): Back / Next one payment at a time, in time order.
  const step = (d: number) => { setPlaying(false); setShown((n) => Math.max(1, Math.min(order.length, (n >= order.length && d > 0 ? 0 : n) + d))); };
  function keys(e: React.KeyboardEvent) {
    if (e.key === "ArrowRight") { e.preventDefault(); step(1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); }
  }

  const rows = order.map((id: string) => flow.edges.find((e: { id: string }) => e.id === id)!);
  const nameOf = (id: string) => flow.nodes.find((n: { id: string }) => n.id === id)?.name ?? id;

  return (
    <div>
      <p className={s.howto}>Each box is an account, each arrow a payment. The blue arrow is the flagged one.</p>
      {!compact && (
        <Explain>
          <p>Arrows are numbered in time order. Everything here happened <strong>before</strong> the
          flagged payment: {graph.window_hours} hours before it, nothing after it, and at most {graph.cap} payments
          per account and direction (&quot;+N more&quot; counts the rest). Step through to see where the money
          came from and where it went.</p>
        </Explain>
      )}
      <div className={s.toolbar} onKeyDown={keys}>
        <button type="button" onClick={() => step(-1)} className={s.btn2} disabled={shown <= 1 || playing} aria-label="Previous payment">← Back</button>
        <button type="button" onClick={() => step(1)} className={s.btn2} disabled={playing} aria-label="Next payment">Next →</button>
        <button type="button" onClick={play} className={s.btn} disabled={playing}>
          {playing ? "Playing…" : "▶ Play all"}
        </button>
      </div>
      {wide && <p className="muted" style={{ fontSize: 12, margin: "0 0 6px" }}>Wide ring: drag to see more, or press ⛶ (bottom left) to see it all.</p>}
      {stepping && current && (
        <p className={s.caption} aria-live="polite">
          {stepCaption(flow.edges.find((e: { id: string }) => e.id === current)!, shown, order.length, nameOf)}
        </p>
      )}
      <div ref={box} className={s.canvas} style={{ height: canvasHeight(size.h) }} aria-hidden="true">
        {/* colorMode: the controls and attribution were light-on-dark blanks (screenshots) */}
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} fitView minZoom={0.2}
          colorMode={dark ? "dark" : "light"} fitViewOptions={{ padding: 0.08, minZoom: MIN_READABLE }}
          nodesConnectable={false} elementsSelectable={false} proOptions={{ hideAttribution: false }}>
          <Background gap={24} size={1} color="var(--grid)" />
          <Controls showInteractive={false} fitViewOptions={{ padding: 0.08 }} />
        </ReactFlow>
      </div>
      <ul className={s.legend}>
        <li><span className={s.swatch} style={{ background: "var(--accent)" }} />the alert</li>
        <li><span className={s.swatch} style={{ background: "var(--edge)" }} />earlier payment</li>
        {ringTx && <li><span className={s.swatch} style={{ background: "var(--ring-hl)" }} />in the laundering scheme (answer key)</li>}
        <li><span className={s.swatchDash} />more payments, not drawn</li>
      </ul>
      <details className={s.table} open={!compact && rows.length <= 12}>
        <summary>The same payments as a table ({rows.length})</summary>
        <table>
          <thead><tr><th scope="col">#</th><th scope="col">When</th><th scope="col">From</th><th scope="col">To</th><th scope="col">Amount</th><th scope="col">What it is</th></tr></thead>
          <tbody>
            {rows.map((e: ReturnType<typeof toFlow>["edges"][number]) => (
              <tr key={e.id} className={e.alert ? s.alertRow : ringTx?.has(e.tx!) ? s.ringRow : undefined}>
                <td className="num">{steps.get(e.id)}</td>
                <td className="num">{e.t?.slice(5, 16)}</td>
                <td>{nameOf(e.source)}</td>
                <td>{nameOf(e.target)}</td>
                <td className="num">{money(e.amount!, e.currency!)}</td>
                <td>{roleText(e.role)}{ringTx?.has(e.tx!) ? " · in the scheme (answer key)" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
