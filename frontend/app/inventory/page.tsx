"use client";

import { useState, useEffect } from "react";
import { getInventoryList, runFullPipeline } from "../../lib/api";

export default function InventoryPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [optimizing, setOptimizing] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    fetchInventory();
  }, []);

  const fetchInventory = async () => {
    try {
      const data = await getInventoryList();
      // Only keep items that are real stockouts or critical (0 or near 0) for the Critical Actions component
      setAlerts(data.filter((item: any) => item.stock_on_hand <= item.reorder_point || item.stock_on_hand <= 10));
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handlePredictPipeline = async (productId: number, storeId: number) => {
    setOptimizing(`${productId}-${storeId}`);
    try {
      const today = new Date();
      const nextWeek = new Date();
      nextWeek.setDate(today.getDate() + 7); // 7-day lookahead as requested!

      const data = await runFullPipeline({
        product_id: productId,
        store_id: storeId,
        start_date: today.toISOString().split("T")[0],
        end_date: nextWeek.toISOString().split("T")[0],
      });
      setResult(data);
    } catch (e) {
      console.error(e);
    } finally {
      setOptimizing(null);
    }
  };

  const getStockStatus = (stock: number, reorder: number) => {
    if (stock <= 0) return { label: "STOCKOUT", class: "badge-danger" };
    if (stock <= reorder * 0.5) return { label: "CRITICAL", class: "badge-danger" };
    if (stock <= reorder) return { label: "RUNNING LOW", class: "badge-warning" };
    return { label: "OK", class: "badge-success" };
  };

  if (loading) return <div className="loading-spinner"><div className="spinner" /></div>;

  return (
    <div>
      <div className="page-header animate-in">
        <h2>Critical Stock Action Center</h2>
        <p>Run immediate AI Full-Pipeline predictions (Demand + Price + Reorder) on depleted stock.</p>
      </div>

      {/* Summary KPIs */}
      <div className="kpi-grid" style={{ marginBottom: "var(--space-xl)" }}>
        <div className="kpi-card animate-in" style={{ "--kpi-color": "#ef4444" } as React.CSSProperties}>
          <div className="kpi-icon">🚨</div>
          <div className="kpi-label">Hard Stockouts</div>
          <div className="kpi-value">{alerts.filter((a) => a.stock_on_hand <= 0).length}</div>
        </div>
        <div className="kpi-card animate-in stagger-1" style={{ "--kpi-color": "#f59e0b" } as React.CSSProperties}>
          <div className="kpi-icon">⚠️</div>
          <div className="kpi-label">Critical Warning</div>
          <div className="kpi-value">{alerts.filter((a) => a.stock_on_hand > 0 && a.stock_on_hand <= a.reorder_point).length}</div>
        </div>
      </div>

      {/* AI Pipeline Result Dashboard */}
      {result && (
        <div className="card animate-in" style={{ marginBottom: "var(--space-xl)", border: "1px solid var(--primary-color)" }}>
          <h3 style={{ marginBottom: "var(--space-md)", color: "var(--primary-light)" }}>
            🧠 AI Pipeline Action Plan — Product {result.product_id}, Store {result.store_id}
          </h3>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
            Predictions generated bridging XGBoost Demand &rarr; LightGBM Pricing &rarr; XGBoost Inventory.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-md)" }}>
            {[
              { label: "Optimal Pricing", value: `₹${result.price.optimal_price}`, unit: "per unit" },
              { label: "7-Day Restock Order Qty", value: result.inventory.order_qty, unit: "units (EOQ)" },
              { label: "Predicted 7-Day Demand", value: result.demand.total_predicted, unit: "total units" },
              { label: "New Expected Profit", value: `₹${result.total_expected_profit}`, unit: "7-day outlook" },
              { label: "Reorder Point", value: result.inventory.reorder_point, unit: "units" },
              { label: "Safety Stock", value: result.inventory.safety_stock, unit: "units" },
            ].map((item) => (
              <div key={item.label} style={{ padding: "var(--space-md)", background: "var(--bg-glass)", borderRadius: "var(--radius-md)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontSize: "1.35rem", fontWeight: 700 }}>{item.value}</div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 2 }}>{item.unit}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Depleted Items Action Table */}
      <div className="card animate-in" style={{ overflow: "auto" }}>
        <h3>At-Risk Merchandise</h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>Product ID</th>
              <th>Store ID</th>
              <th>Remaining Stock</th>
              <th>System Reorder Pt</th>
              <th>Urgency</th>
              <th>ML Actions</th>
            </tr>
          </thead>
          <tbody>
            {alerts.length === 0 ? (
               <tr><td colSpan={6} style={{textAlign: "center"}}>All stock systems nominal!</td></tr>
            ) : alerts.map((a) => {
              const status = getStockStatus(a.stock_on_hand, a.reorder_point);
              return (
                <tr key={`${a.product_id}-${a.store_id}`}>
                  <td style={{ fontWeight: 500, color: "var(--text-primary)" }}>Prod: {a.product_id}</td>
                  <td>Store: {a.store_id}</td>
                  <td style={{ fontWeight: 600, color: a.stock_on_hand <= 0 ? "var(--danger)" : "var(--warning)" }}>
                    {a.stock_on_hand}
                  </td>
                  <td>{a.reorder_point}</td>
                  <td><span className={`badge ${status.class}`}>{status.label}</span></td>
                  <td>
                    <button
                      className="btn btn-primary"
                      style={{ fontSize: "0.75rem", padding: "6px 12px", background: "var(--primary-color)" }}
                      onClick={() => handlePredictPipeline(a.product_id, a.store_id)}
                      disabled={optimizing === `${a.product_id}-${a.store_id}`}
                    >
                      {optimizing === `${a.product_id}-${a.store_id}` ? "Predicting..." : "Analyze & Predict"}
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
