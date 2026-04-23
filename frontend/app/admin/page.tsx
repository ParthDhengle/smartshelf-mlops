"use client";

import { useState, useEffect } from "react";
import { getHealth, clearModelCache, syncWeather, syncEconomic, syncCalendar, getSuppliers } from "../../lib/api";

export default function AdminPage() {
  const [health, setHealth] = useState<any>(null);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState("");
  const [cacheStatus, setCacheStatus] = useState("");
  const [driftReports, setDriftReports] = useState([
    { timestamp: "2025-04-17T14:30:00", drift_score: 0.12, overall_drift: false, drifted_features: [] },
    { timestamp: "2025-04-16T14:30:00", drift_score: 0.35, overall_drift: true, drifted_features: ["selling_price", "temperature_c"] },
    { timestamp: "2025-04-15T14:30:00", drift_score: 0.08, overall_drift: false, drifted_features: [] },
  ]);
  const [models, setModels] = useState([
    { name: "Demand_Model", version: "3", stage: "Production", rmse: 4.23, last_trained: "2025-04-15" },
    { name: "Price_Model", version: "2", stage: "Production", rmse: 6.81, last_trained: "2025-04-15" },
    { name: "Inventory_Model", version: "2", stage: "Staging", rmse: 3.12, last_trained: "2025-04-14" },
  ]);

  const fetchHealth = async () => {
    try {
      const data = await getHealth();
      setHealth(data);
      const supp = await getSuppliers();
      setSuppliers(supp);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const handleClearCache = async () => {
    setCacheStatus("clearing...");
    try {
      await clearModelCache();
      setCacheStatus("✅ Cache cleared — models will reload on next request");
    } catch {
      setCacheStatus("⚠️ Could not clear cache — API may not be running");
    }
  };

  const handleSyncWeather = async () => {
    setActionMsg("Syncing Weather API...");
    try {
      const res = await syncWeather(1);
      setActionMsg(res.message);
    } catch (e: any) { setActionMsg("Error: " + e.message); }
  };

  const handleSyncEconomic = async () => {
    setActionMsg("Syncing Macroeconomic DB...");
    try {
      const res = await syncEconomic();
      setActionMsg(res.message);
    } catch (e: any) { setActionMsg("Error: " + e.message); }
  };
  
  const handleSyncCalendar = async () => {
    setActionMsg("Syncing Holiday Calendar...");
    try {
      const res = await syncCalendar();
      setActionMsg(res.message);
    } catch (e: any) { setActionMsg("Error: " + e.message); }
  };

  if (loading) return <div className="loading-spinner"><div className="spinner" /></div>;

  return (
    <div>
      <div className="page-header animate-in">
        <h2>Admin Panel</h2>
        <p>System health, model management, and drift reports</p>
      </div>

      {/* System Health */}
      <div className="card animate-in" style={{ marginBottom: "var(--space-xl)" }}>
        <h3 style={{ marginBottom: "var(--space-md)", color: "var(--text-secondary)", fontSize: "0.9rem", fontWeight: 600 }}>System Health</h3>
        {health && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-md)" }}>
            <div className={`alert-item ${health.status === "healthy" ? "ok" : "warning"}`}>
              <span style={{ fontSize: "1.5rem" }}>{health.status === "healthy" ? "🟢" : "🟡"}</span>
              <div>
                <div style={{ fontWeight: 600 }}>Status</div>
                <div style={{ fontSize: "0.85rem", textTransform: "uppercase" }}>{health.status}</div>
              </div>
            </div>
            <div className={`alert-item ${health.db_connected ? "ok" : "critical"}`}>
              <span style={{ fontSize: "1.5rem" }}>{health.db_connected ? "✅" : "❌"}</span>
              <div>
                <div style={{ fontWeight: 600 }}>PostgreSQL</div>
                <div style={{ fontSize: "0.85rem" }}>{health.db_connected ? "Connected" : "Disconnected"}</div>
              </div>
            </div>
            <div className={`alert-item ${health.mlflow_connected ? "ok" : "critical"}`}>
              <span style={{ fontSize: "1.5rem" }}>{health.mlflow_connected ? "✅" : "❌"}</span>
              <div>
                <div style={{ fontWeight: 600 }}>MLflow</div>
                <div style={{ fontSize: "0.85rem" }}>{health.mlflow_connected ? "Connected" : "Disconnected"}</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Model Registry */}
      <div className="card animate-in stagger-1" style={{ marginBottom: "var(--space-xl)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-md)" }}>
          <h3 style={{ color: "var(--text-secondary)", fontSize: "0.9rem", fontWeight: 600 }}>Model Registry</h3>
          <div style={{ display: "flex", gap: "var(--space-sm)", alignItems: "center" }}>
            {cacheStatus && <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{cacheStatus}</span>}
            <button className="btn btn-secondary" onClick={handleClearCache}>🔄 Reload Models</button>
          </div>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Version</th>
              <th>Stage</th>
              <th>RMSE</th>
              <th>Last Trained</th>
            </tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.name}>
                <td style={{ fontWeight: 600, color: "var(--text-primary)" }}>{m.name}</td>
                <td>v{m.version}</td>
                <td>
                  <span className={`badge ${m.stage === "Production" ? "badge-success" : "badge-warning"}`}>
                    {m.stage}
                  </span>
                </td>
                <td>{m.rmse}</td>
                <td>{m.last_trained}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Drift Reports */}
      <div className="card animate-in stagger-2">
        <h3 style={{ marginBottom: "var(--space-md)", color: "var(--text-secondary)", fontSize: "0.9rem", fontWeight: 600 }}>
          Drift Detection Reports
        </h3>
        <div className="alert-list">
          {driftReports.map((r, i) => (
            <div key={i} className={`alert-item ${r.overall_drift ? "critical" : "ok"}`}>
              <span style={{ fontSize: "1.5rem" }}>{r.overall_drift ? "⚠️" : "✅"}</span>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                    {r.overall_drift ? "Drift Detected" : "No Drift"}
                  </span>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    {new Date(r.timestamp).toLocaleString()}
                  </span>
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  Score: {r.drift_score.toFixed(2)}
                  {r.drifted_features.length > 0 && ` — Features: ${r.drifted_features.join(", ")}`}
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="card animate-in stagger-2" style={{ flex: 1, minWidth: 300 }}>
          <h3>External Data Synchronization</h3>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
            Pull fresh live data from central public APIs to enhance ML Model features natively.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <button className="btn btn-secondary" style={{ justifyContent: "center" }} onClick={handleSyncWeather}>
              ☁️ Sync OpenWeather API
            </button>
            <button className="btn btn-secondary" style={{ justifyContent: "center" }} onClick={handleSyncEconomic}>
              🏦 Sync World Bank Economic Data
            </button>
            <button className="btn btn-secondary" style={{ justifyContent: "center" }} onClick={handleSyncCalendar}>
              📅 Sync Global Holidays API
            </button>
          </div>
        </div>
      </div>

      <div className="card animate-in stagger-3">
        <h3>Supplier Relationships</h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Supplier Name</th>
              <th>City</th>
              <th>Lead Time</th>
              <th>Reliability</th>
              <th>Delivery Cost</th>
            </tr>
          </thead>
          <tbody>
            {suppliers.map((s) => (
              <tr key={s.supplier_id}>
                <td>{s.supplier_id}</td>
                <td style={{ fontWeight: 500 }}>{s.supplier_name}</td>
                <td>{s.city}</td>
                <td>{s.lead_time_days} days</td>
                <td><span className={s.reliability_score > 0.9 ? "badge badge-success" : "badge badge-warning"}>{s.reliability_score * 100}%</span></td>
                <td>₹{s.delivery_cost}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
