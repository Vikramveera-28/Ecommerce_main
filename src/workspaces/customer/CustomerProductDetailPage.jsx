import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiClient } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import EliteProductTile from "./components/EliteProductTile";
import StorefrontFooter from "./components/StorefrontFooter";

const FALLBACK_IMAGE = "https://dummyimage.com/900x1200/e6eaee/1a2336&text=Elite+Sports";
const DEFAULT_WEIGHTS = ["2lb 8oz", "2lb 9oz", "2lb 10oz", "2lb 12oz"];
const HANDLE_OPTIONS = ["Oval", "Round"];

function formatPrice(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

function buildSpecs(product) {
  const width = product?.dim_width ? `${Number(product.dim_width).toFixed(0)}mm` : "40mm";
  const depth = product?.dim_depth ? `${Number(product.dim_depth).toFixed(0)}mm` : "42mm";
  const bladeLength = product?.dim_height ? `${Number(product.dim_height).toFixed(0)}mm` : "555mm";

  return [
    ["Willow Category", product?.category?.name || "Professional Willow"],
    ["Blade Length", bladeLength],
    ["Sweet Spot", "Mid-Low (210mm from toe)"],
    ["Edge Thickness", `${width} - ${depth}`],
    ["Grains", "9 - 14 straight grains"],
  ];
}

export default function CustomerProductDetailPage() {
  const { id } = useParams();
  const { accessToken } = useAuth();
  const [loading, setLoading] = useState(true);
  const [product, setProduct] = useState(null);
  const [relatedProducts, setRelatedProducts] = useState([]);
  const [activeImage, setActiveImage] = useState(FALLBACK_IMAGE);
  const [selectedWeight, setSelectedWeight] = useState(DEFAULT_WEIGHTS[0]);
  const [selectedHandle, setSelectedHandle] = useState(HANDLE_OPTIONS[0]);
  const [activeTab, setActiveTab] = useState("overview");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let alive = true;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const detail = await apiClient.getProduct(id);
        if (!alive) return;

        setProduct(detail);

        const gallery = [detail.thumbnail, ...(detail.images || []).map((item) => item.url)].filter(Boolean);
        setActiveImage(gallery[0] || FALLBACK_IMAGE);

        if (detail.category?.slug) {
          const related = await apiClient.listProducts({
            category: detail.category.slug,
            sort: "rating_desc",
            per_page: 6,
          });
          if (!alive) return;
          setRelatedProducts((related.items || []).filter((row) => row.id !== detail.id).slice(0, 4));
        } else {
          setRelatedProducts([]);
        }
      } catch (err) {
        if (alive) {
          setError(err.message);
          setProduct(null);
        }
      } finally {
        if (alive) setLoading(false);
      }
    };

    load();
    return () => {
      alive = false;
    };
  }, [id]);

  const galleryImages = useMemo(() => {
    if (!product) return [FALLBACK_IMAGE];
    const items = [product.thumbnail, ...(product.images || []).map((item) => item.url)].filter(Boolean);
    return items.length ? items : [FALLBACK_IMAGE];
  }, [product]);

  const specs = useMemo(() => buildSpecs(product), [product]);
  const reviews = product?.recent_reviews || [];

  const addToCart = async () => {
    if (!product) return;
    try {
      await apiClient.addToCart(accessToken, { product_id: product.id, quantity: 1 });
      setNotice(`${product.name} added to cart.`);
    } catch (err) {
      setError(err.message);
    }
  };

  const addToWishlist = async () => {
    if (!product) return;
    try {
      await apiClient.addToWishlist(accessToken, { product_id: product.id });
      setNotice(`${product.name} saved to wishlist.`);
    } catch (err) {
      setError(err.message);
    }
  };

  const addRelatedToCart = async (selectedProduct) => {
    try {
      await apiClient.addToCart(accessToken, { product_id: selectedProduct.id, quantity: 1 });
      setNotice(`${selectedProduct.name} added to cart.`);
    } catch (err) {
      setError(err.message);
    }
  };

  const deliveryDate = useMemo(() => {
    const candidate = new Date();
    candidate.setDate(candidate.getDate() + 3);
    return new Intl.DateTimeFormat("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
    }).format(candidate);
  }, []);

  if (loading) return <p className="elite-muted">Loading product details...</p>;
  if (error) return <p className="elite-error">{error}</p>;
  if (!product) return <p className="elite-muted">Product unavailable.</p>;

  return (
    <div className="elite-page">
      <section className="elite-detail-top">
        <div className="elite-detail-gallery">
          <div className="elite-detail-main-image">
            <p className="elite-detail-badge">Grade 1+ English Willow</p>
            <img alt={product.name} src={activeImage || FALLBACK_IMAGE} />
          </div>
          <div className="elite-thumb-strip">
            {galleryImages.map((image) => (
              <button
                className={`elite-thumb-btn${activeImage === image ? " active" : ""}`}
                key={image}
                onClick={() => setActiveImage(image)}
                type="button"
              >
                <img alt={`${product.name} preview`} src={image} />
              </button>
            ))}
          </div>
        </div>

        <div className="elite-detail-panel">
          <p className="elite-breadcrumb">
            {(product.category?.name || "Equipment").toUpperCase()} / {(product.brand || "Pro-Series").toUpperCase()}
          </p>
          <h1>{product.name}</h1>
          <p className="elite-detail-subtitle">Handcrafted grade one English willow</p>

          <div className="elite-price-row">
            <strong>{formatPrice(product.discount_price || product.price)}</strong>
            <span>VAT included / Free shipping</span>
            <span>
              Rating {Number(product.rating || 0).toFixed(1)} / 5 ({reviews.length} reviews)
            </span>
          </div>

          <div className="elite-option-group">
            <p>Select weight</p>
            <div className="elite-option-row">
              {DEFAULT_WEIGHTS.map((weight) => (
                <button
                  className={`elite-option-btn${selectedWeight === weight ? " active" : ""}`}
                  key={weight}
                  onClick={() => setSelectedWeight(weight)}
                  type="button"
                >
                  {weight}
                </button>
              ))}
            </div>
          </div>

          <div className="elite-option-group">
            <p>Handle shape</p>
            <div className="elite-option-row">
              {HANDLE_OPTIONS.map((shape) => (
                <button
                  className={`elite-option-btn${selectedHandle === shape ? " active" : ""}`}
                  key={shape}
                  onClick={() => setSelectedHandle(shape)}
                  type="button"
                >
                  {shape}
                </button>
              ))}
            </div>
          </div>

          <div className="elite-action-row">
            <button className="elite-primary-action" onClick={addToCart} type="button">
              Add to Cart
            </button>
            <button className="elite-secondary-action" onClick={addToWishlist} type="button">
              Wish
            </button>
          </div>

          {notice && <p className="elite-notice">{notice}</p>}

          <ul className="elite-benefit-list">
            <li>Express delivery: {deliveryDate}</li>
            <li>Lifetime warranty on blade integrity</li>
            <li>Free 30-day professional pre-knocking</li>
          </ul>
        </div>
      </section>

      <section className="elite-detail-tabs">
        <button
          className={activeTab === "overview" ? "active" : ""}
          onClick={() => setActiveTab("overview")}
          type="button"
        >
          Overview
        </button>
        <button
          className={activeTab === "specs" ? "active" : ""}
          onClick={() => setActiveTab("specs")}
          type="button"
        >
          Specifications
        </button>
        <button
          className={activeTab === "reviews" ? "active" : ""}
          onClick={() => setActiveTab("reviews")}
          type="button"
        >
          Reviews ({reviews.length})
        </button>
      </section>

      {(activeTab === "overview" || activeTab === "specs") && (
        <section className="elite-detail-content-grid">
          {activeTab === "overview" && (
            <article className="elite-overview-card">
              <h3>Engineered for the modern power hitter</h3>
              <p>
                {product.description ||
                  "The Pro-Series line is tuned for aggressive stroke play, reduced vibration, and elite match control."}
              </p>
              <ul>
                <li>Ultra-premium handle with reinforced shock absorption.</li>
                <li>Dynamic balance profile for cleaner pickup through the swing.</li>
                <li>Hand-finished pressing for reliable response under pace.</li>
              </ul>
            </article>
          )}

          <article className="elite-spec-card">
            <h3>Technical specs</h3>
            <dl>
              {specs.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </article>
        </section>
      )}

      {activeTab === "reviews" && (
        <section className="elite-review-card">
          <h3>Latest reviews</h3>
          {reviews.length === 0 && <p className="elite-muted">No reviews yet for this product.</p>}
          {reviews.map((review) => (
            <article key={review.id}>
              <p>
                Rating {Number(review.rating || 0).toFixed(1)} / 5
              </p>
              <p>{review.comment || "No comment provided."}</p>
            </article>
          ))}
        </section>
      )}

      <section className="elite-related-head">
        <div>
          <p className="elite-overline">Complete your gear</p>
          <h3>The Essentials</h3>
        </div>
        <Link className="elite-inline-link" to={`/customer/products?category=${product.category?.slug || ""}`}>
          View all accessories
        </Link>
      </section>

      <section className="elite-product-grid">
        {relatedProducts.map((item) => (
          <EliteProductTile key={item.id} onQuickAdd={addRelatedToCart} product={item} />
        ))}
      </section>

      <StorefrontFooter />
    </div>
  );
}
