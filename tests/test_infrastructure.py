"""Tests for Module 3: Hospital Infrastructure."""


def test_create_department(client, auth_headers):
    resp = client.post("/api/v1/departments", json={"name": "Cardiology"}, headers=auth_headers)
    assert resp.status_code == 201


def test_duplicate_department_name_rejected(client, auth_headers):
    client.post("/api/v1/departments", json={"name": "Cardiology"}, headers=auth_headers)
    resp = client.post("/api/v1/departments", json={"name": "Cardiology"}, headers=auth_headers)
    assert resp.status_code == 400


def test_department_bad_manager_id_rejected(client, auth_headers):
    resp = client.post("/api/v1/departments", json={"name": "Neuro", "manager_id": 9999}, headers=auth_headers)
    assert resp.status_code == 404


def test_create_ward_requires_valid_department(client, auth_headers):
    resp = client.post(
        "/api/v1/wards", json={"department_id": 9999, "name": "X", "ward_type": "icu", "total_capacity": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_create_ward_success(client, auth_headers):
    dept = client.post("/api/v1/departments", json={"name": "Cardiology"}, headers=auth_headers).json()
    resp = client.post(
        "/api/v1/wards",
        json={"department_id": dept["id"], "name": "General Ward A", "ward_type": "general", "total_capacity": 20},
        headers=auth_headers,
    )
    assert resp.status_code == 201


def test_duplicate_room_number_rejected(client, auth_headers):
    client.post("/api/v1/rooms", json={"room_number": "101", "room_type": "private", "daily_rate": 5000}, headers=auth_headers)
    resp = client.post("/api/v1/rooms", json={"room_number": "101", "room_type": "private", "daily_rate": 5000}, headers=auth_headers)
    assert resp.status_code == 400


def test_bed_requires_exactly_one_location(client, auth_headers):
    dept = client.post("/api/v1/departments", json={"name": "Cardiology"}, headers=auth_headers).json()
    ward = client.post(
        "/api/v1/wards", json={"department_id": dept["id"], "name": "W1", "ward_type": "general", "total_capacity": 10},
        headers=auth_headers,
    ).json()
    room = client.post("/api/v1/rooms", json={"room_number": "201", "room_type": "private", "daily_rate": 4000}, headers=auth_headers).json()

    both = client.post("/api/v1/beds", json={"bed_number": "X", "ward_id": ward["id"], "room_id": room["id"]}, headers=auth_headers)
    assert both.status_code == 422

    neither = client.post("/api/v1/beds", json={"bed_number": "X"}, headers=auth_headers)
    assert neither.status_code == 422

    valid_ward_bed = client.post("/api/v1/beds", json={"bed_number": "A1", "ward_id": ward["id"]}, headers=auth_headers)
    assert valid_ward_bed.status_code == 201

    valid_room_bed = client.post("/api/v1/beds", json={"bed_number": "R201", "room_id": room["id"]}, headers=auth_headers)
    assert valid_room_bed.status_code == 201


def test_list_available_beds(client, auth_headers):
    dept = client.post("/api/v1/departments", json={"name": "Cardiology"}, headers=auth_headers).json()
    ward = client.post(
        "/api/v1/wards", json={"department_id": dept["id"], "name": "W1", "ward_type": "general", "total_capacity": 10},
        headers=auth_headers,
    ).json()
    client.post("/api/v1/beds", json={"bed_number": "A1", "ward_id": ward["id"]}, headers=auth_headers)

    resp = client.get("/api/v1/beds/available", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["is_occupied"] is False


def test_duplicate_operation_theater_code_rejected(client, auth_headers):
    client.post("/api/v1/operation-theaters", json={"name_or_code": "OT-1"}, headers=auth_headers)
    resp = client.post("/api/v1/operation-theaters", json={"name_or_code": "OT-1"}, headers=auth_headers)
    assert resp.status_code == 400


def test_delete_department_blocked_when_dependents_exist(client, auth_headers):
    dept = client.post("/api/v1/departments", json={"name": "Cardiology"}, headers=auth_headers).json()
    client.post(
        "/api/v1/wards", json={"department_id": dept["id"], "name": "W1", "ward_type": "general", "total_capacity": 10},
        headers=auth_headers,
    )
    resp = client.delete(f"/api/v1/departments/{dept['id']}", headers=auth_headers)
    assert resp.status_code == 400


def test_delete_ward_blocked_when_beds_exist(client, auth_headers):
    dept = client.post("/api/v1/departments", json={"name": "Cardiology"}, headers=auth_headers).json()
    ward = client.post(
        "/api/v1/wards", json={"department_id": dept["id"], "name": "W1", "ward_type": "general", "total_capacity": 10},
        headers=auth_headers,
    ).json()
    client.post("/api/v1/beds", json={"bed_number": "A1", "ward_id": ward["id"]}, headers=auth_headers)

    resp = client.delete(f"/api/v1/wards/{ward['id']}", headers=auth_headers)
    assert resp.status_code == 400
