"use client";

import { useEffect, useState } from "react";
import { getProducts, getCategories, createProduct, updateProduct, deleteProduct, Product, Category } from "../../lib/api";

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  
  const [formData, setFormData] = useState<Partial<Product>>({
    category_id: 1,
    product_name: "",
    brand: "",
    unit_size: "1 unit",
    perishable: false,
    shelf_life_days: 0,
    base_cost_price: 0,
    base_sell_price: 0,
    gross_margin: 0,
  });

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [prodRes, catRes] = await Promise.all([getProducts(), getCategories()]);
      setProducts(prodRes);
      setCategories(catRes);
      if (catRes.length > 0) {
        setFormData(prev => ({ ...prev, category_id: catRes[0].category_id }));
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const openAddModal = () => {
    setIsEditing(false);
    setEditingId(null);
    setFormData({
      category_id: categories.length > 0 ? categories[0].category_id : 1,
      product_name: "",
      brand: "",
      unit_size: "1 unit",
      perishable: false,
      shelf_life_days: 0,
      base_cost_price: 0,
      base_sell_price: 0,
      gross_margin: 0,
    });
    setIsModalOpen(true);
  };

  const openEditModal = (product: Product) => {
    setIsEditing(true);
    setEditingId(product.product_id!);
    
    // Find category id from category name if necessary, 
    // but the backend might not return category_id in getProducts.
    // Try to map it back based on categories array
    const cat = categories.find(c => c.category_name === product.category);
    
    setFormData({
      category_id: cat?.category_id || categories[0]?.category_id,
      product_name: product.product_name,
      brand: product.brand,
      unit_size: "1 unit", // Placeholder if backend didn't return it
      perishable: product.perishable,
      shelf_life_days: product.shelf_life_days || 0,
      base_cost_price: product.cost_price,
      base_sell_price: product.base_price,
      gross_margin: ((product.base_price - product.cost_price) / product.base_price) * 100 || 0,
    });
    setIsModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this product?")) return;
    try {
      await deleteProduct(id);
      setProducts(products.filter(p => p.product_id !== id));
    } catch (e: any) {
      alert("Failed to delete: " + e.message);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Auto-calculate gross margin if the user didn't set it (optional)
      const cost = Number(formData.base_cost_price);
      const sell = Number(formData.base_sell_price);
      let margin = Number(formData.gross_margin);
      if (sell > 0 && cost > 0 && margin === 0) margin = ((sell - cost) / sell) * 100;
      
      const payload = {
        ...formData,
        base_cost_price: cost,
        base_sell_price: sell,
        gross_margin: margin,
        shelf_life_days: Number(formData.shelf_life_days)
      };

      if (isEditing && editingId) {
        await updateProduct(editingId, payload);
      } else {
        await createProduct(payload);
      }
      setIsModalOpen(false);
      fetchData(); // reload
    } catch (e: any) {
      alert("Failed to save product: " + e.message);
    }
  };

  const filtered = products.filter((p) => {
    const matchesSearch =
      p.product_name.toLowerCase().includes(search.toLowerCase()) ||
      p.brand.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = !categoryFilter || p.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  if (loading) {
    return <div className="loading-spinner"><div className="spinner" /></div>;
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">❌</div>
        <h3 style={{color: "var(--text-primary)"}}>Error Loading Products</h3>
        <p style={{color: "var(--danger)"}}>{error}</p>
        <button className="btn btn-primary" style={{marginTop: "1rem"}} onClick={fetchData}>Retry</button>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header animate-in" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2>Product Admin</h2>
          <p>Manage {products.length} products across {categories.length} categories</p>
        </div>
        <button className="btn btn-primary" onClick={openAddModal}>➕ Add Product</button>
      </div>

      <div className="card animate-in" style={{ marginBottom: "var(--space-xl)", display: "flex", gap: "var(--space-md)", flexWrap: "wrap", alignItems: "flex-end" }}>
        <div className="form-group" style={{ flex: 1, minWidth: 200, marginBottom: 0 }}>
          <label className="form-label">Search</label>
          <input
            className="form-input"
            placeholder="Search by name or brand..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="form-group" style={{ minWidth: 150, marginBottom: 0 }}>
          <label className="form-label">Category</label>
          <select className="form-select" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
            <option value="">All</option>
            {categories.map((c) => (
              <option key={c.category_id} value={c.category_name}>{c.category_name}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="card animate-in" style={{ overflow: "auto" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Product Name</th>
              <th>Category</th>
              <th>Brand</th>
              <th>Sell Price</th>
              <th>Cost Price</th>
              <th>Margin</th>
              <th>Perishable</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => {
              const margin = p.base_price > 0 ? ((p.base_price - p.cost_price) / p.base_price * 100).toFixed(1) : "0";
              return (
                <tr key={p.product_id}>
                  <td>{p.product_id}</td>
                  <td style={{ fontWeight: 500, color: "var(--text-primary)" }}>{p.product_name}</td>
                  <td><span className="badge badge-info">{p.category}</span></td>
                  <td>{p.brand}</td>
                  <td>₹{p.base_price}</td>
                  <td>₹{p.cost_price}</td>
                  <td>
                    <span className={`badge ${Number(margin) > 30 ? "badge-success" : Number(margin) > 15 ? "badge-warning" : "badge-danger"}`}>
                      {margin}%
                    </span>
                  </td>
                  <td>{p.perishable ? <span className="badge badge-warning">Yes</span> : <span className="badge badge-success">No</span>}</td>
                  <td>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="btn btn-secondary" style={{ padding: "4px 8px", fontSize: "0.75rem" }} onClick={() => openEditModal(p)}>Edit</button>
                      <button className="btn btn-danger" style={{ padding: "4px 8px", fontSize: "0.75rem" }} onClick={() => handleDelete(p.product_id!)}>Del</button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">🔍</div>
            <p>No products found matching your filters</p>
          </div>
        )}
      </div>

      {isModalOpen && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(4px)" }}>
          <div className="card animate-in" style={{ width: "100%", maxWidth: 600, maxHeight: "90vh", overflowY: "auto" }}>
            <h3 style={{ marginBottom: "var(--space-md)" }}>{isEditing ? "Edit Product" : "Add Product"}</h3>
            <form onSubmit={handleSubmit}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)" }}>
                <div className="form-group">
                  <label className="form-label">Product Name</label>
                  <input className="form-input" required value={formData.product_name} onChange={e => setFormData({...formData, product_name: e.target.value})} />
                </div>
                <div className="form-group">
                  <label className="form-label">Category</label>
                  <select className="form-select" required value={formData.category_id} onChange={e => setFormData({...formData, category_id: Number(e.target.value)})}>
                    {categories.map(c => <option key={c.category_id} value={c.category_id}>{c.category_name}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Brand</label>
                  <input className="form-input" required value={formData.brand} onChange={e => setFormData({...formData, brand: e.target.value})} />
                </div>
                <div className="form-group">
                  <label className="form-label">Unit Size</label>
                  <input className="form-input" required value={formData.unit_size} onChange={e => setFormData({...formData, unit_size: e.target.value})} />
                </div>
                <div className="form-group">
                  <label className="form-label">Cost Price (₹)</label>
                  <input className="form-input" required type="number" step="0.01" value={formData.base_cost_price} onChange={e => setFormData({...formData, base_cost_price: Number(e.target.value)})} />
                </div>
                <div className="form-group">
                  <label className="form-label">Sell Price (₹)</label>
                  <input className="form-input" required type="number" step="0.01" value={formData.base_sell_price} onChange={e => setFormData({...formData, base_sell_price: Number(e.target.value)})} />
                </div>
                <div className="form-group">
                  <label className="form-label">Perishable?</label>
                  <div style={{ marginTop: 8 }}>
                    <input type="checkbox" checked={formData.perishable} onChange={e => setFormData({...formData, perishable: e.target.checked})} /> Yes
                  </div>
                </div>
                {formData.perishable && (
                  <div className="form-group">
                    <label className="form-label">Shelf Life (Days)</label>
                    <input className="form-input" required type="number" value={formData.shelf_life_days} onChange={e => setFormData({...formData, shelf_life_days: Number(e.target.value)})} />
                  </div>
                )}
              </div>
              <div style={{ display: "flex", gap: "var(--space-md)", justifyContent: "flex-end", marginTop: "var(--space-lg)" }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">{isEditing ? "Save Changes" : "Create Product"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
