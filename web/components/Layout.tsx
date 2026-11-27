import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState, type ReactNode } from "react";
import { ROLES, readRole, roleForPath, saveRole } from "../lib/role.js";
import s from "./Layout.module.css";

const NAV = [
  { href: "/try/", label: "Try it" },
  { href: "/", label: "Queue" },
  { href: "/about/", label: "About" },
];

const SHOWN = ROLES;

function ViewAs() {
  const router = useRouter();
  const [role, setRole] = useState("investigator");
  useEffect(() => { setRole(roleForPath(router.pathname, readRole())); }, [router.pathname]);
  function pick(r: { key: string; home: string }) {
    saveRole(r.key);
    setRole(r.key);
    router.push(r.home);
  }
  return (
    <div className={s.viewAs} role="group" aria-label="View as">
      <span className={s.viewLabel}>View as</span>
      {SHOWN.map((r: { key: string; label: string; home: string }) => (
        <button key={r.key} type="button" aria-pressed={role === r.key}
          className={role === r.key ? s.roleOn : s.roleBtn} onClick={() => pick(r)}>{r.label}</button>
      ))}
    </div>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useRouter();
  return (
    <>
      <div className={s.banner} role="note">
        <div className="wrap">
          {/* S8b.1: a newcomer did not know "synthetic" or "validation window" */}
          <strong>Synthetic data.</strong> Made up by IBM&apos;s AMLworld simulator: no real people or
          banks. Every number here is measured on 2 days of it (6–8 Sep 2022).
        </div>
      </div>
      <header className={s.header}>
        <div className={`wrap ${s.bar}`}>
          <Link href="/" className={s.brand}>
            GraphGuard <span className={s.sub}>money laundering alerts</span>
          </Link>
          <ViewAs />
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
