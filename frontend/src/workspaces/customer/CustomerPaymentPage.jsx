import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";

const initialAddress = {
  full_name: "",
  phone: "",
  address_line_1: "",
  address_line_2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "India",
  is_default: false,
};

const SHIPPING_METHODS = [
  { id: "standard", label: "Standard Shipping", note: "3-5 Business Days", fee: 0 },
  { id: "express", label: "Express Delivery", note: "Next Day Delivery", fee: 12.99 },
];

function formatCurrency(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

export default function CustomerPaymentPage() {
  const { accessToken } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [addresses, setAddresses] = useState([]);
  const [shippingAddressId, setShippingAddressId] = useState("");
  const [addressForm, setAddressForm] = useState(initialAddress);
  const [savedCard, setSavedCard] = useState({ has_card: false, cardholder_name: null, card_last4: null });
  const [paymentMethod, setPaymentMethod] = useState("cod");
  const [shippingMethod, setShippingMethod] = useState("standard");
  const [promoCode, setPromoCode] = useState("");
  const [cardInput, setCardInput] = useState({ card_number: "", card_pin: "" });
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [cartRes, addressRes, cardRes] = await Promise.allSettled([
        apiClient.listCart(accessToken),
        apiClient.listAddresses(accessToken),
        apiClient.getPaymentCard(accessToken),
      ]);

      const nextItems = cartRes.status === "fulfilled" ? cartRes.value || [] : [];
      const nextAddresses = addressRes.status === "fulfilled" ? addressRes.value || [] : [];
      const nextCard =
        cardRes.status === "fulfilled"
          ? cardRes.value || { has_card: false, cardholder_name: null, card_last4: null }
          : { has_card: false, cardholder_name: null, card_last4: null };

      setItems(nextItems);
      setAddresses(nextAddresses);
      setSavedCard(nextCard);

      if (nextAddresses.length > 0) {
        const defaultAddress = nextAddresses.find((address) => address.is_default) || nextAddresses[0];
        setShippingAddressId(String(defaultAddress.id));
      } else {
        setShippingAddressId("");
      }

      if (cartRes.status === "rejected") {
        setError(cartRes.reason?.message || "Failed to load cart.");
      } else if (addressRes.status === "rejected") {
        setError(addressRes.reason?.message || "Failed to load addresses.");
      } else if (cardRes.status === "rejected") {
        setNotice("Saved card service is temporarily unavailable. You can still use COD.");
      }
    } catch (err) {
      setError(err.message);
      setItems([]);
      setAddresses([]);
      setSavedCard({ has_card: false, cardholder_name: null, card_last4: null });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const selectedShipping = useMemo(
    () => SHIPPING_METHODS.find((method) => method.id === shippingMethod) || SHIPPING_METHODS[0],
    [shippingMethod]
  );

  const subtotal = useMemo(
    () =>
      items.reduce((sum, item) => {
        const unit = item.product.discount_price || item.product.price;
        return sum + unit * item.quantity;
      }, 0),
    [items]
  );

  const shippingFee = selectedShipping.fee;
  const estimatedTax = Number((subtotal * 0.08).toFixed(2));
  const totalPayable = Number((subtotal + shippingFee + estimatedTax).toFixed(2));

  const createAddress = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const address = await apiClient.createAddress(accessToken, addressForm);
      setAddresses((old) => [address, ...old]);
      setShippingAddressId(String(address.id));
      setAddressForm(initialAddress);
      setNotice("Address saved. You can now place your order.");
    } catch (err) {
      setError(err.message);
    }
  };

  const placeOrder = async () => {
    if (items.length === 0) {
      setError("Your cart is empty.");
      return;
    }
    if (!shippingAddressId) {
      setError("Select or add a shipping address.");
      return;
    }

    if (paymentMethod === "card") {
      if (!savedCard?.has_card) {
        setError("Please save your card details in Profile page before card payment.");
        return;
      }
      const cardNumber = (cardInput.card_number || "").replace(/\D/g, "");
      const cardPin = (cardInput.card_pin || "").trim();
      if (!cardNumber || !cardPin) {
        setError("Card number and PIN are required for card payment.");
        return;
      }
    }

    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      const payload = {
        shipping_address_id: Number(shippingAddressId),
        use_cart: true,
        payment_method: paymentMethod,
        shipping_fee: shippingFee,
        tax_amount: estimatedTax,
      };
      if (paymentMethod === "card") {
        payload.card_number = (cardInput.card_number || "").replace(/\D/g, "");
        payload.card_pin = (cardInput.card_pin || "").trim();
      }

      const order = await apiClient.createOrder(accessToken, payload);
      setCardInput({ card_number: "", card_pin: "" });
      const message =
        paymentMethod === "card"
          ? `Order #ES-${String(order.id).padStart(5, "0")} paid successfully by card.`
          : `Order #ES-${String(order.id).padStart(5, "0")} placed successfully with Cash on Delivery.`;
      navigate("/customer/orders", {
        replace: true,
        state: {
          paymentNotice: message,
        },
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="elite-checkout-page">
      <div className="elite-checkout-main">
        <section className="elite-checkout-progress">
          <div className="step active">
            <span>1</span>
            <p>Shipping</p>
          </div>
          <div className="line" />
          <div className="step active">
            <span>2</span>
            <p>Method</p>
          </div>
          <div className="line" />
          <div className="step active">
            <span>3</span>
            <p>Payment</p>
          </div>
        </section>

        {loading && <p className="elite-muted">Loading checkout details...</p>}
        {error && <p className="elite-error">{error}</p>}
        {notice && <p className="elite-notice">{notice}</p>}

        <section className="elite-checkout-card">
          <div className="elite-checkout-card-head">
            <h3>Shipping Address</h3>
            <span>Saved Addresses</span>
          </div>

          <div className="elite-checkout-address-list">
            {addresses.map((address) => (
              <label className="elite-checkout-address-item" key={address.id}>
                <input
                  checked={shippingAddressId === String(address.id)}
                  onChange={() => setShippingAddressId(String(address.id))}
                  type="radio"
                />
                <span>
                  {address.full_name} | {address.address_line_1}, {address.city}, {address.state} {address.postal_code}
                </span>
              </label>
            ))}
            {!loading && addresses.length === 0 && <p className="elite-muted">No saved addresses. Add one below.</p>}
          </div>

          <form className="elite-checkout-address-form" onSubmit={createAddress}>
            <input
              onChange={(event) => setAddressForm((old) => ({ ...old, full_name: event.target.value }))}
              placeholder="Full Name"
              required
              value={addressForm.full_name}
            />
            <input
              onChange={(event) => setAddressForm((old) => ({ ...old, phone: event.target.value }))}
              placeholder="Phone Number"
              required
              value={addressForm.phone}
            />
            <input
              className="full"
              onChange={(event) => setAddressForm((old) => ({ ...old, address_line_1: event.target.value }))}
              placeholder="Address Line 1"
              required
              value={addressForm.address_line_1}
            />
            <input
              onChange={(event) => setAddressForm((old) => ({ ...old, city: event.target.value }))}
              placeholder="City"
              required
              value={addressForm.city}
            />
            <input
              onChange={(event) => setAddressForm((old) => ({ ...old, state: event.target.value }))}
              placeholder="State"
              required
              value={addressForm.state}
            />
            <input
              onChange={(event) => setAddressForm((old) => ({ ...old, postal_code: event.target.value }))}
              placeholder="ZIP Code"
              required
              value={addressForm.postal_code}
            />
            <label className="full elite-checkout-checkbox">
              <input
                checked={addressForm.is_default}
                onChange={(event) => setAddressForm((old) => ({ ...old, is_default: event.target.checked }))}
                type="checkbox"
              />
              Save as default shipping address
            </label>
            <button className="elite-checkout-save-address" type="submit">
              Save Address
            </button>
          </form>
        </section>

        <section className="elite-checkout-card">
          <div className="elite-checkout-card-head">
            <h3>Shipping Method</h3>
          </div>
          <div className="elite-checkout-shipping-grid">
            {SHIPPING_METHODS.map((method) => (
              <button
                className={`elite-shipping-option${shippingMethod === method.id ? " active" : ""}`}
                key={method.id}
                onClick={() => setShippingMethod(method.id)}
                type="button"
              >
                <div>
                  <strong>{method.label}</strong>
                  <span>{method.note}</span>
                </div>
                <b>{method.fee === 0 ? "FREE" : formatCurrency(method.fee)}</b>
              </button>
            ))}
          </div>
        </section>

        <section className="elite-checkout-card">
          <div className="elite-checkout-card-head">
            <h3>Payment Information</h3>
          </div>

          <div className="elite-payment-tabs">
            <button
              className={paymentMethod === "card" ? "active" : ""}
              onClick={() => setPaymentMethod("card")}
              type="button"
            >
              Card
            </button>
            <button className={paymentMethod === "cod" ? "active" : ""} onClick={() => setPaymentMethod("cod")} type="button">
              COD
            </button>
          </div>

          {paymentMethod === "card" ? (
            <div className="elite-payment-form">
              {savedCard?.has_card ? (
                <p className="elite-muted">
                  Saved card: {savedCard.cardholder_name} | **** **** **** {savedCard.card_last4}
                </p>
              ) : (
                <p className="elite-error">No saved card found. Save card in Profile page first.</p>
              )}

              <input
                inputMode="numeric"
                onChange={(event) => setCardInput((old) => ({ ...old, card_number: event.target.value }))}
                placeholder="Card Number"
                value={cardInput.card_number}
              />
              <input
                inputMode="numeric"
                maxLength={4}
                onChange={(event) => setCardInput((old) => ({ ...old, card_pin: event.target.value }))}
                placeholder="PIN"
                type="password"
                value={cardInput.card_pin}
              />
            </div>
          ) : (
            <p className="elite-muted">Cash on Delivery selected. Pay when the package arrives.</p>
          )}
        </section>
      </div>

      <aside className="elite-checkout-summary">
        <h3>Order Summary</h3>

        <div className="elite-checkout-summary-items">
          {items.map((item) => {
            const unit = item.product.discount_price || item.product.price;
            return (
              <article key={item.id}>
                <div>
                  <strong>{item.product.name}</strong>
                  <p>
                    Qty: {item.quantity} | Unit: {formatCurrency(unit)}
                  </p>
                </div>
                <b>{formatCurrency(unit * item.quantity)}</b>
              </article>
            );
          })}
          {!loading && items.length === 0 && <p className="elite-muted">No items in cart.</p>}
        </div>

        <div className="elite-checkout-promo">
          <input onChange={(event) => setPromoCode(event.target.value)} placeholder="Promo Code" value={promoCode} />
          <button onClick={() => setNotice(promoCode ? "Promo code placeholder applied." : "Enter a promo code first.")} type="button">
            Apply
          </button>
        </div>

        <div className="elite-checkout-summary-lines">
          <p>
            <span>Subtotal</span>
            <b>{formatCurrency(subtotal)}</b>
          </p>
          <p>
            <span>Shipping</span>
            <b>{shippingFee === 0 ? "Free" : formatCurrency(shippingFee)}</b>
          </p>
          <p>
            <span>Estimated Tax</span>
            <b>{formatCurrency(estimatedTax)}</b>
          </p>
          <p className="total">
            <span>Total Payable</span>
            <b>{formatCurrency(totalPayable)}</b>
          </p>
        </div>

        <button className="elite-checkout-place-order" disabled={submitting || items.length === 0} onClick={placeOrder} type="button">
          {submitting ? "Processing..." : "Place Order"}
        </button>

        <div className="elite-checkout-summary-links">
          <Link to="/customer/cart">Back to Cart</Link>
          <Link to="/customer/profile">Manage Profile</Link>
          <Link to="/customer/orders">View Orders</Link>
        </div>
      </aside>
    </div>
  );
}
