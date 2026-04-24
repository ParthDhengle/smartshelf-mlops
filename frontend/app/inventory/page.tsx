"use client";

import { useState, useEffect } from "react";
import { getStores, getInventoryList, runFullPipeline } from "../../lib/api";

type PredictionResult = {
  product_id: number;
  store_id: number;
  demand: { total_predicted: number };
  price: { optimal_price: number; current_price: number };
  inventory: { reorder_point: number; safety_stock: number; order_qty: number };
  total_expected_profit: number;
};

type Store = {
  store_id: number;
  store_name: string;
  city: string;
  state: string;
  store_type: string;
  store_size_sqft: number;
};

export default function InventoryPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [selectedStore, setSelectedStore] = useState<Store | null>(null);
  const [allItems, setAllItems] = useState<any[]>([]);
  const [loadingStores, setLoadingStores] = useState(true);
  const [loadingItems, setLoadingItems] = useState(false);
  const [optimizing, setOptimizing] = useState<string | null>(null);
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ done: 0, total: 0 });
  const [predictions, setPredictions] = useState<Record<string, PredictionResult>>({});
  const [selectedResult, setSelectedResult] = useState<PredictionResult | null>(null);
  const [viewMode, setViewMode] = useState<"all" | "critical">("all");

  useEffect(() => {
    fetchStores();
  }, []);

  const fetchStores = async () => {
    try {
      const data = await getStores();
      setStores(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingStores(false);
    }
  };

  const openStore = async (store: Store) => {
    setSelectedStore(store);
    setLoadingItems(true);
    setPredictions({});
    setSelectedResult(null);
    setViewMode("all");
    try {
      const data = await getInventoryList(store.store_id);
      setAllItems(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingItems(false);
    }
  };

  const goBack = () => {
    setSelectedStore(null);
    setAllItems([]);
    setPredictions({});
    setSelectedResult(null);
    setBatchRunning(false);
  };

  const criticalItems = allItems.filter(
    (item: any) => item.stock_on_hand <= item.reorder_point || item.stock_on_hand <= 10
  );
  const displayItems = viewMode === "critical" ? criticalItems : allItems;

  const handlePredictSingle = async (productId: number, storeId: number) => {
    const key = `${productId}-${storeId}`;
    setOptimizing(key);
    try {
      const today = new Date();
      const nextWeek = new Date();
      nextWeek.setDate(today.getDate() + 7);
      const data = await runFullPipeline({
        product_id: productId, store_id: storeId,
        start_date: today.toISOString().split("T")[0],
        end_date: nextWeek.toISOString().split("T")[0],
      });
      setPredictions((prev) => ({ ...prev, [key]: data }));
      setSelectedResult(data);
    } catch (e) { console.error(e); }
    finally { setOptimizing(null); }
  };

  const handlePredictAll = async () => {
    setBatchRunning(true);
    const items = displayItems;
    setBatchProgress({ done: 0, total: items.length });
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      const key = `${item.product_id}-${item.store_id}`;
      try {
        const today = new Date();
        const nextWeek = new Date();
        nextWeek.setDate(today.getDate() + 7);
        const data = await runFullPipeline({
          product_id: item.product_id, store_id: item.store_id,
          start_date: today.toISOString().split("T")[0],
          end_date: nextWeek.toISOString().split("T")[0],
        });
        setPredictions((prev) => ({ ...prev, [key]: data }));
      } catch (e) { console.error(e); }
      setBatchProgress({ done: i + 1, total: items.length });
    }
    setBatchRunning(false);
  };

  const getStockStatus = (stock: number, reorder: number) => {
    if (stock <= 0) return { label: "STOCKOUT", class: "badge-danger" };
    if (stock <= reorder * 0.5) return { label: "CRITICAL", class: "badge-danger" };
    if (stock <= reorder) return { label: "LOW", class: "badge-warning" };
    return { label: "OK", class: "badge-success" };
  };

  const predictedCount = Object.keys(predictions).length;

  // ──────────── STORE SELECTOR VIEW ────────────
  if (!selectedStore) {
    if (loadingStores) return <div className="loading-spinner"><div className="spinner" /></div>;

    return (
      <div>
        <div className="page-header animate-in">
          <h2>Inventory Intelligence Center</h2>
          <p>Select a store to view inventory, run demand forecasts, and optimize pricing for all products.</p>
        </div>

        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: "var(--space-lg)",
        }}>
          {stores.map((store, idx) => {
            const staggerClass = idx < 6 ? `stagger-${idx % 4}` : "";
            return (
              <div
                key={store.store_id}
                className={`card animate-in ${staggerClass}`}
                onClick={() => openStore(store)}
                style={{
                  cursor: "pointer",
                  transition: "transform 0.2s ease, box-shadow 0.2s ease",
                  border: "1px solid var(--border-subtle)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-4px)";
                  e.currentTarget.style.boxShadow = "0 8px 25px rgba(0,0,0,0.15)";
                  e.currentTarget.style.borderColor = "var(--primary-color)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.boxShadow = "none";
                  e.currentTarget.style.borderColor = "var(--border-subtle)";
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>🏪</div>
                    <h3 style={{ fontSize: "1rem", marginBottom: "0.25rem" }}>{store.store_name}</h3>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{store.city}, {store.state}</p>
                  </div>
                  <span className="badge badge-info" style={{ fontSize: "0.7rem" }}>Store #{store.store_id}</span>
                </div>
                <div style={{ marginTop: "1rem", display: "flex", gap: "1rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  <span>📐 {store.store_size_sqft?.toLocaleString()} sqft</span>
                  <span>🏷️ {store.store_type}</span>
                </div>
                <div style={{ marginTop: "0.75rem", fontSize: "0.8rem", color: "var(--primary-light)", fontWeight: 500 }}>
                  Click to manage inventory →
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // ──────────── STORE DETAIL VIEW ────────────
  if (loadingItems) return <div className="loading-spinner"><div className="spinner" /></div>;

  return (
    <div>
      {/* Header with back button */}
      <div className="page-header animate-in" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <button className="btn btn-secondary" onClick={goBack} style={{ fontSize: "0.8rem", padding: "6px 12px" }}>
            ← Back
          </button>
          <div>
            <h2>🏪 {selectedStore.store_name}</h2>
            <p>{selectedStore.city} — {allItems.length} products | {selectedStore.store_type} | {selectedStore.store_size_sqft?.toLocaleString()} sqft</p>
          </div>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button className={`btn ${viewMode === "all" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setViewMode("all")} style={{ fontSize: "0.8rem", padding: "8px 14px" }}>
            📦 All ({allItems.length})
          </button>
          <button className={`btn ${viewMode === "critical" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setViewMode("critical")} style={{ fontSize: "0.8rem", padding: "8px 14px" }}>
            🚨 Critical ({criticalItems.length})
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="kpi-grid" style={{ marginBottom: "var(--space-xl)" }}>
        <div className="kpi-card animate-in" style={{ "--kpi-color": "#3b82f6" } as React.CSSProperties}>
          <div className="kpi-icon">📦</div>
          <div className="kpi-label">Total Products</div>
          <div className="kpi-value">{allItems.length}</div>
        </div>
        <div className="kpi-card animate-in stagger-1" style={{ "--kpi-color": "#ef4444" } as React.CSSProperties}>
          <div className="kpi-icon">🚨</div>
          <div className="kpi-label">Critical / Low</div>
          <div className="kpi-value">{criticalItems.length}</div>
        </div>
        <div className="kpi-card animate-in stagger-2" style={{ "--kpi-color": "#f59e0b" } as React.CSSProperties}>
          <div className="kpi-icon">⛔</div>
          <div className="kpi-label">Stockouts</div>
          <div className="kpi-value">{allItems.filter((a) => a.stock_on_hand <= 0).length}</div>
        </div>
        <div className="kpi-card animate-in stagger-3" style={{ "--kpi-color": "#10b981" } as React.CSSProperties}>
          <div className="kpi-icon">🧠</div>
          <div className="kpi-label">Predictions</div>
          <div className="kpi-value">{predictedCount}/{displayItems.length}</div>
        </div>
      </div>

      {/* Batch Predict */}
      <div className="card animate-in" style={{ marginBottom: "var(--space-xl)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h3 style={{ marginBottom: "0.25rem" }}>🧠 Weekly AI Prediction Engine</h3>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            7-Day Pipeline: Demand (XGBoost) → Price (LightGBM) → Inventory (XGBoost) for {displayItems.length} products
          </p>
        </div>
        <button className="btn btn-primary" onClick={handlePredictAll} disabled={batchRunning}
          style={{ fontSize: "0.85rem", padding: "10px 20px", minWidth: "200px" }}>
          {batchRunning
            ? <><span className="spinner" /> {batchProgress.done}/{batchProgress.total}</>
            : `Predict All (7 Days)`}
        </button>
      </div>

      {batchRunning && (
        <div style={{ marginBottom: "var(--space-lg)", background: "var(--bg-glass)", borderRadius: "var(--radius-md)", overflow: "hidden", height: "8px" }}>
          <div style={{
            height: "100%", width: `${(batchProgress.done / Math.max(batchProgress.total, 1)) * 100}%`,
            background: "var(--primary-color)", transition: "width 0.3s ease", borderRadius: "var(--radius-md)"
          }} />
        </div>
      )}

      {/* Selected Result */}
      {selectedResult && (
        <div className="card animate-in" style={{ marginBottom: "var(--space-xl)", border: "1px solid var(--border-accent)" }}>
          <h3 style={{ marginBottom: "var(--space-md)", color: "var(--primary-light)" }}>
            🧠 AI Result — Product {selectedResult.product_id}
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "var(--space-md)" }}>
            {[
              { label: "7-Day Demand", value: `${selectedResult.demand.total_predicted} units` },
              { label: "Current Price", value: `₹${selectedResult.price.current_price}` },
              { label: "Optimal Price", value: `₹${selectedResult.price.optimal_price}` },
              { label: "Order Qty", value: `${selectedResult.inventory.order_qty} units` },
              { label: "Reorder Point", value: `${selectedResult.inventory.reorder_point}` },
              { label: "Safety Stock", value: `${selectedResult.inventory.safety_stock}` },
            ].map((item) => (
              <div key={item.label} style={{ padding: "var(--space-md)", background: "var(--bg-glass)", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="card animate-in" style={{ overflow: "auto" }}>
        <h3 style={{ marginBottom: "var(--space-md)" }}>
          {viewMode === "critical" ? "🚨 Critical Items" : "📦 Full Inventory"}
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "0.5rem" }}>({displayItems.length})</span>
        </h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Stock</th>
              <th>Status</th>
              <th>Current ₹</th>
              <th>7d Demand</th>
              <th>Optimal ₹</th>
              <th>Order Qty</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {displayItems.length === 0 ? (
              <tr><td colSpan={8} style={{ textAlign: "center" }}>No items.</td></tr>
            ) : displayItems.map((a) => {
              const key = `${a.product_id}-${a.store_id}`;
              const status = getStockStatus(a.stock_on_hand, a.reorder_point);
              const pred = predictions[key];
              return (
                <tr key={key}>
                  <td style={{ fontWeight: 500, color: "var(--text-primary)" }}>
                    {a.product_name}
                    <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>ID: {a.product_id}</div>
                  </td>
                  <td style={{
                    fontWeight: 600,
                    color: a.stock_on_hand <= 0 ? "var(--danger)" : a.stock_on_hand <= a.reorder_point ? "var(--warning)" : "var(--text-primary)"
                  }}>{a.stock_on_hand}</td>
                  <td><span className={`badge ${status.class}`}>{status.label}</span></td>
                  <td>₹{a.base_sell_price ?? "—"}</td>
                  <td style={{ color: pred ? "var(--text-primary)" : "var(--text-muted)", fontWeight: pred ? 600 : 400 }}>
                    {pred ? pred.demand.total_predicted : "—"}
                  </td>
                  <td style={{ fontWeight: pred ? 600 : 400 }}>
                    {pred ? (
                      <span style={{
                        color: pred.price.optimal_price > pred.price.current_price ? "var(--success)"
                          : pred.price.optimal_price < pred.price.current_price ? "var(--danger)" : "var(--text-primary)"
                      }}>₹{pred.price.optimal_price}</span>
                    ) : "—"}
                  </td>
                  <td style={{ color: pred ? "var(--primary-light)" : "var(--text-muted)", fontWeight: pred ? 600 : 400 }}>
                    {pred ? pred.inventory.order_qty : "—"}
                  </td>
                  <td>
                    <button className="btn btn-primary" style={{ fontSize: "0.7rem", padding: "4px 10px" }}
                      onClick={() => handlePredictSingle(a.product_id, a.store_id)}
                      disabled={optimizing === key || batchRunning}>
                      {optimizing === key ? "..." : pred ? "✓" : "Predict"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
