"use client";

import { useState } from "react";
import { predictDemand, optimizePrice } from "../../lib/api";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, BarChart, Bar, Cell,
} from "recharts";

export default function PredictionsPage() {
  const [productId, setProductId] = useState<number | string>(1);
  const [storeId, setStoreId] = useState<number | string>(1);
  const [startDate, setStartDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [endDate, setEndDate] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() + 7);
    return d.toISOString().split("T")[0];
  });
  const [demandResult, setDemandResult] = useState<any>(null);
  const [priceResult, setPriceResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleRunAll = async () => {
    setLoading(true);
    setError("");
    setDemandResult(null);
    setPriceResult(null);
    try {
      const [demand, price] = await Promise.all([
        predictDemand({
          product_id: Number(productId),
          store_id: Number(storeId),
          start_date: startDate,
          end_date: endDate,
        }),
        optimizePrice({
          product_id: Number(productId),
          store_id: Number(storeId),
        }),
      ]);
      setDemandResult(demand);
      setPriceResult(price);
    } catch (e: any) {
      setError(e.message || "Prediction failed — ensure models are trained and registered in MLflow.");
    } finally {
      setLoading(false);
    }
  };

  const comparisonData = priceResult
    ? [
        { label: "Current Price", value: priceResult.current_price, fill: "#6b6b80" },
        { label: "Optimal Price", value: priceResult.optimal_price, fill: "#6366f1" },
        { label: "Expected Profit", value: priceResult.expected_profit, fill: "#10b981" },
      ]
    : [];

  return (
    <div>
      <div className="page-header animate-in">
        <h2>ML Predictions Lab</h2>
        <p>Run Demand Forecasting (XGBoost) and Price Optimization (LightGBM) for any product-store pair</p>
      </div>

      {/* Input Form */}
      <div className="card animate-in" style={{ marginBottom: "var(--space-xl)" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "var(--space-md)", alignItems: "flex-end" }}>
          <div className="form-group">
            <label className="form-label">Product ID</label>
            <input className="form-input" type="number" value={productId} onChange={(e) => setProductId(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Store ID</label>
            <input className="form-input" type="number" value={storeId} onChange={(e) => setStoreId(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Start Date</label>
            <input className="form-input" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">End Date</label>
            <input className="form-input" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>
          <button className="btn btn-primary" onClick={handleRunAll} disabled={loading} style={{ marginBottom: "var(--space-md)" }}>
            {loading ? "Running Models..." : "🧠 Run Predictions"}
          </button>
        </div>
        {error && <p style={{ color: "var(--danger)", fontSize: "0.85rem", marginTop: "var(--space-sm)" }}>❌ {error}</p>}
      </div>

      {/* Results */}
      {(demandResult || priceResult) && (
        <>
          {/* Summary KPIs row */}
          <div className="kpi-grid" style={{ marginBottom: "var(--space-xl)" }}>
            {demandResult && (
              <>
                <div className="kpi-card animate-in" style={{ "--kpi-color": "#6366f1" } as React.CSSProperties}>
                  <div className="kpi-label">Total Predicted Demand</div>
                  <div className="kpi-value">{demandResult.total_predicted.toFixed(0)}</div>
                  <div className="kpi-change positive">units over {demandResult.forecasts.length} days</div>
                </div>
                <div className="kpi-card animate-in stagger-1" style={{ "--kpi-color": "#22d3ee" } as React.CSSProperties}>
                  <div className="kpi-label">Avg Daily Demand</div>
                  <div className="kpi-value">{(demandResult.total_predicted / demandResult.forecasts.length).toFixed(1)}</div>
                </div>
              </>
            )}
            {priceResult && (
              <>
                <div className="kpi-card animate-in stagger-2" style={{ "--kpi-color": "#10b981" } as React.CSSProperties}>
                  <div className="kpi-label">Optimal Price</div>
                  <div className="kpi-value">₹{priceResult.optimal_price}</div>
                </div>
                <div className="kpi-card animate-in stagger-3" style={{ "--kpi-color": priceResult.profit_uplift_pct > 0 ? "#10b981" : "#f59e0b" } as React.CSSProperties}>
                  <div className="kpi-label">Profit Uplift</div>
                  <div className="kpi-value">{priceResult.profit_uplift_pct > 0 ? "+" : ""}{priceResult.profit_uplift_pct}%</div>
                </div>
              </>
            )}
          </div>

          <div className="chart-grid">
            {/* Demand Forecast Chart */}
            {demandResult && (
              <div className="chart-card animate-in">
                <h3>Demand Forecast — Product {demandResult.product_id}, Store {demandResult.store_id}</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={demandResult.forecasts}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="date" tick={{ fill: "#6b6b80", fontSize: 11 }} />
                    <YAxis tick={{ fill: "#6b6b80", fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: "#1a1a24", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, color: "#f1f1f7" }} />
                    <ReferenceLine
                      y={demandResult.total_predicted / demandResult.forecasts.length}
                      stroke="#f59e0b" strokeDasharray="5 5"
                      label={{ value: "Avg", fill: "#f59e0b", fontSize: 11 }}
                    />
                    <Line type="monotone" dataKey="predicted_demand" stroke="#6366f1" strokeWidth={2.5} dot={{ fill: "#6366f1", r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Price Optimization Results */}
            {priceResult && (
              <div className="card animate-in stagger-1">
                <h3 style={{ marginBottom: "var(--space-lg)", fontSize: "0.9rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                  Price Optimization
                </h3>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-lg)", marginBottom: "var(--space-lg)" }}>
                  <div style={{ textAlign: "center", padding: "var(--space-lg)", background: "var(--bg-glass)", borderRadius: "var(--radius-md)" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "var(--space-xs)" }}>CURRENT PRICE</div>
                    <div style={{ fontSize: "2rem", fontWeight: 800, color: "var(--text-secondary)" }}>₹{priceResult.current_price}</div>
                  </div>
                  <div style={{ textAlign: "center", padding: "var(--space-lg)", background: "rgba(99,102,241,0.1)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-accent)" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--primary-light)", marginBottom: "var(--space-xs)" }}>OPTIMAL PRICE</div>
                    <div style={{ fontSize: "2rem", fontWeight: 800, color: "var(--primary-light)" }}>₹{priceResult.optimal_price}</div>
                  </div>
                </div>
                <div className="alert-list">
                  <div className="alert-item ok">
                    <span style={{ fontSize: "1.5rem" }}>📈</span>
                    <div>
                      <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>Expected Demand</div>
                      <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>{priceResult.expected_demand} units/day</div>
                    </div>
                  </div>
                  <div className="alert-item ok">
                    <span style={{ fontSize: "1.5rem" }}>💰</span>
                    <div>
                      <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>Expected Profit</div>
                      <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>₹{priceResult.expected_profit.toFixed(2)}</div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
