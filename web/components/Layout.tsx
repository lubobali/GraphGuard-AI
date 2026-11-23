import Link from "next/link";
import { useRouter } from "next/router";
import type { ReactNode } from "react";
import s from "./Layout.module.css";

const NAV = [
  { href: "/", label: "Queue" },
  { href: "/about/", label: "About" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useRouter();
  return (
    <>
      <div className={s.banner} role="note">
        <div className="wrap">
          <strong>Synthetic data.</strong> IBM AMLworld simulator, validation window 6–8 Sep
          2022. No real people or banks. Every number here is measured on that window.
        </div>
      </div>
      <header className={s.header}>
        <div className={`wrap ${s.bar}`}>
          <Link href="/" className={s.brand}>
            GraphGuard <span className={s.sub}>money laundering alerts</span>
          </Link>
          <nav aria-label="Main">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href}
                className={pathname === n.href.replace(/\/$/, "") || pathname === n.href ? s.on : s.link}>
                {n.label}
              </Link>
            ))}
          </nav>
        </div>
        <p className={`wrap ${s.tagline}`}>
          GraphGuard finds likely money laundering in bank payments and gives investigators a
          list to check, worst first.
        </p>
      </header>
      <main className="wrap">{children}</main>
      <footer className={`wrap ${s.footer}`}>
        A portfolio project. The model is XGBoost on transaction and graph features; the
        queue and every count come from the evaluation on the validation window.
      </footer>
    </>
  );
}
