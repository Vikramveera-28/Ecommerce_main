import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import EliteProductTile from "./components/EliteProductTile";
import StorefrontFooter from "./components/StorefrontFooter";

export default function CustomerHomePage() {
  const { accessToken } = useAuth();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    apiClient
      .listProducts({ per_page: 16, sort: "rating_desc" })
      .then((productRows) => {
        setProducts(productRows.items || []);
      })
      .catch((err) => {
        setError(err.message);
        setProducts([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const addToCart = async (product) => {
    try {
      await apiClient.addToCart(accessToken, { product_id: product.id, quantity: 1 });
      setNotice(`${product.name} added to cart.`);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="elite-page">
      <section className="elite-category-hero">
        <p className="elite-overline">Trending now</p>
        <h2>Top Rated Equipment</h2>
        <p>
          Home shows the highest-rated products only. Use Category to browse the full product catalog with all
          categories.
        </p>
        <Link className="elite-inline-link" to="/customer/products">
          Open all categories
        </Link>
      </section>

      {notice && <p className="elite-notice">{notice}</p>}
      {loading && <p className="elite-muted">Loading trending products...</p>}
      {error && <p className="elite-error">{error}</p>}

      <section className="elite-related-head">
        <div>
          <p className="elite-overline">Home feed</p>
          <h3>Trending Products</h3>
        </div>
        <Link className="elite-inline-link" to="/customer/products?sort=rating_desc">
          View full ranked list
        </Link>
      </section>

      <section className="elite-product-grid">
        {products.map((product) => (
          <EliteProductTile key={product.id} onQuickAdd={addToCart} product={product} />
        ))}
      </section>

      <StorefrontFooter />
    </div>
  );
}
