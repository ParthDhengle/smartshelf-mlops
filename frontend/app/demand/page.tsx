"use client";

import { useState } from "react";
import { predictDemand } from "../../lib/api";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

export default function DemandPage() {
  const [productId, setProductId] = useState<number | string>(1);
  const [storeId, setStoreId] = useState<number | string>(1);
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("2025-01-14");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handlePredict = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await predictDemand({
        product_id: Number(productId),
        store_id: Number(storeId),
        start_date: startDate,
        end_date: endDate,
      });
      setResult(data);
    } catch (e) {
      setError(e.message);
      // Mock fallback
      const days = Math.ceil((new Date(endDate).getTime() - new Date(startDate).getTime()) / 86400000) + 1;
      const forecasts = Array.from({ length: days }, (_, i) => {
        const d = new Date(startDate);
        d.setDate(d.getDate() + i);
        const base = 15 + Math.random() * 10;
        return {
          date: d.toISOString().split("T")[0],
          predicted_demand: Math.round(base * 10) / 10,
          confidence_lower: Math.round(base * 0.8 * 10) / 10,
          confidence_upper: Math.round(base * 1.2 * 10) / 10,
        };
      });
      setResult({
        product_id: Number(productId),
        store_id: Number(storeId),
        forecasts,
        total_predicted: forecasts.reduce((s, f) => s + f.predicted_demand, 0),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header animate-in">
        <h2>Demand Forecast</h2>
        <p>Predict daily demand for any product-store combination</p>
      </div>

      {/* Input Form */}
      <div className="card animate-in" style={{ marginBottom: "var(--space-xl)" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-md)", alignItems: "flex-end" }}>
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
          <button className="btn btn-primary" onClick={handlePredict} disabled={loading} style={{ marginBottom: "var(--space-md)" }}>
            {loading ? "Predicting..." : "🔮 Predict Demand"}
          </button>
        </div>
        {error && <p style={{ color: "var(--warning)", fontSize: "0.8rem", marginTop: "var(--space-sm)" }}>⚠️ Using mock data: {error}</p>}
      </div>

      {/* Results */}
      {result && (
        <>
          {/* Summary KPIs */}
          <div className="kpi-grid" style={{ marginBottom: "var(--space-xl)" }}>
            <div className="kpi-card animate-in" style={{ "--kpi-color": "#6366f1" } as React.CSSProperties}>
              <div className="kpi-label">Total Predicted</div>
              <div className="kpi-value">{result.total_predicted.toFixed(0)}</div>
              <div className="kpi-change positive">units over {result.forecasts.length} days</div>
            </div>
            <div className="kpi-card animate-in stagger-1" style={{ "--kpi-color": "#22d3ee" } as React.CSSProperties}>
              <div className="kpi-label">Avg Daily</div>
              <div className="kpi-value">{(result.total_predicted / result.forecasts.length).toFixed(1)}</div>
            </div>
            <div className="kpi-card animate-in stagger-2" style={{ "--kpi-color": "#10b981" } as React.CSSProperties}>
              <div className="kpi-label">Peak Day</div>
              <div className="kpi-value">{Math.max(...result.forecasts.map((f) => f.predicted_demand)).toFixed(1)}</div>
            </div>
          </div>

          {/* Chart */}
          <div className="chart-card animate-in">
            <h3>Demand Forecast — Product {result.product_id}, Store {result.store_id}</h3>
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={result.forecasts}>
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
                <ReferenceLine
                  y={result.total_predicted / result.forecasts.length}
                  stroke="#f59e0b"
                  strokeDasharray="5 5"
                  label={{ value: "Avg", fill: "#f59e0b", fontSize: 11 }}
                />
                <Line type="monotone" dataKey="confidence_upper" stroke="transparent" fill="rgba(99,102,241,0.1)" />
                <Line type="monotone" dataKey="confidence_lower" stroke="transparent" fill="rgba(99,102,241,0.1)" />
                <Line type="monotone" dataKey="predicted_demand" stroke="#6366f1" strokeWidth={2.5} dot={{ fill: "#6366f1", r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
