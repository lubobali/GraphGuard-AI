// The demo API (S7.6), same origin. Every number on screen comes from here.
import { plainNames } from "./names.js";
export type Ranking = {
  ranking: string; k: number; caught: number; missed: number; precision: number;
  recall: number; rings_caught: number; rings_touched: number; rings_total: number;
};
export type Capacity = { per_day: number; k: number; rankings: Record<string, Ranking> };
export type Curve = Record<string, [number, number, number][]>;
export type QueueGroup = {
  alerts: number; event_id: number; rank: number; percentile: number; event_time: string;
  due: string; amount_paid: number; payment_currency: string; payment_format: string;
  cold_policy: string; rules: string[]; from_name: string | null; from_bank_name: string | null;
  from_account?: string; to_account?: string; has_ai?: boolean;
  to_name: string | null; to_bank_name: string | null; top_reason: string | null;
};
export type Queue = { k: number; page: number; page_size: number; alerts: number;
  accounts: number; groups: QueueGroup[] };
export type Performance = {
  measured_offline: Ranking | null;
  confirmed_so_far: { known: number; laundering: number; latest: string | null };
  laundering_in_window: number; note: string;
};
export type Meta = { banner: string; window_days: number; build: { model_version: string;
  built_at: string; window: string[] } | null };

export async function get<T>(path: string): Promise<T> {
  const r = await fetch(`/api${path}`, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return plainNames(await r.json()) as T; // S8b.1: business types in plain words
}

/** S7.15: a visitor's cases (their own and their copy of Sam's). */
export type DecisionCase = { event_id: number; owner: string; rank: number; from_name: string | null;
  to_name: string | null; amount_paid: number; payment_currency: string; state: string;
  decision: string | null; code: string | null; reason: string | null; sar_due: string | null;
  acted: boolean; is_laundering: boolean | null };
export type Decisions = { cases: DecisionCase[]; score: { decided: number; right: number; model_right: number } };

/** S7.16: the manager's page. */
export type Manager = {
  scope: "me" | "all"; as_of: string; decided: number; escalated: number; closed: number;
  waiting_review: number; sent_back: number; final_escalated: number; final_closed: number;
  reviews_done: number; matched: number; model_right: number; ai_agreement: { cases: number; agree: number };
  ai_strong_against: { cases: number; strong: number };
  backlog: { total: number; under_24h: number; h24_48: number; over_48h: number; oldest: string | null };
  qa: { event_id: number; code: string; ok: boolean; reason?: string }[];
};
