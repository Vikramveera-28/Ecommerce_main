import { useEffect, useMemo, useState } from "react";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";

const VENDOR_STATUS_FILTER = ["", "pending", "approved", "rejected"];
const PRODUCT_STATUS_FILTER = ["", "pending", "approved", "rejected"];

export default function AdminModerationPage() {
  const { accessToken } = useAuth();
  const [vendors, setVendors] = useState([]);
  const [products, setProducts] = useState([]);
  const [activeTag, setActiveTag] = useState("vendor");
  const [query, setQuery] = useState("");
  const [vendorStatus, setVendorStatus] = useState("");
  const [productStatus, setProductStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    const [vendorRows, productRows] = await Promise.all([
      apiClient.listVendors(),
      apiClient.listProducts({ per_page: 300 }),
    ]);
    setVendors(vendorRows || []);
    setProducts(productRows.items || []);
  };

  useEffect(() => {
    let cancelled = false;
    const bootstrap = async () => {
      setLoading(true);
      setError("");
      try {
        await load();
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  const filteredVendors = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return vendors.filter((vendor) => {
      const statusOk = !vendorStatus || vendor.kyc_status === vendorStatus;
      if (!statusOk) return false;
      if (!needle) return true;
      return [vendor.store_name, vendor.store_slug, vendor.kyc_status]
        .map((value) => String(value || "").toLowerCase())
        .join(" ")
        .includes(needle);
    });
  }, [query, vendorStatus, vendors]);

  const filteredProducts = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return products.filter((product) => {
      const statusOk = !productStatus || product.approval_status === productStatus;
      if (!statusOk) return false;
      if (!needle) return true;
      return [product.name, product.vendor?.store_name, product.approval_status]
        .map((value) => String(value || "").toLowerCase())
        .join(" ")
        .includes(needle);
    });
  }, [productStatus, products, query]);

  const approveVendor = async (vendorId) => {
    setError("");
    try {
      await apiClient.approveVendor(accessToken, vendorId);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const approveProduct = async (productId) => {
    setError("");
    try {
      await apiClient.approveProduct(accessToken, productId, { approved: true });
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <section className="delivery-page">
        <p className="delivery-loading">Loading moderation data...</p>
      </section>
    );
  }

  return (
    <div className="delivery-page">
      <header className="delivery-page-head">
        <h2>Moderation</h2>
        <p>Approve vendors and products with quick filters for status and search.</p>
      </header>

      <article className="delivery-card">
        <div className="delivery-row-actions">
          <button
            className={`delivery-mini-btn ${activeTag === "vendor" ? "strong" : "muted"}`}
            onClick={() => setActiveTag("vendor")}
            type="button"
          >
            Vendor Tag
          </button>
          <button
            className={`delivery-mini-btn ${activeTag === "product" ? "strong" : "muted"}`}
            onClick={() => setActiveTag("product")}
            type="button"
          >
            Product Tag
          </button>
        </div>

        <div className="delivery-filter-row">
          {activeTag === "vendor" ? (
            <label>
              <span>Vendor KYC</span>
              <select onChange={(event) => setVendorStatus(event.target.value)} value={vendorStatus}>
                {VENDOR_STATUS_FILTER.map((status) => (
                  <option key={status || "all"} value={status}>
                    {status || "All Vendor Status"}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label>
              <span>Product Approval</span>
              <select onChange={(event) => setProductStatus(event.target.value)} value={productStatus}>
                {PRODUCT_STATUS_FILTER.map((status) => (
                  <option key={status || "all"} value={status}>
                    {status || "All Product Status"}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            <span>Search</span>
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Vendor, product, status..."
              value={query}
            />
          </label>
        </div>
      </article>

      {error && <p className="delivery-error">{error}</p>}

      {activeTag === "vendor" ? (
        <article className="delivery-card">
          <div className="delivery-card-head">
            <h3>Vendor Approval</h3>
            <span>{filteredVendors.length} rows</span>
          </div>
          <div className="delivery-task-table-wrap">
            <table className="delivery-task-table">
              <thead>
                <tr>
                  <th>Store</th>
                  <th>Slug</th>
                  <th>KYC Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredVendors.length === 0 && (
                  <tr>
                    <td className="empty" colSpan={4}>
                      No vendor rows for this filter.
                    </td>
                  </tr>
                )}
                {filteredVendors.map((vendor) => (
                  <tr key={vendor.id}>
                    <td>{vendor.store_name}</td>
                    <td>{vendor.store_slug}</td>
                    <td>
                      <span className={`delivery-status-pill ${vendor.kyc_status === "approved" ? "success" : "warning"}`}>
                        {vendor.kyc_status}
                      </span>
                    </td>
                    <td>
                      {vendor.kyc_status !== "approved" && (
                        <button className="delivery-mini-btn strong" onClick={() => approveVendor(vendor.id)} type="button">
                          Approve
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      ) : (
        <article className="delivery-card">
          <div className="delivery-card-head">
            <h3>Product Approval</h3>
            <span>{filteredProducts.length} rows</span>
          </div>
          <div className="delivery-task-table-wrap">
            <table className="delivery-task-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Vendor</th>
                  <th>Approval Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.length === 0 && (
                  <tr>
                    <td className="empty" colSpan={4}>
                      No product rows for this filter.
                    </td>
                  </tr>
                )}
                {filteredProducts.map((product) => (
                  <tr key={product.id}>
                    <td>{product.name}</td>
                    <td>{product.vendor?.store_name || "-"}</td>
                    <td>
                      <span className={`delivery-status-pill ${product.approval_status === "approved" ? "success" : "warning"}`}>
                        {product.approval_status}
                      </span>
                    </td>
                    <td>
                      {product.approval_status !== "approved" && (
                        <button className="delivery-mini-btn strong" onClick={() => approveProduct(product.id)} type="button">
                          Approve
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      )}
    </div>
  );
}
