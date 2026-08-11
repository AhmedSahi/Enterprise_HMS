# Enterprise IAM and Hospital Management System Backend

## Overview

This project is a production-grade, modular backend application built with FastAPI, PostgreSQL, SQLAlchemy ORM, and Alembic for database migrations. It combines an Enterprise-grade Identity and Access Management (IAM) framework with a comprehensive Hospital Management System (HMS).

The system enforces Role-Based Access Control (RBAC), JWT authentication, user profiling, clinical workflows, billing management, and blood bank inventory tracking.

---

## Key Modules & Features

### 1. Identity & Access Management (IAM)
* **Users & Roles:** Granular authentication system with Role-Based Access Control (RBAC).
* **Permissions:** Route-level permission validation for Admin, Manager, Doctor, Patient, and User roles.
* **Audit Logs & Refresh Tokens:** Secure session tracking, token revocation, and system activity logs.

### 2. User Profiles
* **Patient Profiles:** Extended medical profile linked directly to IAM user accounts.
* **Doctor Profiles:** Holds specialization details, license numbers, and operational schedules.

### 3. Clinical Operations
* **Departments:** Department management connected with assigned managers (Users).
* **Appointments:** Scheduling workflow connecting patients and doctors.
* **Prescriptions:** Strict 1-to-1 relation mapped directly with completed appointments.

### 4. Billing Module
* **Invoices:** Auto-generated records tracking total cost and payment status.
* **Payments:** Supports multiple and partial payment entries per invoice.

### 5. Blood Bank Module
* **Inventory Management:** Tracks blood unit availability across all blood groups.
* **Blood Requests:** Tracks patient blood requests through approval and fulfillment states.

---

##  Current Directory Structure

```text
ENTERPRISE_IAM/
├── alembic/              # Alembic database migrations and versions
├── src/                  # Application source code
│   ├── core/             # Security, tokens, and core configurations
│   ├── db/               # Database connection and session management
│   ├── models/           # SQLAlchemy database models
│   └── schemas/          # Pydantic data validation models
├── .env                  # Environment secrets (Git-ignored)
├── .env.example          # Sample environment variables configuration
├── .gitignore            # Git exclusion definitions
├── alembic.ini           # Alembic configuration file
├── main.py               # FastAPI application entry point
└── requirements.txt      # Project Python dependencies