import { useEffect, useMemo, useState } from "react";

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

const initialCard = {
  cardholder_name: "",
  card_number: "",
  card_pin: "",
};

export default function CustomerProfilePage() {
  const { accessToken, user } = useAuth();
  const [addresses, setAddresses] = useState([]);
  const [orders, setOrders] = useState([]);
  const [addressForm, setAddressForm] = useState(initialAddress);
  const [cardForm, setCardForm] = useState(initialCard);
  const [savedCard, setSavedCard] = useState({ has_card: false, cardholder_name: null, card_last4: null, updated_at: null });
  const [loading, setLoading] = useState(true);
  const [savingCard, setSavingCard] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [addressRes, orderRes, cardRes] = await Promise.allSettled([
        apiClient.listAddresses(accessToken),
        apiClient.listOrders(accessToken),
        apiClient.getPaymentCard(accessToken),
      ]);

      const nextAddresses = addressRes.status === "fulfilled" ? addressRes.value || [] : [];
      const nextOrders = orderRes.status === "fulfilled" ? orderRes.value || [] : [];
      const nextCard =
        cardRes.status === "fulfilled"
          ? cardRes.value || { has_card: false, cardholder_name: null, card_last4: null, updated_at: null }
          : { has_card: false, cardholder_name: null, card_last4: null, updated_at: null };

      setAddresses(nextAddresses);
      setOrders(nextOrders);
      setSavedCard(nextCard);
      if (nextCard?.has_card) {
        setCardForm((old) => ({ ...old, cardholder_name: nextCard.cardholder_name || "" }));
      }

      if (addressRes.status === "rejected") {
        setError(addressRes.reason?.message || "Failed to load addresses.");
      } else if (orderRes.status === "rejected") {
        setError(orderRes.reason?.message || "Failed to load orders.");
      } else if (cardRes.status === "rejected") {
        setNotice("Saved card service is temporarily unavailable. Address data loaded.");
      }
    } catch (err) {
      setError(err.message);
      setAddresses([]);
      setOrders([]);
      setSavedCard({ has_card: false, cardholder_name: null, card_last4: null, updated_at: null });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const orderStats = useMemo(() => {
    const delivered = orders.filter((order) => order.order_status === "delivered").length;
    const active = orders.filter((order) => !["delivered", "cancelled"].includes(order.order_status)).length;
    const firstOrder = orders.length
      ? new Date(
          orders.reduce((earliest, row) => (new Date(row.created_at) < new Date(earliest.created_at) ? row : earliest), orders[0])
            .created_at
        )
      : null;

    return {
      total: orders.length,
      delivered,
      active,
      memberSince: firstOrder
        ? new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric" }).format(firstOrder).toUpperCase()
        : "NEW",
    };
  }, [orders]);

  const avatarUrl = useMemo(() => {
    const seed = encodeURIComponent(user?.email || user?.name || "elite-user");
    return `https://i.pravatar.cc/180?u=${seed}`;
  }, [user?.email, user?.name]);

  const createAddress = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const created = await apiClient.createAddress(accessToken, addressForm);
      setAddresses((old) => [created, ...old]);
      setAddressForm(initialAddress);
      setNotice("Address saved successfully.");
    } catch (err) {
      setError(err.message);
    }
  };

  const saveCard = async (event) => {
    event.preventDefault();
    const cardNumber = (cardForm.card_number || "").replace(/\D/g, "");
    const cardPin = (cardForm.card_pin || "").trim();

    if (!cardForm.cardholder_name.trim()) {
      setError("Cardholder name is required.");
      return;
    }
    if (cardNumber.length < 12 || cardNumber.length > 19) {
      setError("Card number must be 12 to 19 digits.");
      return;
    }
    if (!/^\d{4}$/.test(cardPin)) {
      setError("Card PIN must be exactly 4 digits.");
      return;
    }

    setSavingCard(true);
    setError("");
    setNotice("");
    try {
      const saved = await apiClient.savePaymentCard(accessToken, {
        cardholder_name: cardForm.cardholder_name.trim(),
        card_number: cardNumber,
        card_pin: cardPin,
      });
      setSavedCard(saved);
      setCardForm({ cardholder_name: saved.cardholder_name || "", card_number: "", card_pin: "" });
      setNotice(`Card saved successfully. Ending in ${saved.card_last4}.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingCard(false);
    }
  };

  const onAddressAction = (action) => {
    setNotice(`${action} action can be wired to API endpoints in the next step.`);
  };

  return (
    <div className="elite-account-content elite-profile-main">
        <section className="elite-profile-summary">
          <div className="elite-profile-user-block">
            <div className="elite-profile-avatar">
              <img alt={user?.name || "Profile"} src={avatarUrl} />
            </div>
            <div>
              <h2>{user?.name || "Customer"}</h2>
              <p>{user?.email || "No email available"}</p>
              <div className="elite-profile-badges">
                <span>{orders.length >= 4 ? "Premium Member" : "Active Member"}</span>
                <span>Since {orderStats.memberSince}</span>
              </div>
            </div>
          </div>

          <button className="elite-profile-edit-btn" onClick={() => onAddressAction("Edit profile")} type="button">
            Edit Profile
          </button>
        </section>

        <section className="elite-profile-stats">
          <article>
            <p>Total Orders</p>
            <h3>{String(orderStats.total).padStart(2, "0")}</h3>
          </article>
          <article>
            <p>Active Orders</p>
            <h3>{String(orderStats.active).padStart(2, "0")}</h3>
          </article>
          <article>
            <p>Delivered</p>
            <h3>{String(orderStats.delivered).padStart(2, "0")}</h3>
          </article>
        </section>

        <section className="elite-address-form-card">
          <h3>Saved Card Details</h3>
          {savedCard?.has_card ? (
            <p className="elite-muted">
              Stored card: {savedCard.cardholder_name} | **** **** **** {savedCard.card_last4}
            </p>
          ) : (
            <p className="elite-muted">No card saved yet. Add one for card payments at checkout.</p>
          )}

          <form className="elite-address-form" onSubmit={saveCard}>
            <label>
              Cardholder Name
              <input
                onChange={(event) => setCardForm((old) => ({ ...old, cardholder_name: event.target.value }))}
                placeholder="e.g. John Doe"
                required
                value={cardForm.cardholder_name}
              />
            </label>

            <label>
              Card Number
              <input
                inputMode="numeric"
                onChange={(event) => setCardForm((old) => ({ ...old, card_number: event.target.value }))}
                placeholder="0000 0000 0000 0000"
                required
                value={cardForm.card_number}
              />
            </label>

            <label>
              Card PIN
              <input
                inputMode="numeric"
                maxLength={4}
                onChange={(event) => setCardForm((old) => ({ ...old, card_pin: event.target.value }))}
                placeholder="4 digit PIN"
                required
                type="password"
                value={cardForm.card_pin}
              />
            </label>

            <div className="elite-address-form-actions full">
              <button className="elite-profile-primary-btn" disabled={savingCard} type="submit">
                {savingCard ? "Saving..." : savedCard?.has_card ? "Update Card" : "Save Card"}
              </button>
              <button className="elite-profile-secondary-btn" onClick={() => setCardForm(initialCard)} type="button">
                Clear
              </button>
            </div>
          </form>
        </section>

        <section className="elite-address-section" id="saved-addresses">
          <div className="elite-section-header">
            <h3>Saved Addresses</h3>
            <a href="#address-form">Manage All</a>
          </div>

          {loading && <p className="elite-muted">Loading profile data...</p>}
          {error && <p className="elite-error">{error}</p>}
          {notice && <p className="elite-notice">{notice}</p>}
          {!loading && addresses.length === 0 && <p className="elite-muted">No addresses found yet.</p>}

          <div className="elite-address-grid">
            {addresses.map((address) => (
              <article className={`elite-address-card${address.is_default ? " default" : ""}`} key={address.id}>
                <div className="elite-address-card-head">
                  <h4>{address.address_line_2 || "Home"}</h4>
                  {address.is_default && <span>Default</span>}
                </div>
                <p>{address.full_name}</p>
                <p>{address.address_line_1}</p>
                <p>
                  {address.city}, {address.state} - {address.postal_code}
                </p>
                <p>{address.country}</p>
                <div className="elite-address-card-actions">
                  <button onClick={() => onAddressAction("Edit")} type="button">
                    Edit
                  </button>
                  <button onClick={() => onAddressAction("Remove")} type="button">
                    Remove
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="elite-address-form-card" id="address-form">
          <h3>Add New Address</h3>
          <form className="elite-address-form" onSubmit={createAddress}>
            <label>
              Address Label
              <input
                onChange={(event) => setAddressForm((old) => ({ ...old, address_line_2: event.target.value }))}
                placeholder="e.g. Home / Office"
                value={addressForm.address_line_2}
              />
            </label>

            <label>
              Receiver Name
              <input
                onChange={(event) => setAddressForm((old) => ({ ...old, full_name: event.target.value }))}
                required
                value={addressForm.full_name}
              />
            </label>

            <label className="full">
              Full Address
              <textarea
                onChange={(event) => setAddressForm((old) => ({ ...old, address_line_1: event.target.value }))}
                placeholder="Street name, building number, area"
                required
                rows={3}
                value={addressForm.address_line_1}
              />
            </label>

            <label>
              City
              <input
                onChange={(event) => setAddressForm((old) => ({ ...old, city: event.target.value }))}
                placeholder="e.g. Bangalore"
                required
                value={addressForm.city}
              />
            </label>

            <label>
              State
              <input
                onChange={(event) => setAddressForm((old) => ({ ...old, state: event.target.value }))}
                placeholder="e.g. Karnataka"
                required
                value={addressForm.state}
              />
            </label>

            <label>
              Phone
              <input
                onChange={(event) => setAddressForm((old) => ({ ...old, phone: event.target.value }))}
                placeholder="e.g. +91 9876543210"
                required
                value={addressForm.phone}
              />
            </label>

            <label>
              Zip Code
              <input
                onChange={(event) => setAddressForm((old) => ({ ...old, postal_code: event.target.value }))}
                placeholder="e.g. 560100"
                required
                value={addressForm.postal_code}
              />
            </label>

            <label>
              Country
              <input
                onChange={(event) => setAddressForm((old) => ({ ...old, country: event.target.value }))}
                value={addressForm.country}
              />
            </label>

            <label className="elite-address-default-toggle full">
              <input
                checked={addressForm.is_default}
                onChange={(event) => setAddressForm((old) => ({ ...old, is_default: event.target.checked }))}
                type="checkbox"
              />
              Set as default delivery address
            </label>

            <div className="elite-address-form-actions full">
              <button className="elite-profile-primary-btn" type="submit">
                Save Address
              </button>
              <button className="elite-profile-secondary-btn" onClick={() => setAddressForm(initialAddress)} type="button">
                Discard
              </button>
            </div>
          </form>
        </section>
    </div>
  );
}
