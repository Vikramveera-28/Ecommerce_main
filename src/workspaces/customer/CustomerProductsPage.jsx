import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import EliteProductTile from "./components/EliteProductTile";
import StorefrontFooter from "./components/StorefrontFooter";

function getPageWindow(page, totalPages) {
  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, start + 4);
  const adjustedStart = Math.max(1, end - 4);
  return Array.from({ length: end - adjustedStart + 1 }, (_, index) => adjustedStart + index);
}

export default function CustomerProductsPage() {
  const { accessToken } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, pages: 1, total: 0 });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const filters = useMemo(
    () => ({
      q: searchParams.get("q") || "",
      category: searchParams.get("category") || "",
      sort: searchParams.get("sort") || "created_desc",
      page: Math.max(Number(searchParams.get("page") || 1), 1),
    }),
    [searchParams]
  );

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [productRes, categoryRes] = await Promise.all([
          apiClient.listProducts({
            q: filters.q,
            category: filters.category,
            sort: filters.sort,
            page: filters.page,
            per_page: 12,
          }),
          apiClient.listCategories(),
        ]);

        setProducts(productRes.items || []);
        setPagination(productRes.pagination || { page: 1, pages: 1, total: (productRes.items || []).length });
        setCategories(categoryRes || []);
      } catch (err) {
        setError(err.message);
        setProducts([]);
        setPagination({ page: 1, pages: 1, total: 0 });
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [filters.q, filters.category, filters.sort, filters.page]);

  const setParam = (key, value) => {
    setSearchParams((old) => {
      const next = new URLSearchParams(old);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      if (key !== "page") {
        next.delete("page");
      }
      return next;
    });
  };

  const setPage = (page) => {
    if (page < 1 || page > pagination.pages || page === filters.page) return;
    setParam("page", String(page));
  };

  const addToCart = async (product) => {
    try {
      await apiClient.addToCart(accessToken, { product_id: product.id, quantity: 1 });
      setNotice(`${product.name} added to cart.`);
    } catch (err) {
      setError(err.message);
    }
  };

  const pageNumbers = useMemo(
    () => getPageWindow(filters.page, Math.max(pagination.pages, 1)),
    [filters.page, pagination.pages]
  );

  return (
    <div className="elite-page">
      <section className="elite-category-hero">
        <p className="elite-overline">Complete your gear</p>
        <h2>The Essentials</h2>
        <p>
          Build your match-day setup with pro-grade bats, accessories, and training equipment tuned for performance.
        </p>
        <div className="elite-category-search-row">
          <input
            onChange={(event) => setParam("q", event.target.value)}
            placeholder="Search by product, brand, or category"
            value={filters.q}
          />
          <span>{pagination.total} items detected</span>
        </div>
      </section>

      <section className="elite-category-tabs">
        <button
          className={`elite-tab-chip${!filters.category ? " active" : ""}`}
          onClick={() => setParam("category", "")}
          type="button"
        >
          All Equipment
        </button>
        {categories.slice(0, 8).map((category) => (
          <button
            className={`elite-tab-chip${filters.category === category.slug ? " active" : ""}`}
            key={category.id}
            onClick={() => setParam("category", category.slug)}
            type="button"
          >
            {category.name}
          </button>
        ))}
      </section>

      <section className="elite-catalog-controls">
        <label htmlFor="catalog-sort">Sort</label>
        <select
          id="catalog-sort"
          onChange={(event) => setParam("sort", event.target.value)}
          value={filters.sort}
        >
          <option value="created_desc">Newest</option>
          <option value="rating_desc">Top Rated</option>
          <option value="price_asc">Price Low to High</option>
          <option value="price_desc">Price High to Low</option>
        </select>
        <Link className="elite-inline-link" to="/customer/favorites">
          View saved items
        </Link>
      </section>

      {notice && <p className="elite-notice">{notice}</p>}
      {loading && <p className="elite-muted">Loading products...</p>}
      {error && <p className="elite-error">{error}</p>}
      {!loading && !error && products.length === 0 && <p className="elite-muted">No products found for this filter set.</p>}

      <section className="elite-product-grid">
        {products.map((product) => (
          <EliteProductTile key={product.id} onQuickAdd={addToCart} product={product} />
        ))}
      </section>

      <section className="elite-pagination">
        <button disabled={filters.page <= 1} onClick={() => setPage(filters.page - 1)} type="button">
          Prev
        </button>
        {pageNumbers.map((page) => (
          <button
            className={page === filters.page ? "active" : ""}
            key={page}
            onClick={() => setPage(page)}
            type="button"
          >
            {String(page).padStart(2, "0")}
          </button>
        ))}
        <button disabled={filters.page >= pagination.pages} onClick={() => setPage(filters.page + 1)} type="button">
          Next
        </button>
      </section>

      <StorefrontFooter />
    </div>
  );
}
