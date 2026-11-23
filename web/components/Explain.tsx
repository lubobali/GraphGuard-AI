import type { ReactNode } from "react";
import s from "./Explain.module.css";

// S7.18: longer explanations stay one click away, closed by default (a native <details>:
// keyboard-usable, and closed text is not read out until opened).
export default function Explain({ label = "What is this?", children }: { label?: string; children: ReactNode }) {
  return (
    <details className={s.explain}>
      <summary>{label}</summary>
      <div className={s.body}>{children}</div>
    </details>
  );
}
