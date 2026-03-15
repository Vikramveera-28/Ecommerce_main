import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";

const PAGE_SIZE = 10;

function formatCurrency(value) {
  return `$${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function currentMonthRevenue(orders) {
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  return (orders || [])
    .filter((row) => {
      const created = new Date(row.created_at);
      return !Number.isNaN(created.getTime()) && created >= monthStart && row.order_status !== "cancelled";
    })
    .reduce((sum, row) => sum + Number(row.price || 0) * Number(row.quantity || 0), 0);
}

function getStockState(stockQuantity) {
  const stock = Number(stockQuantity || 0);
  if (stock <= 0) {
    return { key: "out", label: "Out of Stock", className: "out", percent: 0 };
  }
  if (stock <= 20) {
    return { key: "low", label: "Low Stock", className: "low", percent: Math.min(100, Math.round(stock)) };
  }
  return { key: "in", label: "In Stock", className: "in", percent: Math.min(100, Math.round(stock)) };
}

function productThumb(name) {
  const seed = encodeURIComponent((name || "P").slice(0, 2).toUpperCase());
  return `https://dummyimage.com/64x64/e7edf4/1a2d48&text=${seed}`;
}

function exportProductsCsv(rows) {
  const headers = ["product", "sku", "category", "price", "stock", "stock_status", "sold_qty", "sold_revenue"];
  const body = rows.map((row) => [
    row.name,
    row.sku,
    row.categoryName,
    Number(row.price || 0).toFixed(2),
    row.stock_quantity,
    row.stockState.label,
    row.soldQty,
    Number(row.soldRevenue || 0).toFixed(2),
  ]);
  const csv = [headers, ...body]
    .map((line) => line.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(","))
    .join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "vendor_product_analysis.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export default function VendorProductsPage() {
  const { accessToken } = useAuth();
  const [searchParams] = useSearchParams();
  const searchFromUrl = searchParams.get("q") || "";
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState("monitor");
  const [searchTerm, setSearchTerm] = useState(searchFromUrl);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [stockFilter, setStockFilter] = useState("all");
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedProductIds, setSelectedProductIds] = useState([]);
  const [form, setForm] = useState({
    name: "",
    sku: "",
    category_id: "",
    price: "",
    stock_quantity: 0,
    description: "",
  });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [productRows, orderRows, categoryRows] = await Promise.all([
        apiClient.listVendorProducts(accessToken),
        apiClient.listVendorOrders(accessToken),
        apiClient.listCategories(),
      ]);
      const nextProducts = productRows || [];
      const nextCategories = categoryRows || [];

      setProducts(nextProducts);
      setOrders(orderRows || []);
      setCategories(nextCategories);

      if (!form.category_id && nextCategories.length > 0) {
        setForm((old) => ({ ...old, category_id: String(nextCategories[0].id) }));
      }
    } catch (err) {
      setError(err.message);
      setProducts([]);
      setOrders([]);
      setCategories([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [accessToken]);

  useEffect(() => {
    setSearchTerm(searchFromUrl);
  }, [searchFromUrl]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, categoryFilter, stockFilter]);

  const create = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("");

    if (!form.category_id) {
      setError("Please select a category.");
      return;
    }

    try {
      await apiClient.createVendorProduct(accessToken, {
        ...form,
        category_id: Number(form.category_id),
        price: Number(form.price),
        stock_quantity: Number(form.stock_quantity || 0),
      });
      setForm({
        name: "",
        sku: "",
        category_id: categories.length ? String(categories[0].id) : "",
        price: "",
        stock_quantity: 0,
        description: "",
      });
      setNotice("Product submitted for approval.");
      setActiveSection("monitor");
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const analytics = useMemo(() => {
    const totalProducts = products.length;
    const activeListings = products.filter((p) => p.status === "active" && p.approval_status === "approved").length;
    const pendingApproval = products.filter((p) => p.approval_status === "pending").length;
    const monthlyRevenue = currentMonthRevenue(orders);
    const inventoryValue = products.reduce((sum, product) => sum + Number(product.price || 0) * Number(product.stock_quantity || 0), 0);

    const soldByProduct = new Map();
    orders.forEach((row) => {
      if (row.order_status === "cancelled") return;
      const current = soldByProduct.get(row.product_id) || { qty: 0, revenue: 0 };
      current.qty += Number(row.quantity || 0);
      current.revenue += Number(row.price || 0) * Number(row.quantity || 0);
      soldByProduct.set(row.product_id, current);
    });

    const lowStockItems = products.filter((product) => {
      const stock = Number(product.stock_quantity || 0);
      return stock > 0 && stock <= 20;
    }).length;

    const outOfStock = products.filter((product) => Number(product.stock_quantity || 0) <= 0).length;

    return {
      totalProducts,
      activeListings,
      pendingApproval,
      monthlyRevenue,
      inventoryValue,
      lowStockItems,
      outOfStock,
      soldByProduct,
    };
  }, [orders, products]);

  const categoryNameById = useMemo(() => {
    const map = new Map();
    categories.forEach((category) => {
      map.set(Number(category.id), category.name);
    });
    return map;
  }, [categories]);

  const monitorRows = useMemo(
    () =>
      products.map((product) => {
        const sold = analytics.soldByProduct.get(product.id) || { qty: 0, revenue: 0 };
        const stockState = getStockState(product.stock_quantity);
        return {
          ...product,
          categoryName: categoryNameById.get(Number(product.category_id)) || `Category #${product.category_id}`,
          soldQty: sold.qty,
          soldRevenue: sold.revenue,
          stockState,
          thumbnail: productThumb(product.name),
        };
      }),
    [analytics.soldByProduct, categoryNameById, products]
  );

  const filteredRows = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return monitorRows.filter((row) => {
      const matchesQuery =
        !q ||
        row.name.toLowerCase().includes(q) ||
        row.sku.toLowerCase().includes(q) ||
        row.categoryName.toLowerCase().includes(q);
      const matchesCategory = categoryFilter === "all" || String(row.category_id) === categoryFilter;
      const matchesStock = stockFilter === "all" || row.stockState.key === stockFilter;
      return matchesQuery && matchesCategory && matchesStock;
    });
  }, [categoryFilter, monitorRows, searchTerm, stockFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE));

  useEffect(() => {
    setCurrentPage((old) => Math.min(old, totalPages));
  }, [totalPages]);

  const pagedRows = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredRows.slice(start, start + PAGE_SIZE);
  }, [currentPage, filteredRows]);

  const pageIds = pagedRows.map((row) => row.id);
  const allOnPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedProductIds.includes(id));

  const toggleOne = (productId) => {
    setSelectedProductIds((old) =>
      old.includes(productId) ? old.filter((id) => id !== productId) : [...old, productId]
    );
  };

  const toggleAllOnPage = () => {
    setSelectedProductIds((old) => {
      if (allOnPageSelected) {
        return old.filter((id) => !pageIds.includes(id));
      }
      const merged = [...old];
      pageIds.forEach((id) => {
        if (!merged.includes(id)) merged.push(id);
      });
      return merged;
    });
  };

  const startEntry = filteredRows.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const endEntry = Math.min(currentPage * PAGE_SIZE, filteredRows.length);

  return (
    <div className="vendor-page">
      {activeSection === "monitor" && (
        <>
          <section className="vendor-analysis-header">
            <div>
              <h2>My Products</h2>
              <p>Manage your inventory, monitor stock levels, and perform bulk operations.</p>
            </div>
            <div className="vendor-analysis-actions">
              <button type="button" onClick={() => setNotice("Import flow can be wired in the next step.")}>Import Stock</button>
              <button type="button" onClick={() => exportProductsCsv(filteredRows)}>Export Stock</button>
              <button className="primary" onClick={() => setActiveSection("add")} type="button">
                Add Product
              </button>
            </div>
          </section>

          <section className="vendor-analysis-stats">
            <article>
              <div className="top">
                <span className="icon total">PR</span>
                <b className="up">+12%</b>
              </div>
              <p>Total Products</p>
              <h3>{analytics.totalProducts.toLocaleString()}</h3>
            </article>
            <article>
              <div className="top">
                <span className="icon low">LS</span>
              </div>
              <p>Low Stock Items</p>
              <h3>{analytics.lowStockItems.toLocaleString()}</h3>
            </article>
            <article>
              <div className="top">
                <span className="icon out">OS</span>
              </div>
              <p>Out of Stock</p>
              <h3>{analytics.outOfStock.toLocaleString()}</h3>
            </article>
            <article>
              <div className="top">
                <span className="icon value">IV</span>
              </div>
              <p>Inventory Value</p>
              <h3>{formatCurrency(analytics.inventoryValue)}</h3>
            </article>
          </section>

          <section className="vendor-analysis-filters">
            <label className="search">
              <input
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="Search by name, SKU, or category..."
                value={searchTerm}
              />
            </label>

            <select onChange={(event) => setCategoryFilter(event.target.value)} value={categoryFilter}>
              <option value="all">All Categories</option>
              {categories.map((category) => (
                <option key={category.id} value={String(category.id)}>
                  {category.name}
                </option>
              ))}
            </select>

            <select onChange={(event) => setStockFilter(event.target.value)} value={stockFilter}>
              <option value="all">Stock Status</option>
              <option value="in">In Stock</option>
              <option value="low">Low Stock</option>
              <option value="out">Out of Stock</option>
            </select>
          </section>

          <section className="vendor-analysis-table-card">
            {loading && <p className="elite-muted">Loading products...</p>}
            {error && <p className="elite-error">{error}</p>}
            {notice && <p className="elite-notice">{notice}</p>}

            <div className="vendor-analysis-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th className="check-col">
                      <input checked={allOnPageSelected} onChange={toggleAllOnPage} type="checkbox" />
                    </th>
                    <th>Product</th>
                    <th>SKU</th>
                    <th>Category</th>
                    <th>Price</th>
                    <th>Stock Levels</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pagedRows.length === 0 ? (
                    <tr>
                      <td className="empty" colSpan={8}>
                        No products found for current filters.
                      </td>
                    </tr>
                  ) : (
                    pagedRows.map((row) => (
                      <tr key={row.id}>
                        <td className="check-col">
                          <input
                            checked={selectedProductIds.includes(row.id)}
                            onChange={() => toggleOne(row.id)}
                            type="checkbox"
                          />
                        </td>
                        <td>
                          <div className="vendor-product-cell">
                            <img alt={row.name} src={row.thumbnail} />
                            <div>
                              <strong>{row.name}</strong>
                              <span>{row.soldQty} sold | {formatCurrency(row.soldRevenue)}</span>
                            </div>
                          </div>
                        </td>
                        <td>{row.sku}</td>
                        <td>{row.categoryName}</td>
                        <td>{formatCurrency(row.price)}</td>
                        <td>
                          <div className="vendor-stock-level">
                            <small>{row.stock_quantity} units</small>
                            <div className="meter">
                              <i className={row.stockState.className} style={{ width: `${row.stockState.percent}%` }} />
                            </div>
                            <small>{row.stockState.percent}%</small>
                          </div>
                        </td>
                        <td>
                          <span className={`vendor-status ${row.stockState.className}`}>{row.stockState.label}</span>
                        </td>
                        <td>
                          <button
                            className="vendor-mini-action"
                            onClick={() => setNotice(`Stock update for ${row.name} can be wired in next step.`)}
                            type="button"
                          >
                            Update
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="vendor-analysis-table-footer">
              <p>
                Showing {startEntry} to {endEntry} of {filteredRows.length.toLocaleString()} entries
              </p>

              <div className="vendor-analysis-pagination">
                <button disabled={currentPage <= 1} onClick={() => setCurrentPage((old) => Math.max(1, old - 1))} type="button">
                  Prev
                </button>
                {Array.from({ length: totalPages }, (_, idx) => idx + 1)
                  .slice(0, 5)
                  .map((pageNo) => (
                    <button
                      className={pageNo === currentPage ? "active" : ""}
                      key={pageNo}
                      onClick={() => setCurrentPage(pageNo)}
                      type="button"
                    >
                      {pageNo}
                    </button>
                  ))}
                <button
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((old) => Math.min(totalPages, old + 1))}
                  type="button"
                >
                  Next
                </button>
              </div>
            </div>
          </section>

          <section className="vendor-analysis-tip">
            <strong>Quick Tip: Bulk Inventory Update</strong>
            <p>
              Select multiple products to prepare bulk price or stock actions. Use Import Stock for CSV updates and
              Export Stock for reporting.
            </p>
          </section>
        </>
      )}

      {activeSection === "add" && (
        <>
          <section className="vendor-products-switch">
            <button className="active" type="button">
              Add Product
            </button>
            <button onClick={() => setActiveSection("monitor")} type="button">
              My Products Monitoring
            </button>
          </section>

          {loading && <p className="elite-muted">Loading products...</p>}
          {error && <p className="elite-error">{error}</p>}
          {notice && <p className="elite-notice">{notice}</p>}

          <section className="vendor-products-layout vendor-products-layout-single">
            <form className="vendor-product-form" onSubmit={create}>
              <div className="vendor-form-head">
                <h3>Add New Product</h3>
                <p>List new elite sports gear to the marketplace.</p>
              </div>

              <label>
                Product Name
                <input onChange={(e) => setForm((o) => ({ ...o, name: e.target.value }))} placeholder="e.g. Pro-Series Carbon Bat" required value={form.name} />
              </label>

              <div className="vendor-form-grid-two">
                <label>
                  SKU
                  <input onChange={(e) => setForm((o) => ({ ...o, sku: e.target.value }))} placeholder="ES-10293" required value={form.sku} />
                </label>
                <label>
                  Price ($)
                  <input onChange={(e) => setForm((o) => ({ ...o, price: e.target.value }))} placeholder="299.99" required type="number" value={form.price} />
                </label>
              </div>

              <div className="vendor-form-grid-two">
                <label>
                  Stock
                  <input
                    onChange={(e) => setForm((o) => ({ ...o, stock_quantity: e.target.value }))}
                    placeholder="42"
                    type="number"
                    value={form.stock_quantity}
                  />
                </label>
                <label>
                  Category
                  <select onChange={(e) => setForm((o) => ({ ...o, category_id: e.target.value }))} required value={form.category_id}>
                    {categories.length === 0 ? (
                      <option value="">No categories</option>
                    ) : (
                      categories.map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                        </option>
                      ))
                    )}
                  </select>
                </label>
              </div>

              <label>
                Description
                <textarea
                  onChange={(e) => setForm((o) => ({ ...o, description: e.target.value }))}
                  placeholder="Describe the premium features..."
                  rows={4}
                  value={form.description}
                />
              </label>

              <div className="vendor-upload-placeholder">
                <span>Click to upload product media or drag and drop</span>
                <small>PNG, JPG up to 10MB</small>
              </div>

              <button className="vendor-submit-btn" type="submit">
                Submit for Approval
              </button>
            </form>
          </section>
        </>
      )}
    </div>
  );
}
