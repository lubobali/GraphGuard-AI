// The demo API (S7.6), same origin. Every number on screen comes from here.
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
  from_account?: string; to_account?: string;
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
  return (await r.json()) as T;
}
