"""Tests for Module 2: Staff & Patient Profiles."""
from tests.conftest import signup_plain_user


def test_create_doctor_with_license_succeeds(client, auth_headers):
    user = signup_plain_user(client, "doc@hms.com")
    resp = client.post(
        "/api/v1/staff",
        json={
            "user_id": user["id"], "employee_code": "EMP001", "staff_type": "doctor",
            "specialization": "Cardiologist", "license_number": "PMC-1", "consultation_fee": 2000,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201


def test_create_doctor_without_license_rejected(client, auth_headers):
    user = signup_plain_user(client, "doc2@hms.com")
    resp = client.post(
        "/api/v1/staff",
        json={"user_id": user["id"], "employee_code": "EMP002", "staff_type": "doctor"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_non_doctor_with_consultation_fee_rejected(client, auth_headers):
    user = signup_plain_user(client, "nurse1@hms.com")
    resp = client.post(
        "/api/v1/staff",
        json={"user_id": user["id"], "employee_code": "EMP003", "staff_type": "nurse", "consultation_fee": 500},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_duplicate_employee_code_rejected(client, auth_headers):
    u1 = signup_plain_user(client, "e1@hms.com")
    u2 = signup_plain_user(client, "e2@hms.com")
    client.post("/api/v1/staff", json={"user_id": u1["id"], "employee_code": "DUP1", "staff_type": "nurse"}, headers=auth_headers)
    resp = client.post("/api/v1/staff", json={"user_id": u2["id"], "employee_code": "DUP1", "staff_type": "nurse"}, headers=auth_headers)
    assert resp.status_code == 400


def test_user_cannot_be_both_staff_and_patient(client, auth_headers):
    user = signup_plain_user(client, "dual@hms.com")
    client.post("/api/v1/staff", json={"user_id": user["id"], "employee_code": "DUAL1", "staff_type": "nurse"}, headers=auth_headers)
    resp = client.post(
        "/api/v1/patients", json={"user_id": user["id"], "patient_code": "MRN-DUAL", "blood_group": "O+"}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_create_patient_with_valid_blood_group(client, auth_headers):
    user = signup_plain_user(client, "pat1@hms.com")
    resp = client.post(
        "/api/v1/patients", json={"user_id": user["id"], "patient_code": "MRN-001", "blood_group": "O+"}, headers=auth_headers
    )
    assert resp.status_code == 201


def test_create_patient_with_invalid_blood_group_rejected(client, auth_headers):
    user = signup_plain_user(client, "pat2@hms.com")
    resp = client.post(
        "/api/v1/patients", json={"user_id": user["id"], "patient_code": "MRN-002", "blood_group": "X+"}, headers=auth_headers
    )
    assert resp.status_code == 422


def test_duplicate_patient_code_rejected(client, auth_headers):
    u1 = signup_plain_user(client, "pat3@hms.com")
    u2 = signup_plain_user(client, "pat4@hms.com")
    client.post("/api/v1/patients", json={"user_id": u1["id"], "patient_code": "MRN-DUP", "blood_group": "A+"}, headers=auth_headers)
    resp = client.post("/api/v1/patients", json={"user_id": u2["id"], "patient_code": "MRN-DUP", "blood_group": "B+"}, headers=auth_headers)
    assert resp.status_code == 400


def test_create_duplicate_allergen_rejected(client, auth_headers):
    client.post("/api/v1/allergens", json={"name": "Penicillin", "category": "drug"}, headers=auth_headers)
    resp = client.post("/api/v1/allergens", json={"name": "Penicillin", "category": "drug"}, headers=auth_headers)
    assert resp.status_code == 400


def test_add_and_prevent_duplicate_patient_allergy(client, auth_headers):
    user = signup_plain_user(client, "pat5@hms.com")
    patient = client.post(
        "/api/v1/patients", json={"user_id": user["id"], "patient_code": "MRN-ALG", "blood_group": "AB-"}, headers=auth_headers
    ).json()
    allergen = client.post("/api/v1/allergens", json={"name": "Peanuts", "category": "food"}, headers=auth_headers).json()

    first = client.post(
        f"/api/v1/patients/{patient['id']}/allergies",
        json={"patient_id": patient["id"], "allergen_id": allergen["id"], "severity": "severe"},
        headers=auth_headers,
    )
    assert first.status_code == 201

    duplicate = client.post(
        f"/api/v1/patients/{patient['id']}/allergies",
        json={"patient_id": patient["id"], "allergen_id": allergen["id"], "severity": "mild"},
        headers=auth_headers,
    )
    assert duplicate.status_code == 400


def test_add_medical_history_and_update_status(client, auth_headers):
    user = signup_plain_user(client, "pat6@hms.com")
    patient = client.post(
        "/api/v1/patients", json={"user_id": user["id"], "patient_code": "MRN-HIST", "blood_group": "B-"}, headers=auth_headers
    ).json()

    entry = client.post(
        f"/api/v1/patients/{patient['id']}/medical-history",
        json={"patient_id": patient["id"], "condition_name": "Hypertension", "status": "chronic"},
        headers=auth_headers,
    ).json()

    update = client.patch(
        f"/api/v1/medical-history/{entry['id']}", json={"status": "resolved"}, headers=auth_headers
    )
    assert update.status_code == 200
    assert update.json()["status"] == "resolved"
