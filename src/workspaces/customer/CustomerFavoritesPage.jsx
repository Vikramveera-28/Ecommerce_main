import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import CustomerEmptyState from "./components/CustomerEmptyState";

export default function CustomerFavoritesPage() {
  const { accessToken } = useAuth();
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await apiClient.listWishlist(accessToken);
      if (!rows?.length) {
        setFavorites([]);
        return;
      }

      const detailedRows = await Promise.all(
        rows.map(async (row) => {
          try {
            const product = await apiClient.getProduct(row.product_id);
            return { ...row, product };
          } catch {
            return { ...row, product: null };
          }
        })
      );
      setFavorites(detailedRows);
    } catch (err) {
      setError(err.message);
      setFavorites([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const removeFavorite = async (wishlistId) => {
    try {
      await apiClient.deleteWishlistItem(accessToken, wishlistId);
      setNotice("Removed from favorites.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const moveToCart = async (favorite) => {
    try {
      await apiClient.addToCart(accessToken, { product_id: favorite.product_id, quantity: 1 });
      await apiClient.deleteWishlistItem(accessToken, favorite.id);
      setNotice("Moved to cart.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const formatPrice = (product) => {
    const price = product?.discount_price ?? product?.price ?? 0;
    return `$${Number(price).toFixed(2)}`;
  };

  return (
    <div className="elite-account-content elite-favorites-main">
      <section className="elite-account-card">
        <div className="elite-section-header">
          <h2>Favorites</h2>
          <span>{favorites.length} saved</span>
        </div>

        {notice && <p className="elite-notice">{notice}</p>}
        {loading && <p className="elite-muted">Loading favorites...</p>}
        {error && <p className="elite-error">{error}</p>}
        {!loading && !error && favorites.length === 0 ? (
          <CustomerEmptyState
            actionLabel="Continue Shopping"
            actionTo="/customer/products"
            className="elite-empty-state-inline"
            description="Looks like you have not added any favorites yet. Explore products and save the gear you love."
            icon="favorites"
            title="No favorites yet"
          />
        ) : (
          <div className="elite-favorites-grid">
            {favorites.map((favorite) => (
              <article className={`elite-favorite-card${favorite.product ? "" : " elite-favorite-card-no-media"}`} key={favorite.id}>
                {favorite.product ? (
                  <>
                    <div className="elite-favorite-card-media">
                      <img alt={favorite.product.name} loading="lazy" src={favorite.product.thumbnail} />
                    </div>

                    <div className="elite-favorite-card-content">
                      <h4>{favorite.product.name}</h4>
                      <p>{favorite.product.category?.name || "Sports Equipment"}</p>
                      <strong>{formatPrice(favorite.product)}</strong>

                      <div className="elite-favorite-actions">
                        <Link className="elite-order-secondary-action" to={`/customer/products/${favorite.product.id}`}>
                          Details
                        </Link>
                        <button className="elite-order-primary-action" onClick={() => moveToCart(favorite)} type="button">
                          Move to Cart
                        </button>
                        <button className="elite-order-secondary-action" onClick={() => removeFavorite(favorite.id)} type="button">
                          Remove
                        </button>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="elite-favorite-card-content">
                    <h4>Product unavailable</h4>
                    <p>This item no longer exists in the catalog.</p>
                    <div className="elite-favorite-actions">
                      <button className="elite-order-secondary-action" onClick={() => removeFavorite(favorite.id)} type="button">
                        Remove
                      </button>
                    </div>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
