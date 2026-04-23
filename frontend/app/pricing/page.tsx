"use client";

import { useState } from "react";
import { optimizePrice } from "../../lib/api";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";

export default function PricingPage() {
  const [productId, setProductId] = useState<number | string>(1);
  const [storeId, setStoreId] = useState<number | string>(1);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleOptimize = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await optimizePrice({
        product_id: Number(productId),
        store_id: Number(storeId),
      });
      setResult(data);
    } catch (e) {
      setError(e.message);
      // Mock
      const current = 120 + Math.random() * 80;
      const optimal = current * (0.9 + Math.random() * 0.3);
      setResult({
        product_id: Number(productId),
        store_id: Number(storeId),
        current_price: Math.round(current),
        optimal_price: Math.round(optimal * 100) / 100,
        expected_demand: Math.round(15 + Math.random() * 20),
        expected_profit: Math.round(optimal * 0.3 * 20 * 100) / 100,
        profit_uplift_pct: Math.round((Math.random() * 20 - 5) * 10) / 10,
        price_elasticity: Math.round(-1.5 + Math.random() * 100) / 100,
      });
    } finally {
      setLoading(false);
    }
  };

  const comparisonData = result
    ? [
        { label: "Current Price", value: result.current_price, fill: "#6b6b80" },
        { label: "Optimal Price", value: result.optimal_price, fill: "#6366f1" },
        { label: "Expected Profit", value: result.expected_profit, fill: "#10b981" },
      ]
    : [];

  return (
    <div>
      <div className="page-header animate-in">
        <h2>Price Optimization</h2>
        <p>Find the profit-maximizing price for each product-store</p>
      </div>

      {/* Form */}
      <div className="card animate-in" style={{ marginBottom: "var(--space-xl)" }}>
        <div style={{ display: "flex", gap: "var(--space-md)", alignItems: "flex-end", flexWrap: "wrap" }}>
          <div className="form-group">
            <label className="form-label">Product ID</label>
            <input className="form-input" type="number" value={productId} onChange={(e) => setProductId(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Store ID</label>
            <input className="form-input" type="number" value={storeId} onChange={(e) => setStoreId(e.target.value)} />
          </div>
          <button className="btn btn-primary" onClick={handleOptimize} disabled={loading} style={{ marginBottom: "var(--space-md)" }}>
            {loading ? "Optimizing..." : "💰 Optimize Price"}
          </button>
        </div>
        {error && <p style={{ color: "var(--warning)", fontSize: "0.8rem", marginTop: "var(--space-sm)" }}>⚠️ Using mock data</p>}
      </div>

      {/* Results */}
      {result && (
        <div className="chart-grid">
          {/* Price Comparison */}
          <div className="card animate-in">
            <h3 style={{ marginBottom: "var(--space-lg)", fontSize: "0.9rem", fontWeight: 600, color: "var(--text-secondary)" }}>
              Price Comparison
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-lg)" }}>
              <div style={{ textAlign: "center", padding: "var(--space-lg)", background: "var(--bg-glass)", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "var(--space-xs)" }}>CURRENT PRICE</div>
                <div style={{ fontSize: "2rem", fontWeight: 800, color: "var(--text-secondary)" }}>₹{result.current_price}</div>
              </div>
              <div style={{ textAlign: "center", padding: "var(--space-lg)", background: "rgba(99,102,241,0.1)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-accent)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--primary-light)", marginBottom: "var(--space-xs)" }}>OPTIMAL PRICE</div>
                <div style={{ fontSize: "2rem", fontWeight: 800, color: "var(--primary-light)" }}>₹{result.optimal_price}</div>
              </div>
            </div>
          </div>

          {/* Metrics */}
          <div className="card animate-in stagger-1">
            <h3 style={{ marginBottom: "var(--space-lg)", fontSize: "0.9rem", fontWeight: 600, color: "var(--text-secondary)" }}>
              Expected Outcomes
            </h3>
            <div className="alert-list">
              <div className="alert-item ok">
                <span style={{ fontSize: "1.5rem" }}>📈</span>
                <div>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>Expected Demand</div>
                  <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>{result.expected_demand} units/day</div>
                </div>
              </div>
              <div className="alert-item ok">
                <span style={{ fontSize: "1.5rem" }}>💰</span>
                <div>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>Expected Profit</div>
                  <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>₹{result.expected_profit.toFixed(2)}</div>
                </div>
              </div>
              <div className={`alert-item ${result.profit_uplift_pct > 0 ? "ok" : "warning"}`}>
                <span style={{ fontSize: "1.5rem" }}>{result.profit_uplift_pct > 0 ? "🚀" : "⚠️"}</span>
                <div>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>Profit Uplift</div>
                  <div style={{ color: result.profit_uplift_pct > 0 ? "var(--success)" : "var(--warning)", fontSize: "0.85rem" }}>
                    {result.profit_uplift_pct > 0 ? "+" : ""}{result.profit_uplift_pct}%
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bar chart */}
          <div className="chart-card animate-in stagger-2">
            <h3>Value Comparison</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={comparisonData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" tick={{ fill: "#6b6b80", fontSize: 11 }} />
                <YAxis type="category" dataKey="label" tick={{ fill: "#a1a1b5", fontSize: 12 }} width={120} />
                <Tooltip
                  contentStyle={{
                    background: "#1a1a24",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: 8,
                    color: "#f1f1f7",
                  }}
                />
                <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                  {comparisonData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
