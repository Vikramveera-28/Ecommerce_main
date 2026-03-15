import { Link } from "react-router-dom";

const FALLBACK_IMAGE = "https://dummyimage.com/640x640/e6eaee/1a2336&text=Elite+Sports";

function formatPrice(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

export default function EliteProductTile({ product, onQuickAdd }) {
  if (!product) return null;

  return (
    <article className="elite-product-tile">
      <Link className="elite-product-media-link" to={`/customer/products/${product.id}`}>
        <img
          alt={product.name}
          loading="lazy"
          src={product.thumbnail || FALLBACK_IMAGE}
        />
      </Link>
      <p className="elite-product-tile-meta">{(product.category?.name || "Equipment").toUpperCase()}</p>
      <Link className="elite-product-tile-name" to={`/customer/products/${product.id}`}>
        {product.name}
      </Link>
      <div className="elite-product-tile-footer">
        <span className="elite-product-tile-price">{formatPrice(product.discount_price || product.price)}</span>
        <button
          aria-label={`Add ${product.name} to cart`}
          className="elite-product-plus-btn"
          onClick={() => onQuickAdd?.(product)}
          type="button"
        >
          +
        </button>
      </div>
    </article>
  );
}
