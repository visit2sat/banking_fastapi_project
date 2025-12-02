# Banking FastAPI Project

## Overview
This project implements a simple banking backend with FastAPI and SQLite supporting:
- Create accounts (Savings, Current)
- Deposit, Withdraw, Transfer transactions
- Auto interest calculation (PUT /accounts/{id}/interest)
- Transaction history (GET /accounts/{id}/transactions)
- Mini-statement (GET /accounts/{id}/mini-statement?limit=5)
- Delete uncompleted transactions (DELETE /transactions/{id})

Compatibility: `POST /tasks/` supports both account creation and transaction payloads.

## Files
- app.py : main FastAPI app
- tests.py : automated tests using TestClient
- README.md : this file

## How to run locally
1. Create a new virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate      # linux / mac
   venv\Scripts\activate         # windows
