"""Tests for Module 6: Billing & Finance."""
from tests.conftest import signup_plain_user


def _setup_patient(client, auth_headers, email="billpat@hms.com", code="MRN-BILL"):
    user = signup_plain_user(client, email)
    return client.post(
        "/api/v1/patients", json={"user_id": user["id"], "patient_code": code, "blood_group": "O+"}, headers=auth_headers
    ).json()


def _login(client, email, password="Plain123!"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# =========================================================================
# INVOICE CREATION
# =========================================================================
def test_create_invoice_computes_total_from_items(client, auth_headers):
    patient = _setup_patient(client, auth_headers)
    resp = client.post(
        "/api/v1/invoices",
        json={
            "patient_id": patient["id"],
            "items": [
                {"item_type": "consultation", "description": "Doctor visit", "quantity": 1, "unit_price": 2000},
                {"item_type": "medicine", "description": "Paracetamol", "quantity": 2, "unit_price": 50},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["total_amount"] == 2100  # 2000 + (2*50)
    assert body["paid_amount"] == 0
    assert body["status"] == "unpaid"


def test_create_invoice_ignores_client_supplied_amount(client, auth_headers):
    """Even if a malicious client sends an 'amount' field, the server recomputes it."""
    patient = _setup_patient(client, auth_headers, email="tamper@hms.com", code="MRN-TAMPER")
    resp = client.post(
        "/api/v1/invoices",
        json={
            "patient_id": patient["id"],
            "items": [{"item_type": "lab", "description": "Blood test", "quantity": 1, "unit_price": 500, "amount": 1}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["total_amount"] == 500  # NOT the tampered "amount": 1
    assert resp.json()["items"][0]["amount"] == 500


def test_create_invoice_with_no_items_rejected(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="noitems@hms.com", code="MRN-NOITEMS")
    resp = client.post("/api/v1/invoices", json={"patient_id": patient["id"], "items": []}, headers=auth_headers)
    assert resp.status_code == 400


def test_invoice_admission_and_appointment_both_rejected(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="both@hms.com", code="MRN-BOTH")
    resp = client.post(
        "/api/v1/invoices",
        json={
            "patient_id": patient["id"], "admission_id": 1, "appointment_id": 1,
            "items": [{"item_type": "other", "description": "x", "quantity": 1, "unit_price": 10}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422  # schema-level validator rejects this


def test_invoice_patient_mismatch_with_admission_rejected(client, auth_headers):
    patient_a = _setup_patient(client, auth_headers, email="mismatch_a@hms.com", code="MRN-MA")
    patient_b = _setup_patient(client, auth_headers, email="mismatch_b@hms.com", code="MRN-MB")

    dept = client.post("/api/v1/departments", json={"name": "Cardiology"}, headers=auth_headers).json()
    ward = client.post(
        "/api/v1/wards", json={"department_id": dept["id"], "name": "W1", "ward_type": "general", "total_capacity": 5},
        headers=auth_headers,
    ).json()
    bed = client.post("/api/v1/beds", json={"bed_number": "A1", "ward_id": ward["id"]}, headers=auth_headers).json()
    client.post(
        "/api/v1/roles/assign", json={"user_id": 1, "role_id": 1}, headers=auth_headers
    )  # no-op safety, ignore result
    admission = client.post(
        "/api/v1/admissions",
        json={"patient_id": patient_a["id"], "bed_id": bed["id"], "admission_date": "2026-01-01T09:00:00"},
        headers=auth_headers,
    ).json()

    resp = client.post(
        "/api/v1/invoices",
        json={
            "patient_id": patient_b["id"], "admission_id": admission["id"],
            "items": [{"item_type": "room", "description": "Room charge", "quantity": 1, "unit_price": 1000}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


# =========================================================================
# INVOICE ITEMS (post-creation)
# =========================================================================
def test_add_item_recomputes_total(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="additem@hms.com", code="MRN-ADD")
    invoice = client.post(
        "/api/v1/invoices",
        json={"patient_id": patient["id"], "items": [{"item_type": "consultation", "description": "Visit", "quantity": 1, "unit_price": 1000}]},
        headers=auth_headers,
    ).json()

    resp = client.post(
        f"/api/v1/invoices/{invoice['id']}/items",
        json={"item_type": "lab", "description": "X-Ray", "quantity": 1, "unit_price": 800},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    updated = client.get(f"/api/v1/invoices/{invoice['id']}", headers=auth_headers).json()
    assert updated["total_amount"] == 1800


def test_cannot_add_item_to_paid_invoice(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="paidinv@hms.com", code="MRN-PAID")
    invoice = client.post(
        "/api/v1/invoices",
        json={"patient_id": patient["id"], "items": [{"item_type": "consultation", "description": "Visit", "quantity": 1, "unit_price": 500}]},
        headers=auth_headers,
    ).json()
    client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice["id"], "amount_paid": 500, "payment_method": "cash", "transaction_date": "2026-01-01T10:00:00"},
        headers=auth_headers,
    )

    resp = client.post(
        f"/api/v1/invoices/{invoice['id']}/items",
        json={"item_type": "other", "description": "late add", "quantity": 1, "unit_price": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# =========================================================================
# PAYMENTS
# =========================================================================
def test_partial_payment_sets_status_partially_paid(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="partial@hms.com", code="MRN-PARTIAL")
    invoice = client.post(
        "/api/v1/invoices",
        json={"patient_id": patient["id"], "items": [{"item_type": "consultation", "description": "Visit", "quantity": 1, "unit_price": 1000}]},
        headers=auth_headers,
    ).json()

    resp = client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice["id"], "amount_paid": 400, "payment_method": "cash", "transaction_date": "2026-01-01T10:00:00"},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    updated = client.get(f"/api/v1/invoices/{invoice['id']}", headers=auth_headers).json()
    assert updated["status"] == "partially_paid"
    assert updated["paid_amount"] == 400


def test_full_payment_sets_status_paid(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="full@hms.com", code="MRN-FULL")
    invoice = client.post(
        "/api/v1/invoices",
        json={"patient_id": patient["id"], "items": [{"item_type": "consultation", "description": "Visit", "quantity": 1, "unit_price": 1000}]},
        headers=auth_headers,
    ).json()

    client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice["id"], "amount_paid": 1000, "payment_method": "card", "transaction_date": "2026-01-01T10:00:00"},
        headers=auth_headers,
    )
    updated = client.get(f"/api/v1/invoices/{invoice['id']}", headers=auth_headers).json()
    assert updated["status"] == "paid"


def test_overpayment_rejected(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="over@hms.com", code="MRN-OVER")
    invoice = client.post(
        "/api/v1/invoices",
        json={"patient_id": patient["id"], "items": [{"item_type": "consultation", "description": "Visit", "quantity": 1, "unit_price": 500}]},
        headers=auth_headers,
    ).json()

    resp = client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice["id"], "amount_paid": 999, "payment_method": "cash", "transaction_date": "2026-01-01T10:00:00"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_payment_after_fully_paid_rejected(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="afterpaid@hms.com", code="MRN-AP")
    invoice = client.post(
        "/api/v1/invoices",
        json={"patient_id": patient["id"], "items": [{"item_type": "consultation", "description": "Visit", "quantity": 1, "unit_price": 300}]},
        headers=auth_headers,
    ).json()
    client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice["id"], "amount_paid": 300, "payment_method": "cash", "transaction_date": "2026-01-01T10:00:00"},
        headers=auth_headers,
    )
    resp = client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice["id"], "amount_paid": 1, "payment_method": "cash", "transaction_date": "2026-01-01T11:00:00"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_multiple_partial_payments_accumulate(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="multi_pay@hms.com", code="MRN-MULTI")
    invoice = client.post(
        "/api/v1/invoices",
        json={"patient_id": patient["id"], "items": [{"item_type": "consultation", "description": "Visit", "quantity": 1, "unit_price": 1000}]},
        headers=auth_headers,
    ).json()

    client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice["id"], "amount_paid": 300, "payment_method": "cash", "transaction_date": "2026-01-01T10:00:00"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/payments",
        json={"invoice_id": invoice["id"], "amount_paid": 700, "payment_method": "card", "transaction_date": "2026-01-02T10:00:00"},
        headers=auth_headers,
    )
    updated = client.get(f"/api/v1/invoices/{invoice['id']}", headers=auth_headers).json()
    assert updated["paid_amount"] == 1000
    assert updated["status"] == "paid"

    payments = client.get(f"/api/v1/invoices/{invoice['id']}/payments", headers=auth_headers).json()
    assert len(payments) == 2


# =========================================================================
# ACCESS SCOPING
# =========================================================================
def test_patient_can_view_own_invoice_but_not_others(client, auth_headers):
    pat_a = _setup_patient(client, auth_headers, email="scope_a@hms.com", code="MRN-SA")
    pat_b_user = signup_plain_user(client, "scope_b@hms.com")
    pat_b = client.post(
        "/api/v1/patients", json={"user_id": pat_b_user["id"], "patient_code": "MRN-SB", "blood_group": "A+"}, headers=auth_headers
    ).json()

    invoice_a = client.post(
        "/api/v1/invoices",
        json={"patient_id": pat_a["id"], "items": [{"item_type": "consultation", "description": "Visit", "quantity": 1, "unit_price": 500}]},
        headers=auth_headers,
    ).json()

    headers_a = _login(client, "scope_a@hms.com")
    own = client.get(f"/api/v1/invoices/{invoice_a['id']}", headers=headers_a)
    assert own.status_code == 200

    headers_b = _login(client, "scope_b@hms.com")
    others = client.get(f"/api/v1/invoices/{invoice_a['id']}", headers=headers_b)
    assert others.status_code == 403


# =========================================================================
# INSURANCE
# =========================================================================
def test_duplicate_insurance_provider_rejected(client, auth_headers):
    client.post("/api/v1/insurance-providers", json={"name": "State Life"}, headers=auth_headers)
    resp = client.post("/api/v1/insurance-providers", json={"name": "State Life"}, headers=auth_headers)
    assert resp.status_code == 400


def test_duplicate_patient_policy_rejected(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="insured@hms.com", code="MRN-INS")
    provider = client.post("/api/v1/insurance-providers", json={"name": "Jubilee Insurance"}, headers=auth_headers).json()

    first = client.post(
        f"/api/v1/patients/{patient['id']}/insurance",
        json={"patient_id": patient["id"], "provider_id": provider["id"], "policy_number": "POL-1"},
        headers=auth_headers,
    )
    assert first.status_code == 201

    dup = client.post(
        f"/api/v1/patients/{patient['id']}/insurance",
        json={"patient_id": patient["id"], "provider_id": provider["id"], "policy_number": "POL-1"},
        headers=auth_headers,
    )
    assert dup.status_code == 400
