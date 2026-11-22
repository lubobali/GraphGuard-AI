import dagre from "@dagrejs/dagre";
import { Background, Controls, Handle, MarkerType, Position, ReactFlow } from "@xyflow/react";
import type { Edge, Node, NodeProps } from "@xyflow/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { money, playOrder, toFlow } from "../lib/caseLogic.js";
import s from "./RingGraph.module.css";

// The ring as of the alert (S7.5 data), left to right in time. Accounts are nodes, payments
// are edges. Play reveals the money in time order; a table holds the same payments.
type Graph = Parameters<typeof toFlow>[0];
type AccountData = { name: string; bank: string; kind: string };
const NW = 160, NH = 54;
const MIN_READABLE = 0.75; // below this the 11-12 px labels are unreadable (screenshot #21)

function AccountNode({ data }: NodeProps<Node<AccountData>>) {
  return (
    <div className={`${s.node} ${s[data.kind] ?? ""}`}>
      <Handle type="target" position={Position.Left} className={s.handle} />
      <div className={s.name}>{data.name}</div>
      <div className={s.bank}>{data.kind === "sender" ? "sender · " : data.kind === "receiver" ? "receiver · " : ""}{data.bank}</div>
      <Handle type="source" position={Position.Right} className={s.handle} />
    </div>
  );
}
const nodeTypes = { account: AccountNode };

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

export default function RingGraph({ graph, ringTx }: { graph: Graph; ringTx: Set<number> | null }) {
  const flow = useMemo(() => toFlow(graph), [graph]);
  const { nodes, size } = useMemo(() => layout(flow), [flow]);
  const [dark, setDark] = useState(false);
  // Never open below a readable zoom: a wide ring opens centred, with a note to pan or fit.
  const box = useRef<HTMLDivElement>(null);
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const w = box.current?.clientWidth ?? 0;
    setWide(w > 0 && (w / size.w) < MIN_READABLE);
  }, [size.w]);
  useEffect(() => {
    const q = window.matchMedia?.("(prefers-color-scheme: dark)");
    const read = () => {
      const t = document.documentElement.dataset.theme;
      setDark(t ? t === "dark" : !!q?.matches);
    };
    read();
    q?.addEventListener?.("change", read);
    return () => q?.removeEventListener?.("change", read);
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
  const edges: Edge[] = flow.edges.map((e: ReturnType<typeof toFlow>["edges"][number]) => {
    const inRing = ringTx !== null && e.tx !== null && ringTx.has(e.tx);
    const on = e.tx === null || visible.has(e.id);
    const color = inRing ? "var(--ring-hl)" : e.alert ? "var(--accent)" : "var(--edge)";
    return {
      id: e.id, source: e.source, target: e.target,
      label: e.amount !== null ? money(e.amount, e.currency) : undefined,
      labelStyle: { fontSize: 11, fill: "var(--ink-2)" },
      labelBgStyle: { fill: "var(--surface)" },
      style: { stroke: color, strokeWidth: e.alert || inRing ? 3 : 1.5,
        strokeDasharray: e.role === "more" ? "4 4" : undefined, opacity: on ? 1 : 0.12 },
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
      animated: playing && on && order[shown - 1] === e.id,
    };
  });

  function play() {
    if (reduced) { setShown(order.length); return; }
    setShown(0);
    setPlaying(true);
  }

  const rows = order.map((id: string) => flow.edges.find((e: { id: string }) => e.id === id)!);
  const nameOf = (id: string) => flow.nodes.find((n: { id: string }) => n.id === id)?.name ?? id;

  return (
    <div>
      <div className={s.toolbar}>
        <button type="button" onClick={play} className={s.btn} disabled={playing}>
          {playing ? "Playing…" : "▶ Play the money in time order"}
        </button>
        <span className="muted">
          {graph.window_hours} h before the alert · nothing after it · at most {graph.cap} payments per account and direction
        </span>
      </div>
      {wide && <p className="muted" style={{ fontSize: 12, margin: "0 0 6px" }}>Wide ring: drag to see more, or press ⛶ (bottom left) to see it all.</p>}
      <div ref={box} className={s.canvas} style={{ height: canvasHeight(size.h) }} aria-hidden="true">
        {/* colorMode: the controls and attribution were light-on-dark blanks (screenshots) */}
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.2}
          colorMode={dark ? "dark" : "light"} fitViewOptions={{ padding: 0.08, minZoom: MIN_READABLE }}
          nodesConnectable={false} elementsSelectable={false} proOptions={{ hideAttribution: false }}>
          <Background gap={24} size={1} color="var(--grid)" />
          <Controls showInteractive={false} fitViewOptions={{ padding: 0.08 }} />
        </ReactFlow>
      </div>
      <ul className={s.legend}>
        <li><span className={s.swatch} style={{ background: "var(--accent)" }} />the alert</li>
        <li><span className={s.swatch} style={{ background: "var(--edge)" }} />earlier payment</li>
        {ringTx && <li><span className={s.swatch} style={{ background: "var(--ring-hl)" }} />in the laundering ring (answer key)</li>}
        <li><span className={s.swatchDash} />more payments, not drawn</li>
      </ul>
      <details className={s.table}>
        <summary>The same payments as a table ({rows.length})</summary>
        <table>
          <thead><tr><th scope="col">When</th><th scope="col">From</th><th scope="col">To</th><th scope="col">Amount</th><th scope="col">Role</th></tr></thead>
          <tbody>
            {rows.map((e: ReturnType<typeof toFlow>["edges"][number]) => (
              <tr key={e.id} className={e.alert ? s.alertRow : ringTx?.has(e.tx!) ? s.ringRow : undefined}>
                <td className="num">{e.t?.slice(5, 16)}</td>
                <td>{nameOf(e.source)}</td>
                <td>{nameOf(e.target)}</td>
                <td className="num">{money(e.amount!, e.currency!)}</td>
                <td>{e.role}{ringTx?.has(e.tx!) ? " · in ring" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
