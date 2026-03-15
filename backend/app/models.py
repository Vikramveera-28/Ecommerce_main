from __future__ import annotations

from datetime import datetime
from enum import Enum

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class Role(str, Enum):
    CUSTOMER = "customer"
    VENDOR = "vendor"
    LOGISTICS = "logistics"
    DELIVERY_BOY = "delivery_boy"
    ADMIN = "admin"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    PENDING = "pending"


class VendorKycStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProductStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ProductApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PACKED = "packed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class PaymentStatus(str, Enum):
    COD_PENDING = "cod_pending"
    COD_CONFIRMED = "cod_confirmed"
    PAID = "paid"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    COD = "cod"
    CARD = "card"


class ShipmentStatus(str, Enum):
    PICKUP_REQUESTED = "pickup_requested"
    PICKED = "picked"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED = "failed"


class PayoutStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


class ReturnStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditMixin:
    created_by = db.Column(db.Integer, nullable=True)
    updated_by = db.Column(db.Integer, nullable=True)


class SoftDeleteMixin:
    deleted_at = db.Column(db.DateTime, nullable=True)


class RevokedToken(db.Model):
    __tablename__ = "revoked_tokens"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(255), nullable=False, unique=True)
    token_type = db.Column(db.String(32), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class User(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    phone = db.Column(db.String(32), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=Role.CUSTOMER.value)
    status = db.Column(db.String(20), nullable=False, default=AccountStatus.PENDING.value)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)

    customer_profile = db.relationship("CustomerProfile", back_populates="user", uselist=False)
    vendor_profile = db.relationship("VendorProfile", back_populates="user", uselist=False)
    logistics_profile = db.relationship("LogisticsProfile", back_populates="user", uselist=False)
    delivery_profile = db.relationship("DeliveryProfile", back_populates="user", uselist=False)

    addresses = db.relationship("Address", back_populates="user", lazy="dynamic")

    def set_password(self, plain_password: str) -> None:
        self.password_hash = generate_password_hash(plain_password)

    def check_password(self, plain_password: str) -> bool:
        return check_password_hash(self.password_hash, plain_password)


class CustomerProfile(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "customer_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    default_address_id = db.Column(db.Integer, db.ForeignKey("addresses.id"), nullable=True)

    user = db.relationship("User", back_populates="customer_profile")


class CustomerPaymentCard(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "customer_payment_cards"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    cardholder_name = db.Column(db.String(120), nullable=False)
    card_last4 = db.Column(db.String(4), nullable=False)
    card_number_hash = db.Column(db.String(255), nullable=False)
    card_pin_hash = db.Column(db.String(255), nullable=False)

    def set_card_number(self, card_number: str) -> None:
        self.card_number_hash = generate_password_hash(card_number)

    def check_card_number(self, card_number: str) -> bool:
        return check_password_hash(self.card_number_hash, card_number)

    def set_card_pin(self, card_pin: str) -> None:
        self.card_pin_hash = generate_password_hash(card_pin)

    def check_card_pin(self, card_pin: str) -> bool:
        return check_password_hash(self.card_pin_hash, card_pin)


class VendorProfile(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "vendor_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    store_name = db.Column(db.String(255), nullable=False)
    store_slug = db.Column(db.String(255), nullable=False, unique=True)
    store_description = db.Column(db.Text, nullable=True)
    gst_number = db.Column(db.String(64), nullable=True)
    kyc_status = db.Column(db.String(20), nullable=False, default=VendorKycStatus.PENDING.value)
    bank_account_number = db.Column(db.String(64), nullable=True)
    ifsc_code = db.Column(db.String(32), nullable=True)
    total_rating = db.Column(db.Float, nullable=False, default=0.0)

    user = db.relationship("User", back_populates="vendor_profile")
    products = db.relationship("Product", back_populates="vendor", lazy="dynamic")


class LogisticsProfile(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "logistics_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    vehicle_number = db.Column(db.String(64), nullable=True)
    service_area = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=AccountStatus.ACTIVE.value)

    user = db.relationship("User", back_populates="logistics_profile")


class DeliveryProfile(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "delivery_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    phone = db.Column(db.String(32), nullable=True)
    vehicle_type = db.Column(db.String(64), nullable=True)
    license_number = db.Column(db.String(64), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    user = db.relationship("User", back_populates="delivery_profile")


class Address(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(32), nullable=False)
    address_line_1 = db.Column(db.String(255), nullable=False)
    address_line_2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(120), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(120), nullable=False, default="India")
    is_default = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", back_populates="addresses")


class Category(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), nullable=False, unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    image_url = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=ProductStatus.ACTIVE.value)

    parent = db.relationship("Category", remote_side=[id], backref="children")


class Product(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    legacy_product_id = db.Column(db.Integer, nullable=True, unique=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor_profiles.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    discount_price = db.Column(db.Float, nullable=True)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    sku = db.Column(db.String(120), nullable=False, unique=True)
    status = db.Column(db.String(20), nullable=False, default=ProductStatus.ACTIVE.value)
    approval_status = db.Column(db.String(20), nullable=False, default=ProductApprovalStatus.PENDING.value)
    rating = db.Column(db.Float, nullable=False, default=0.0)
    brand = db.Column(db.String(255), nullable=True)
    weight = db.Column(db.Float, nullable=True)
    dim_width = db.Column(db.Float, nullable=True)
    dim_height = db.Column(db.Float, nullable=True)
    dim_depth = db.Column(db.Float, nullable=True)
    warranty_information = db.Column(db.Text, nullable=True)
    shipping_information = db.Column(db.Text, nullable=True)
    availability_status = db.Column(db.String(50), nullable=True)
    return_policy = db.Column(db.Text, nullable=True)
    minimum_order_quantity = db.Column(db.Integer, nullable=True)
    barcode = db.Column(db.String(255), nullable=True)
    qr_code = db.Column(db.Text, nullable=True)
    thumbnail = db.Column(db.Text, nullable=True)

    vendor = db.relationship("VendorProfile", back_populates="products")
    category = db.relationship("Category")
    images = db.relationship("ProductImage", back_populates="product", lazy="dynamic", cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="product", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (
        db.Index("idx_products_category_status", "category_id", "status"),
        db.Index("idx_products_vendor", "vendor_id"),
    )


class ProductImage(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    image_url = db.Column(db.Text, nullable=False)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)

    product = db.relationship("Product", back_populates="images")


class Tag(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)


class ProductTagMap(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "product_tags_map"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey("tags.id"), nullable=False)

    __table_args__ = (db.UniqueConstraint("product_id", "tag_id", name="uq_product_tag"),)


class Review(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text, nullable=True)

    product = db.relationship("Product", back_populates="reviews")

    __table_args__ = (db.Index("idx_reviews_product_created", "product_id", "created_at"),)


class CartItem(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    __table_args__ = (db.UniqueConstraint("customer_id", "product_id", name="uq_cart_customer_product"),)


class WishlistItem(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "wishlist_items"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    __table_args__ = (db.UniqueConstraint("customer_id", "product_id", name="uq_wishlist_customer_product"),)


class Order(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(32), nullable=False, default=PaymentStatus.COD_PENDING.value)
    order_status = db.Column(db.String(32), nullable=False, default=OrderStatus.PENDING.value)
    shipping_address_id = db.Column(db.Integer, db.ForeignKey("addresses.id"), nullable=False)

    items = db.relationship("OrderItem", back_populates="order", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (db.Index("idx_orders_customer_created", "customer_id", "created_at"),)


class OrderItem(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor_profiles.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

    order = db.relationship("Order", back_populates="items")

    __table_args__ = (db.Index("idx_order_items_order", "order_id"),)


class Payment(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    payment_method = db.Column(db.String(20), nullable=False, default=PaymentMethod.COD.value)
    transaction_id = db.Column(db.String(128), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(32), nullable=False, default=PaymentStatus.COD_PENDING.value)


class Shipment(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "shipments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    logistics_id = db.Column(db.Integer, db.ForeignKey("logistics_profiles.id"), nullable=True)
    assigned_delivery_boy_id = db.Column(db.Integer, db.ForeignKey("delivery_profiles.id"), nullable=True)
    assigned_by_logistics_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_time = db.Column(db.DateTime, nullable=True)
    pickup_time = db.Column(db.DateTime, nullable=True)
    delivery_time = db.Column(db.DateTime, nullable=True)
    tracking_number = db.Column(db.String(120), nullable=True, unique=True)
    shipment_status = db.Column(db.String(32), nullable=False, default=ShipmentStatus.PICKUP_REQUESTED.value)
    otp_code = db.Column(db.String(6), nullable=True)
    delivery_attempts = db.Column(db.Integer, nullable=False, default=0)
    proof_of_delivery_url = db.Column(db.Text, nullable=True)
    failure_reason = db.Column(db.Text, nullable=True)

    order = db.relationship("Order", backref=db.backref("shipments", lazy="dynamic"))
    assigned_delivery_boy = db.relationship("DeliveryProfile", foreign_keys=[assigned_delivery_boy_id])
    assigned_by_logistics_user = db.relationship("User", foreign_keys=[assigned_by_logistics_id])


class ReturnRequest(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "return_requests"

    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_items.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=ReturnStatus.REQUESTED.value)


class Commission(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "commissions"

    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_items.id"), nullable=False, unique=True)
    vendor_amount = db.Column(db.Float, nullable=False)
    platform_commission = db.Column(db.Float, nullable=False)
    commission_percentage = db.Column(db.Float, nullable=False)


class Coupon(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "coupons"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), nullable=False, unique=True)
    discount_percentage = db.Column(db.Float, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_to = db.Column(db.DateTime, nullable=True)


class VendorPayout(TimestampMixin, AuditMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "vendor_payouts"

    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor_profiles.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=PayoutStatus.PENDING.value)
    scheduled_at = db.Column(db.DateTime, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)


class StagingProduct(db.Model):
    __tablename__ = "stg_products"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, nullable=False, unique=True)
    title = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(255), nullable=True)
    price = db.Column(db.Float, nullable=True)
    discount_percentage = db.Column(db.Float, nullable=True)
    rating = db.Column(db.Float, nullable=True)
    stock = db.Column(db.Integer, nullable=True)
    brand = db.Column(db.String(255), nullable=True)
    sku = db.Column(db.String(255), nullable=True)
    weight = db.Column(db.Float, nullable=True)
    dim_width = db.Column(db.Float, nullable=True)
    dim_height = db.Column(db.Float, nullable=True)
    dim_depth = db.Column(db.Float, nullable=True)
    warranty_information = db.Column(db.Text, nullable=True)
    shipping_information = db.Column(db.Text, nullable=True)
    availability_status = db.Column(db.String(50), nullable=True)
    return_policy = db.Column(db.Text, nullable=True)
    minimum_order_quantity = db.Column(db.Integer, nullable=True)
    meta_created_at = db.Column(db.String(50), nullable=True)
    meta_updated_at = db.Column(db.String(50), nullable=True)
    barcode = db.Column(db.String(255), nullable=True)
    qr_code = db.Column(db.Text, nullable=True)
    thumbnail = db.Column(db.Text, nullable=True)


class StagingProductImage(db.Model):
    __tablename__ = "stg_product_images"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, nullable=False, unique=True)
    product_id = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.Text, nullable=False)


class StagingProductTag(db.Model):
    __tablename__ = "stg_product_tags"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, nullable=False, unique=True)
    product_id = db.Column(db.Integer, nullable=False)
    tag = db.Column(db.String(255), nullable=False)


class StagingProductReview(db.Model):
    __tablename__ = "stg_product_reviews"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, nullable=False, unique=True)
    product_id = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Float, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    review_date = db.Column(db.String(50), nullable=True)
    reviewer_name = db.Column(db.String(255), nullable=True)
    reviewer_email = db.Column(db.String(255), nullable=True)
