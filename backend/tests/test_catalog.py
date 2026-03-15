from app.extensions import db
from app.models import Category, Product, ProductApprovalStatus, ProductStatus, User, VendorKycStatus, VendorProfile


def _seed_product():
    vendor_user = User(name="Vendor User", email="vendor@test.local", role="vendor", status="active", password_hash="x")
    db.session.add(vendor_user)
    db.session.flush()

    vendor = VendorProfile(user_id=vendor_user.id, store_name="Vendor A", store_slug="vendor-a", kyc_status=VendorKycStatus.APPROVED.value)
    db.session.add(vendor)

    category = Category(name="Beauty", slug="beauty", status=ProductStatus.ACTIVE.value)
    db.session.add(category)
    db.session.flush()

    product = Product(
        vendor_id=vendor.id,
        category_id=category.id,
        name="Lipstick",
        sku="SKU-1",
        price=10,
        stock_quantity=30,
        status=ProductStatus.ACTIVE.value,
        approval_status=ProductApprovalStatus.APPROVED.value,
        rating=4.5,
    )
    db.session.add(product)
    db.session.commit()


def test_list_products(client, app):
    with app.app_context():
        _seed_product()

    response = client.get("/api/v1/products")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["pagination"]["total"] >= 1
    assert payload["items"][0]["name"]
