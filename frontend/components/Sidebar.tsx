"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/products", label: "Products Admin", icon: "📦" },
  { href: "/demand", label: "Demand Forecast", icon: "📈" },
  { href: "/pricing", label: "Price Optimization", icon: "💰" },
  { href: "/inventory", label: "Inventory", icon: "🏭" },
  { href: "/admin", label: "Admin Panel", icon: "⚙️" },
  { href: "/simulator", label: "Sales Simulator", icon: "🎮" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-brand-icon">🛒</span>
        <h1>SmartShelf</h1>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-link ${pathname === item.href ? "active" : ""}`}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>
      <div
        style={{
          padding: "var(--space-md)",
          borderTop: "1px solid var(--border-subtle)",
          marginTop: "auto",
          fontSize: "0.75rem",
          color: "var(--text-muted)",
        }}
      >
        SmartShelf MLOps v1.0
      </div>
    </aside>
  );
}
