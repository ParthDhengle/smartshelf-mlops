/**
 * SmartShelf — TypeScript API Client
 * Centralized fetch wrapper for all backend calls natively throwing errors on failure.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Category {
  category_id: number;
  category_name: string;
  parent_category_id?: number | null;
}

export interface Product {
  product_id?: number;
  category: string;
  category_id?: number;
  product_name: string;
  brand: string;
  unit_size: string;
  perishable: boolean;
  shelf_life_days: number;
  base_cost_price?: number;
  base_sell_price?: number;
  cost_price?: number;
  base_price?: number;
  gross_margin: number;
}

async function apiFetch(path: string, options: RequestInit = {}) {
  const url = `${API_BASE}${path}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
    if (!res.ok) {
      const errorBody = await res.text();
      throw new Error(`API ${res.status}: ${errorBody}`);
    }
    return res.json();
  } catch (error: any) {
    throw new Error(`Connection Error: ${error.message}`);
  }
}

// ── Dashboard ────────────────────────────────────────────────────────────
export const getKPIs = () => apiFetch("/api/v1/dashboard/kpis");
export const getSalesTrend = () => apiFetch("/api/v1/dashboard/sales-trend");
export const getCategoryBreakdown = () => apiFetch("/api/v1/dashboard/category-breakdown");

// ── Products CRUD ────────────────────────────────────────────────────────
export const getProducts = () => apiFetch("/api/v1/products");
export const getCategories = () => apiFetch("/api/v1/categories");
export const createProduct = (data: Partial<Product>) => apiFetch("/api/v1/products", { method: "POST", body: JSON.stringify(data) });
export const updateProduct = (id: number, data: Partial<Product>) => apiFetch(`/api/v1/products/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteProduct = (id: number) => apiFetch(`/api/v1/products/${id}`, { method: "DELETE" });

export const getStores = () => apiFetch("/api/v1/stores");

// ── Predictions ──────────────────────────────────────────────────────────
export const predictDemand = (data: any) =>
  apiFetch("/api/v1/predict-demand", { method: "POST", body: JSON.stringify(data) });

export const optimizePrice = (data: any) =>
  apiFetch("/api/v1/optimize-price", { method: "POST", body: JSON.stringify(data) });

export const optimizeInventory = (data: any) =>
  apiFetch("/api/v1/optimize-inventory", { method: "POST", body: JSON.stringify(data) });

export const runFullPipeline = (data: any) =>
  apiFetch("/api/v1/full-pipeline", { method: "POST", body: JSON.stringify(data) });

// ── Sales ────────────────────────────────────────────────────────────────
export const simulateSale = (data: any) =>
  apiFetch("/api/v1/simulate-sale", { method: "POST", body: JSON.stringify(data) });

// ── Admin & Sync ─────────────────────────────────────────────────────────
export const clearModelCache = () =>
  apiFetch("/api/v1/admin/refresh-models", { method: "POST" });

export const syncWeather = (storeId: number) =>
  apiFetch("/api/v1/sync/weather", { method: "POST", body: JSON.stringify({ store_id: storeId, days_to_sync: 7 }) });

export const syncEconomic = () =>
  apiFetch("/api/v1/sync/economic", { method: "POST", body: JSON.stringify({ months_to_sync: 1 }) });

export const syncCalendar = () =>
  apiFetch("/api/v1/sync/calendar", { method: "POST", body: JSON.stringify({ year: new Date().getFullYear() }) });

export const getHealth = () => apiFetch("/health");

// ── Inventory / Suppliers ────────────────────────────────────────────────
export const getSuppliers = () => apiFetch("/api/v1/suppliers");

export const getInventoryList = (storeId: number = 1) => apiFetch(`/api/v1/inventory?store_id=${storeId}&limit=500`);

// ── Model Registry (live from MLflow) ────────────────────────────────────
export const getModelRegistry = () => apiFetch("/api/v1/admin/model-registry");

// ── Sales History ────────────────────────────────────────────────────────
export const getSalesHistory = (limit: number = 50) => apiFetch(`/api/v1/sales?limit=${limit}`);

// ── Store Optimization ───────────────────────────────────────────────────
export const optimizeStorePrice = (storeId: number) =>
  apiFetch("/api/v1/optimize-store", { method: "POST", body: JSON.stringify({ store_id: storeId }) });
