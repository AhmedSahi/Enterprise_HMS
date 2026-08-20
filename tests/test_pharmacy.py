"""Tests for Module 5: Pharmacy & Inventory."""
from datetime import date, timedelta


def test_create_medication(client, auth_headers):
    resp = client.post(
        "/api/v1/medications",
        json={"name": "Paracetamol", "dosage_form": "tablet", "strength": "500mg", "unit_price": 2.5},
        headers=auth_headers,
    )
    assert resp.status_code == 201


def test_add_batch_with_past_expiry_rejected(client, auth_headers):
    med = client.post(
        "/api/v1/medications",
        json={"name": "Amoxicillin", "dosage_form": "capsule", "strength": "250mg", "unit_price": 5},
        headers=auth_headers,
    ).json()
    past_date = (date.today() - timedelta(days=1)).isoformat()
    resp = client.post(
        f"/api/v1/medications/{med['id']}/batches",
        json={"medication_id": med["id"], "batch_number": "B1", "expiry_date": past_date, "quantity_available": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_add_batch_with_future_expiry_succeeds(client, auth_headers):
    med = client.post(
        "/api/v1/medications",
        json={"name": "Ibuprofen", "dosage_form": "tablet", "strength": "200mg", "unit_price": 3},
        headers=auth_headers,
    ).json()
    future_date = (date.today() + timedelta(days=180)).isoformat()
    resp = client.post(
        f"/api/v1/medications/{med['id']}/batches",
        json={"medication_id": med["id"], "batch_number": "B1", "expiry_date": future_date, "quantity_available": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 201


def test_duplicate_batch_number_for_same_medication_rejected(client, auth_headers):
    med = client.post(
        "/api/v1/medications",
        json={"name": "Cetirizine", "dosage_form": "tablet", "strength": "10mg", "unit_price": 1.5},
        headers=auth_headers,
    ).json()
    future_date = (date.today() + timedelta(days=90)).isoformat()
    client.post(
        f"/api/v1/medications/{med['id']}/batches",
        json={"medication_id": med["id"], "batch_number": "DUPBATCH", "expiry_date": future_date, "quantity_available": 50},
        headers=auth_headers,
    )
    resp = client.post(
        f"/api/v1/medications/{med['id']}/batches",
        json={"medication_id": med["id"], "batch_number": "DUPBATCH", "expiry_date": future_date, "quantity_available": 20},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_list_batches_excludes_expired_by_default(client, auth_headers, session_factory):
    med = client.post(
        "/api/v1/medications",
        json={"name": "Metformin", "dosage_form": "tablet", "strength": "500mg", "unit_price": 4},
        headers=auth_headers,
    ).json()
    future_date = (date.today() + timedelta(days=60)).isoformat()
    client.post(
        f"/api/v1/medications/{med['id']}/batches",
        json={"medication_id": med["id"], "batch_number": "FRESH", "expiry_date": future_date, "quantity_available": 30},
        headers=auth_headers,
    )
    # insert an already-expired batch directly (schema itself blocks creating one via the API)
    from src.models.pharmacy import MedicationBatch
    db = session_factory()
    db.add(MedicationBatch(
        medication_id=med["id"], batch_number="OLD", expiry_date=date.today() - timedelta(days=5), quantity_available=10
    ))
    db.commit()
    db.close()

    default_list = client.get(f"/api/v1/medications/{med['id']}/batches", headers=auth_headers).json()
    assert len(default_list) == 1
    assert default_list[0]["batch_number"] == "FRESH"

    full_list = client.get(f"/api/v1/medications/{med['id']}/batches?include_expired=true", headers=auth_headers).json()
    assert len(full_list) == 2


def test_expiring_soon_endpoint(client, auth_headers):
    med = client.post(
        "/api/v1/medications",
        json={"name": "Aspirin", "dosage_form": "tablet", "strength": "75mg", "unit_price": 1},
        headers=auth_headers,
    ).json()
    soon = (date.today() + timedelta(days=10)).isoformat()
    far = (date.today() + timedelta(days=200)).isoformat()
    client.post(
        f"/api/v1/medications/{med['id']}/batches",
        json={"medication_id": med["id"], "batch_number": "SOON", "expiry_date": soon, "quantity_available": 10},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/medications/{med['id']}/batches",
        json={"medication_id": med["id"], "batch_number": "FAR", "expiry_date": far, "quantity_available": 10},
        headers=auth_headers,
    )
    resp = client.get("/api/v1/medication-batches/expiring?days=30", headers=auth_headers)
    codes = [b["batch_number"] for b in resp.json()]
    assert "SOON" in codes
    assert "FAR" not in codes


def test_delete_medication_with_stock_blocked(client, auth_headers):
    med = client.post(
        "/api/v1/medications",
        json={"name": "Vitamin C", "dosage_form": "tablet", "strength": "1000mg", "unit_price": 1},
        headers=auth_headers,
    ).json()
    future_date = (date.today() + timedelta(days=90)).isoformat()
    client.post(
        f"/api/v1/medications/{med['id']}/batches",
        json={"medication_id": med["id"], "batch_number": "B1", "expiry_date": future_date, "quantity_available": 5},
        headers=auth_headers,
    )
    resp = client.delete(f"/api/v1/medications/{med['id']}", headers=auth_headers)
    assert resp.status_code == 400
