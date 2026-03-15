from app.extensions import db
from app.models import Category, Product, ProductApprovalStatus, ProductStatus, Role, User, VendorKycStatus, VendorProfile


def _auth_token(client, email, password):
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.get_json()["access_token"]


def test_order_cod_flow(client, app):
    # Register and login customer.
    reg = client.post(
        "/api/v1/auth/register",
        json={"name": "Buyer", "email": "buyer@test.local", "password": "pass12345", "role": "customer"},
    )
    assert reg.status_code == 201
    token = _auth_token(client, "buyer@test.local", "pass12345")

    with app.app_context():
        vendor_user = User(name="Vendor", email="v@test.local", role=Role.VENDOR.value, status="active", password_hash="x")
        db.session.add(vendor_user)
        db.session.flush()

        vendor = VendorProfile(
            user_id=vendor_user.id,
            store_name="Vendor",
            store_slug="vendor",
            kyc_status=VendorKycStatus.APPROVED.value,
        )
        db.session.add(vendor)

        category = Category(name="Beauty", slug="beauty", status=ProductStatus.ACTIVE.value)
        db.session.add(category)
        db.session.flush()

        product = Product(
            vendor_id=vendor.id,
            category_id=category.id,
            name="Test Product",
            sku="TEST-SKU",
            price=15.0,
            stock_quantity=10,
            status=ProductStatus.ACTIVE.value,
            approval_status=ProductApprovalStatus.APPROVED.value,
        )
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    addr = client.post(
        "/api/v1/addresses",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "full_name": "Buyer",
            "phone": "1234567890",
            "address_line_1": "Street 1",
            "city": "Mumbai",
            "state": "MH",
            "postal_code": "400001",
            "country": "India",
            "is_default": True,
        },
    )
    assert addr.status_code == 201
    address_id = addr.get_json()["id"]

    add_cart = client.post(
        "/api/v1/cart/items",
        headers={"Authorization": f"Bearer {token}"},
        json={"product_id": product_id, "quantity": 2},
    )
    assert add_cart.status_code == 201

    order = client.post(
        "/api/v1/orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"shipping_address_id": address_id, "use_cart": True},
    )
    assert order.status_code == 201
    payload = order.get_json()
    assert payload["payment_status"] == "cod_pending"
    assert payload["order_status"] == "pending"
