import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import CustomerEmptyState from "./components/CustomerEmptyState";

const FALLBACK_IMAGE = "https://dummyimage.com/520x360/e6ecf2/1b2a3f&text=Elite+Sports";
const TAX_RATE = 0.08;

function toCurrency(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

function getUnitPrice(item) {
  const discount = Number(item.product?.discount_price || 0);
  const regular = Number(item.product?.price || 0);
  return discount > 0 ? discount : regular;
}

export default function CustomerCartPage() {
  const { accessToken } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [promoCode, setPromoCode] = useState("ELITE20");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const cartRows = await apiClient.listCart(accessToken);
      if (!cartRows?.length) {
        setItems([]);
        return;
      }

      const detailedRows = await Promise.all(
        cartRows.map(async (row) => {
          try {
            const details = await apiClient.getProduct(row.product_id);
            return {
              ...row,
              product: {
                ...row.product,
                ...details,
              },
            };
          } catch {
            return row;
          }
        })
      );

      setItems(detailedRows);
    } catch (err) {
      setError(err.message);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const subtotal = useMemo(
    () =>
      items.reduce((sum, item) => {
        return sum + getUnitPrice(item) * Number(item.quantity || 0);
      }, 0),
    [items]
  );

  const shipping = 0;
  const tax = subtotal * TAX_RATE;
  const total = subtotal + shipping + tax;

  const updateQty = async (item, quantity) => {
    if (quantity < 1) return;
    try {
      await apiClient.updateCartItem(accessToken, item.id, { quantity });
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const removeItem = async (itemId) => {
    try {
      await apiClient.deleteCartItem(accessToken, itemId);
      setNotice("Item removed from cart.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const clearCart = async () => {
    if (!items.length) return;
    try {
      await Promise.all(items.map((item) => apiClient.deleteCartItem(accessToken, item.id)));
      setNotice("Cart cleared.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const applyPromo = (event) => {
    event.preventDefault();
    if (!promoCode.trim()) {
      setNotice("Enter a promo code first.");
      return;
    }
    setNotice(`Promo code ${promoCode.trim().toUpperCase()} will be validated at checkout.`);
  };

  return (
    <div className="elite-account-content elite-cart-main">
      <section className="elite-cart-header-block">
        <h2>Shopping Cart</h2>
        <p>
          You have <strong>{items.length} items</strong> in your cart
        </p>
      </section>

      {notice && <p className="elite-notice">{notice}</p>}
      {loading && <p className="elite-muted">Loading cart...</p>}
      {error && <p className="elite-error">{error}</p>}

      {!loading && !error && items.length === 0 && (
        <CustomerEmptyState
          actionLabel="Continue Shopping"
          actionTo="/customer/products"
          description="Looks like you have not added anything to your cart yet. Explore our latest sports gear and find what you need."
          icon="cart"
          title="Your cart is empty"
        />
      )}

      {!loading && items.length > 0 && (
        <div className="elite-cart-layout-grid">
          <section className="elite-cart-list-panel">
            <div className="elite-cart-items">
              {items.map((item) => {
                const unitPrice = getUnitPrice(item);
                const regularPrice = Number(item.product?.price || unitPrice);
                const lineTotal = unitPrice * Number(item.quantity || 0);
                const hasDiscount = regularPrice > unitPrice;
                const stockQuantity = Number(item.product?.stock_quantity || 0);
                const isMaxed = stockQuantity > 0 && Number(item.quantity || 0) >= stockQuantity;
                const metaText = [item.product?.category?.name || "Sports Equipment", `Stock: ${stockQuantity || "N/A"}`]
                  .filter(Boolean)
                  .join(" | ");

                return (
                  <article className="elite-cart-item-card" key={item.id}>
                    <div className="elite-cart-item-media">
                      <img
                        alt={item.product?.name || "Cart item"}
                        loading="lazy"
                        src={item.product?.thumbnail || FALLBACK_IMAGE}
                      />
                    </div>

                    <div className="elite-cart-item-content">
                      <div className="elite-cart-item-top">
                        <div>
                          <h3>{item.product?.name || `Product ${item.product_id}`}</h3>
                          <p>{metaText}</p>
                        </div>

                        <button className="elite-cart-remove-btn" onClick={() => removeItem(item.id)} type="button">
                          Remove
                        </button>
                      </div>

                      <div className="elite-cart-item-bottom">
                        <div className="elite-cart-qty-control">
                          <button onClick={() => updateQty(item, item.quantity - 1)} type="button">
                            -
                          </button>
                          <span>{item.quantity}</span>
                          <button disabled={isMaxed} onClick={() => updateQty(item, item.quantity + 1)} type="button">
                            +
                          </button>
                        </div>

                        <div className="elite-cart-price-wrap">
                          {hasDiscount && <span>{toCurrency(regularPrice)}</span>}
                          <strong>{toCurrency(lineTotal)}</strong>
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="elite-cart-bottom-bar">
              <Link className="elite-cart-inline-link" to="/customer/products">
                Continue Shopping
              </Link>
              <button className="elite-cart-clear-btn" onClick={clearCart} type="button">
                Clear Cart
              </button>
            </div>
          </section>

          <aside className="elite-cart-summary-panel">
            <h3>Order Summary</h3>

            <div className="elite-cart-summary-lines">
              <div>
                <span>Subtotal</span>
                <strong>{toCurrency(subtotal)}</strong>
              </div>
              <div>
                <span>Shipping</span>
                <strong className="green">Free</strong>
              </div>
              <div>
                <span>Tax</span>
                <strong>{toCurrency(tax)}</strong>
              </div>
            </div>

            <form className="elite-cart-promo" onSubmit={applyPromo}>
              <label htmlFor="cart-promo">Promo Code</label>
              <div>
                <input
                  id="cart-promo"
                  onChange={(event) => setPromoCode(event.target.value)}
                  placeholder="ELITE20"
                  value={promoCode}
                />
                <button type="submit">Apply</button>
              </div>
            </form>

            <div className="elite-cart-total-row">
              <span>Total Amount</span>
              <strong>{toCurrency(total)}</strong>
            </div>

            <Link className="elite-cart-checkout-btn" to="/customer/payment">
              Proceed to Checkout
            </Link>

            <p className="elite-cart-secure-note">Secure checkout guaranteed</p>
          </aside>
        </div>
      )}
    </div>
  );
}
