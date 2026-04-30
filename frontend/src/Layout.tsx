import { useEffect } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { apiJson } from "./api";
import { FloatingOrbs } from "./FloatingOrbs";

const tabs = [
  { to: "/events", label: "События" },
  { to: "/incidents", label: "Инциденты" },
  { to: "/diagnosis", label: "Диагностика" },
  { to: "/dashboard", label: "Дашборд" },
] as const;

export function Layout() {
  const { pathname } = useLocation();

  useEffect(() => {
    void apiJson(`/admin/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        payload: {
          route: pathname,
          ts: new Date().toISOString(),
          screen: { w: window.innerWidth, h: window.innerHeight },
          lang: navigator.language,
        },
        source: "frontend",
      }),
    }).catch(() => {});
  }, [pathname]);

  return (
    <>
      <FloatingOrbs />
      <div className="app-shell">
        <header className="app-header">
          <div className="app-header-inner">
            <NavLink to="/events" className="brand-link" end>
              <h1 className="brand">
                AI Editor
                <span>Operations & diagnostics</span>
              </h1>
            </NavLink>
            <nav className="nav-tabs" aria-label="Разделы">
              {tabs.map(({ to, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) => (isActive ? "nav-tab active" : "nav-tab")}
                >
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
        </header>
        <main className="layout page-main">
          <Outlet />
        </main>
      </div>
    </>
  );
}
