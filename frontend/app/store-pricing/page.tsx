"use client";

import { useState } from "react";
import { optimizeStorePrice } from "../../lib/api";

type OptimizationItem = {
  product_id: number;
  product_name: string;
  current_price: number;
  optimal_price: number;
  expected_7d_demand: number;
  expected_7d_profit: number;
  profit_uplift_pct: number;
};

export default function StorePricingPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState<OptimizationItem[]>([]);
  const [totalProfit, setTotalProfit] = useState<number | null>(null);

  const handleOptimize = async () => {
    setLoading(true);
    setError("");
    setResults([]);
    try {
      // Hardcoded store 1 for demo purposes
      const res = await optimizeStorePrice(1);
      setResults(res.optimizations);
      setTotalProfit(res.total_expected_profit);
    } catch (err: any) {
      setError(err.message || "Failed to run store optimization.");
    } finally {
      setLoading(false);
    }
  };

  const getTrend = (item: OptimizationItem) => {
    const isIncrease = item.optimal_price > item.current_price;
    const isDecrease = item.optimal_price < item.current_price;
    const difference = Math.abs(item.optimal_price - item.current_price);

    if (isIncrease) {
      return { label: `↑ $${difference.toFixed(2)}`, className: "badge badge-success" };
    }

    if (isDecrease) {
      return { label: `↓ $${difference.toFixed(2)}`, className: "badge badge-danger" };
    }

    return { label: "—", className: "badge badge-info" };
  };

  const increasedCount = results.filter((item) => item.optimal_price > item.current_price).length;
  const decreasedCount = results.filter((item) => item.optimal_price < item.current_price).length;

  return (
    <div>
      <div className="page-header animate-in" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h2>Store-Wide Price Optimization</h2>
          <p>Generate 7-day optimal pricing directives for the active store inventory.</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleOptimize}
          disabled={loading}
          style={{ fontSize: "0.85rem", padding: "10px 20px" }}
        >
          {loading ? (
            <>
              <span className="spinner" /> Processing Store...
            </>
          ) : (
            "🏷️ Optimize Store (7 Days)"
          )}
        </button>
      </div>

      <div className="kpi-grid" style={{ marginBottom: "var(--space-xl)" }}>
        <div className="kpi-card animate-in" style={{ "--kpi-color": "#3b82f6" } as React.CSSProperties}>
          <div className="kpi-icon">🏷️</div>
          <div className="kpi-label">Products Optimized</div>
          <div className="kpi-value">{results.length}</div>
        </div>
        <div className="kpi-card animate-in stagger-1" style={{ "--kpi-color": "#10b981" } as React.CSSProperties}>
          <div className="kpi-icon">📈</div>
          <div className="kpi-label">Price Increases</div>
          <div className="kpi-value">{increasedCount}</div>
        </div>
        <div className="kpi-card animate-in stagger-2" style={{ "--kpi-color": "#ef4444" } as React.CSSProperties}>
          <div className="kpi-icon">📉</div>
          <div className="kpi-label">Price Decreases</div>
          <div className="kpi-value">{decreasedCount}</div>
        </div>
      </div>

      {error && (
        <div className="card animate-in" style={{ borderLeft: "4px solid var(--danger)", color: "var(--danger)" }}>
          <strong>Error: </strong> {error}
        </div>
      )}

      {totalProfit !== null && !loading && (
        <div className="card animate-in" style={{ marginBottom: "var(--space-xl)", border: "1px solid var(--border-accent)" }}>
          <h3>Optimization Complete</h3>
          <p style={{ marginTop: "0.5rem", color: "var(--text-muted)" }}>
            Total 7-Day Expected Store Profit: <span style={{ color: "var(--success)", fontWeight: "bold", fontSize: "1.2rem" }}>${totalProfit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
          </p>
        </div>
      )}

      {results.length > 0 && !loading && (
        <div className="card animate-in" style={{ overflow: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", marginBottom: "var(--space-md)", flexWrap: "wrap" }}>
            <h3 style={{ color: "var(--primary-light)" }}>New Weekly Price Directives</h3>
            <button className="btn btn-secondary" onClick={() => alert("Connecting to label printer...")} style={{ fontSize: "0.7rem", padding: "4px 10px" }}>
              🖨️ Print Price Tags
            </button>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Current Price</th>
                <th>Optimal Price</th>
                <th>Trend</th>
                <th>7-Day Demand</th>
                <th>7-Day Profit</th>
                <th>Profit Uplift</th>
              </tr>
            </thead>
            <tbody>
              {results.map((opt) => {
                const trend = getTrend(opt);

                return (
                  <tr key={opt.product_id}>
                    <td style={{ fontWeight: 500, color: "var(--text-primary)" }}>
                      {opt.product_name}
                      <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>ID: {opt.product_id}</div>
                    </td>
                    <td>${opt.current_price.toFixed(2)}</td>
                    <td style={{ fontWeight: 600, color: "var(--primary-light)" }}>${opt.optimal_price.toFixed(2)}</td>
                    <td><span className={trend.className}>{trend.label}</span></td>
                    <td>{opt.expected_7d_demand.toFixed(1)} units</td>
                    <td style={{ fontWeight: 600, color: "var(--success)" }}>${opt.expected_7d_profit.toFixed(2)}</td>
                    <td style={{ color: opt.profit_uplift_pct > 0 ? "var(--success)" : "var(--text-muted)" }}>
                      {opt.profit_uplift_pct > 0 ? `+${opt.profit_uplift_pct.toFixed(1)}%` : "-"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !results.length && !error && (
        <div className="card animate-in" style={{ textAlign: "center", padding: "4rem 2rem", opacity: 0.75 }}>
          <span style={{ fontSize: "3rem", display: "block", marginBottom: "1rem" }}>🏷️</span>
          <h3 style={{ marginBottom: "var(--space-sm)" }}>Ready to Optimize</h3>
          <p style={{ color: "var(--text-secondary)" }}>Click the Optimize button to calculate new shelf prices for the entire store.</p>
        </div>
      )}
    </div>
  );
}
