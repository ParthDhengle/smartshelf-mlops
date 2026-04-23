"use client";

import { useEffect, useState } from "react";
import { getKPIs } from "../lib/api";
import KPICard from "../components/KPICard";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell,
} from "recharts";

const generateTrendData = () => {
  const data = [];
  const base = 50000;
  for (let i = 30; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    data.push({
      date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      revenue: Math.round(base + Math.random() * 20000 + i * 200),
      demand: Math.round(300 + Math.random() * 150 + Math.sin(i / 5) * 50),
      profit: Math.round(base * 0.3 + Math.random() * 5000),
    });
  }
  return data;
};

const categoryData = [
  { name: "Dairy", value: 28, color: "#6366f1" },
  { name: "Beverages", value: 22, color: "#22d3ee" },
  { name: "Snacks", value: 18, color: "#f59e0b" },
  { name: "Fresh", value: 16, color: "#10b981" },
  { name: "Household", value: 16, color: "#ef4444" },
];

export default function DashboardPage() {
  const [kpis, setKpis] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [trendData] = useState(generateTrendData);

  useEffect(() => {
    getKPIs()
      .then(setKpis)
      .catch((err) => {
        setError(err.message || "Failed to fetch KPIs");
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="loading-spinner">
        <div className="spinner" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">❌</div>
        <h3 style={{color: "var(--text-primary)"}}>Error Loading Dashboard</h3>
        <p style={{color: "var(--danger)"}}>{error}</p>
        <p style={{marginTop: "1rem"}}>Please ensure the backend API is running on localhost:8000</p>
      </div>
    );
  }

  const kpiCards = [
    { label: "Total Revenue", value: `₹${(kpis.total_revenue / 100000).toFixed(1)}L`, icon: "💰", color: "#6366f1", change: "+12.3%" },
    { label: "Total Profit", value: `₹${(kpis.total_profit / 100000).toFixed(1)}L`, icon: "📈", color: "#10b981", change: "+8.7%" },
    { label: "Avg Margin", value: `${kpis.avg_margin_pct}%`, icon: "📊", color: "#22d3ee", change: "+2.1%" },
    { label: "Products", value: kpis.total_products, icon: "📦", color: "#f59e0b" },
    { label: "Stores", value: kpis.total_stores, icon: "🏪", color: "#8b5cf6" },
    { label: "Stockout Rate", value: `${kpis.stockout_rate}%`, icon: "⚠️", color: kpis.stockout_rate > 5 ? "#ef4444" : "#10b981", change: kpis.stockout_rate > 5 ? "+1.2%" : "-0.8%" },
    { label: "Avg Daily Demand", value: kpis.avg_demand.toFixed(1), icon: "🛒", color: "#ec4899" },
    { label: "Active Promos", value: kpis.active_promos, icon: "🎯", color: "#14b8a6" },
  ];

  return (
    <div>
      <div className="page-header animate-in">
        <h2>Dashboard</h2>
        <p>Real-time overview of your Smart Shelf retail operations</p>
      </div>

      <div className="kpi-grid">
        {kpiCards.map((kpi, i) => (
          <KPICard key={kpi.label} {...kpi} index={i} />
        ))}
      </div>

      <div className="chart-grid">
        {/* Revenue Trend */}
        <div className="chart-card animate-in">
          <h3>Revenue Trend (30 Days)</h3>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="date" tick={{ fill: "#6b6b80", fontSize: 11 }} />
              <YAxis tick={{ fill: "#6b6b80", fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: "#1a1a24",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 8,
                  color: "#f1f1f7",
                }}
              />
              <Area type="monotone" dataKey="revenue" stroke="#6366f1" fill="url(#revenueGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Category Distribution */}
        <div className="chart-card animate-in">
          <h3>Sales by Category</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={categoryData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={3}
                dataKey="value"
              >
                {categoryData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#1a1a24",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 8,
                  color: "#f1f1f7",
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", justifyContent: "center", gap: "1rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
            {categoryData.map((c) => (
              <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: c.color }} />
                {c.name} ({c.value}%)
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
