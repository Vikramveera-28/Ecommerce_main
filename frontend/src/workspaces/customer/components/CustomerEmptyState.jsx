import { Link } from "react-router-dom";

const ICONS = {
  cart: (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M3 4h2l2.2 10.2a2 2 0 0 0 2 1.6h7.9a2 2 0 0 0 2-1.7l1.2-6.6H7.2" />
      <circle cx="10" cy="19" r="1.4" />
      <circle cx="17" cy="19" r="1.4" />
    </svg>
  ),
  favorites: (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M12 20s-6.7-4.4-8.9-7.4a5.3 5.3 0 0 1 .8-6.9 5 5 0 0 1 6.8.1L12 7l1.3-1.2a5 5 0 0 1 6.8-.1 5.3 5.3 0 0 1 .8 6.9C18.7 15.6 12 20 12 20z" />
    </svg>
  ),
  orders: (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M4 8.5L12 4l8 4.5v7L12 20l-8-4.5z" />
      <path d="M12 20v-8.2" />
      <path d="M4 8.5l8 4.3 8-4.3" />
    </svg>
  ),
  empty: (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M6 6h12v12H6z" />
      <path d="M9 9h6v6H9z" />
    </svg>
  ),
};

export default function CustomerEmptyState({
  icon = "empty",
  title,
  description,
  actionLabel,
  actionTo,
  onAction,
  className = "",
}) {
  const iconNode = ICONS[icon] || ICONS.empty;

  return (
    <section className={`elite-empty-state${className ? ` ${className}` : ""}`}>
      <div className="elite-empty-state-icon-wrap">
        <span className="elite-empty-state-icon">{iconNode}</span>
      </div>

      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}

      {actionLabel ? (
        actionTo ? (
          <Link className="elite-empty-state-action" to={actionTo}>
            {actionLabel}
          </Link>
        ) : (
          <button className="elite-empty-state-action" onClick={onAction} type="button">
            {actionLabel}
          </button>
        )
      ) : null}
    </section>
  );
}
