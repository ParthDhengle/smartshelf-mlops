"use client";

import { useState } from "react";
import { simulateSale } from "../../lib/api";

export default function SimulatorPage() {
  const [form, setForm] = useState<any>({
    product_id: 1,
    store_id: 1,
    quantity: 5,
    unit_price: 120,
    discount_pct: 0,
  });
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const payload = {
      product_id: Number(form.product_id),
      store_id: Number(form.store_id),
      quantity: Number(form.quantity),
      unit_price: parseFloat(form.unit_price),
      discount_pct: parseFloat(form.discount_pct),
    };

    try {
      const data = await simulateSale(payload);
      setResult(data);
      setHistory((prev) => [{ ...payload, ...data, timestamp: new Date().toLocaleTimeString() }, ...prev].slice(0, 20));
    } catch (e) {
      setError(e.message);
      const mock = {
        status: "ok (mock)",
        order_id: 99000 + history.length,
        line_total: Math.round(payload.quantity * payload.unit_price * (1 - payload.discount_pct / 100) * 100) / 100,
      };
      setResult(mock);
      setHistory((prev) => [{ ...payload, ...mock, timestamp: new Date().toLocaleTimeString() }, ...prev].slice(0, 20));
    } finally {
      setLoading(false);
    }
  };

  const update = (field, value) => setForm((prev) => ({ ...prev, [field]: value }));

  return (
    <div>
      <div className="page-header animate-in">
        <h2>Sales Simulator</h2>
        <p>Inject test sales data into the system to observe predictions</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-xl)" }}>
        {/* Form */}
        <div className="card animate-in">
          <h3 style={{ marginBottom: "var(--space-lg)", fontSize: "0.9rem", fontWeight: 600, color: "var(--text-secondary)" }}>
            🎮 Simulate a Sale
          </h3>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Product ID</label>
              <input className="form-input" type="number" value={form.product_id} onChange={(e) => update("product_id", e.target.value)} min="1" required />
            </div>
            <div className="form-group">
              <label className="form-label">Store ID</label>
              <input className="form-input" type="number" value={form.store_id} onChange={(e) => update("store_id", e.target.value)} min="1" required />
            </div>
            <div className="form-group">
              <label className="form-label">Quantity</label>
              <input className="form-input" type="number" value={form.quantity} onChange={(e) => update("quantity", e.target.value)} min="1" required />
            </div>
            <div className="form-group">
              <label className="form-label">Unit Price (₹)</label>
              <input className="form-input" type="number" step="0.01" value={form.unit_price} onChange={(e) => update("unit_price", e.target.value)} min="0.01" required />
            </div>
            <div className="form-group">
              <label className="form-label">Discount (%)</label>
              <input className="form-input" type="number" step="0.1" value={form.discount_pct} onChange={(e) => update("discount_pct", e.target.value)} min="0" max="100" />
            </div>

            {/* Live Preview */}
            <div style={{ padding: "var(--space-md)", background: "var(--bg-glass)", borderRadius: "var(--radius-md)", marginBottom: "var(--space-md)" }}>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 4 }}>LINE TOTAL PREVIEW</div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--primary-light)" }}>
                ₹{(form.quantity * form.unit_price * (1 - form.discount_pct / 100)).toFixed(2)}
              </div>
            </div>

            <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: "100%" }}>
              {loading ? "Submitting..." : "🚀 Submit Sale"}
            </button>
            {error && <p style={{ color: "var(--warning)", fontSize: "0.8rem", marginTop: "var(--space-sm)" }}>⚠️ Using mock mode</p>}
          </form>

          {result && (
            <div style={{ marginTop: "var(--space-md)", padding: "var(--space-md)", background: "rgba(16,185,129,0.08)", borderRadius: "var(--radius-md)", border: "1px solid rgba(16,185,129,0.2)" }}>
              <div style={{ fontSize: "0.8rem", color: "var(--success)", fontWeight: 600 }}>
                ✅ Sale recorded — Order #{result.order_id} (₹{result.line_total})
              </div>
            </div>
          )}
        </div>

        {/* History */}
        <div className="card animate-in stagger-1">
          <h3 style={{ marginBottom: "var(--space-lg)", fontSize: "0.9rem", fontWeight: 600, color: "var(--text-secondary)" }}>
            📜 Recent Simulations
          </h3>
          {history.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🎯</div>
              <p>No simulations yet. Submit a sale to see history.</p>
            </div>
          ) : (
            <div className="alert-list">
              {history.map((h, i) => (
                <div key={i} className="alert-item ok">
                  <span style={{ fontSize: "1.2rem" }}>🧾</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "0.85rem" }}>
                        Order #{h.order_id}
                      </span>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{h.timestamp}</span>
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                      Product {h.product_id} × {h.quantity} @ ₹{h.unit_price} = ₹{h.line_total}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
