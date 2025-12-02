from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import sqlite3
from datetime import datetime
import uuid

DB = "banking.db"

def get_conn():
    conn = sqlite3.connect(DB,detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id VARCHAR(10) PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        balance REAL NOT NULL DEFAULT 0.0,
        interest_rate REAL NOT NULL DEFAULT 0.0,
        created_at TEXT NOT NULL,
        last_interest_applied TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id VARCHAR(10) PRIMARY KEY,
        from_account VARCHAR(10),
        to_account VARCHAR(10),
        amount REAL NOT NULL,
        type TEXT NOT NULL,
        status TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        note TEXT
    )
    """)
    conn.commit()
    conn.close()

# initialize DB on module import
init_db()

app = FastAPI(title="Banking System with Transaction History")

class AccountCreate(BaseModel):
    name: str = Field(default="John Doe")
    type: str = Field(..., pattern="^(Savings|Current)$", example="Savings") # type: ignore
    initial_deposit: Optional[float] = Field(0.0, ge=0.0)
    interest_rate: Optional[float] = Field(0.01, ge=0.0)  # default 1% annually

class TransactionCreate(BaseModel):
    action: str #= Field(..., example="deposit")  # deposit, withdraw, transfer
    from_account: Optional[str] = None
    to_account: Optional[str] = None
    amount: float #= Field(..., gt=0)
    note: Optional[str] = None

    @validator("action")
    def action_must_be_valid(cls, v):
        if v not in ("deposit","withdraw","transfer"):
            raise ValueError("action must be 'deposit', 'withdraw' or 'transfer'")
        return v
    def accid_created(self):

        return self.from_account or self.to_account
class TransactionOut(BaseModel):
    id: str
    from_account: Optional[str]
    to_account: Optional[str]
    amount: float
    type: str
    status: str
    created_at: str
    note: Optional[str]

class AccountOut(BaseModel):
    id: str
    name: str
    type: str
    balance: float
    interest_rate: float
    created_at: str
    last_interest_applied: Optional[str]

# Compatibility route: user requested POST /tasks/ — accept either account creation or transactions
@app.post('/tasks/', tags=["tasks"])
def tasks_handler(payload: dict):
    # If payload indicates account creation (has type Savings/Current) -> create account
    if payload.get("type") in ("Savings", "Current") or payload.get("mode") == "create_account":
        data = AccountCreate(**payload)
        return create_account(data)
    else:
        data = TransactionCreate(**payload)
        return create_transaction(data)

@app.post('/accounts/', response_model=AccountOut)
def create_account(account: AccountCreate):
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    # Generate next ACC ID
    cur.execute("""
    SELECT 'ACC' || printf('%06d',
        COALESCE(MAX(CAST(SUBSTR(id, 4) AS INTEGER)), 0) + 1
    ) AS next_id
    FROM accounts;
    """)
    acc_id = cur.fetchone()[0]

# Insert account
    cur.execute("""
    INSERT INTO accounts
    (id, name, type, balance, interest_rate, created_at, last_interest_applied)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    (
    acc_id,
    account.name,
    account.type,
    float(account.initial_deposit or 0.0),
    float(account.interest_rate or 0.0),
    now,
    now
    ))

    conn.commit()
    conn.close()
    return AccountOut(
        id=acc_id,
        name=account.name,
        type=account.type,
        balance=float(account.initial_deposit or 0.0),
        interest_rate=float(account.interest_rate or 0.0),
        created_at=now,
        last_interest_applied=now
    )
@app.get('/accounts/', response_model=List[AccountOut])
def list_accounts():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts")
    rows = cur.fetchall()
    conn.close()
    return [AccountOut(**r) for r in rows]
@app.get('/transactions/', response_model=List[TransactionOut])
def list_transactions():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="Account not found")
    return [TransactionOut(
        id=row['id'],
        from_account=row['from_account'],
        to_account=row['to_account'],
        amount=row['amount'],
        type=row['type'],
        status=row['status'],
        created_at=row['timestamp'],
        note=row['note']
    ) for row in rows]

@app.put('/accounts/{account_id}/interest', response_model=AccountOut)
def apply_interest(account_id: str):
    # simple interest: interest_rate is annual; apply for days since last_interest_applied
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Account not found")
    balance = row['balance']
    rate = row['interest_rate']
    last = row['last_interest_applied'] or row['created_at']
    last_dt = datetime.fromisoformat(last)
    now = datetime.utcnow()
    days = (now - last_dt).days
    if days <= 0:
        conn.close()
        return AccountOut(**row)
    interest = balance * (rate) * (days/365.0)
    new_balance = balance + interest
    cur.execute("UPDATE accounts SET balance=?, last_interest_applied=? WHERE id=?", (new_balance, now.isoformat(), account_id))
    conn.commit()
    cur.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
    updated = cur.fetchone()
    conn.close()
    return AccountOut(**updated)

@app.post('/transactions/', response_model=TransactionOut)
def create_transaction(tx: TransactionCreate):
    conn = get_conn()
    cur = conn.cursor()
    tid =     None
    # Generate next TX ID
    cur.execute("""
    SELECT 'TX' || printf('%06d',
        COALESCE(MAX(CAST(SUBSTR(id, 4) AS INTEGER)), 0) + 1
    ) AS next_id
    FROM transactions;
    """)
    tid = cur.fetchone()[0]
    now = datetime.utcnow().isoformat()
    status = "completed"
    
    # deposit
    if tx.action == "deposit":
        if not tx.to_account:
            conn.close()
            raise HTTPException(status_code=400, detail="to_account required for deposit")
        cur.execute("SELECT balance FROM accounts WHERE id=?", (tx.to_account,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="to_account not found")
        newbal = row['balance'] + tx.amount
        cur.execute("UPDATE accounts SET balance=? WHERE id=?", (newbal, tx.to_account))
        cur.execute("INSERT INTO transactions (id,from_account,to_account,amount,type,status,timestamp,note) VALUES (?,?,?,?,?,?,?,?)",
                    (tid, tx.from_account,tx.to_account, tx.amount, 'deposit', status, now, tx.note))
    elif tx.action == "withdraw":
        if not tx.from_account:
            conn.close()
            raise HTTPException(status_code=400, detail="from_account required for withdraw")
        cur.execute("SELECT balance FROM accounts WHERE id=?", (tx.from_account,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="from_account not found")
        if row['balance'] < tx.amount:
            conn.close()
            raise HTTPException(status_code=400, detail="insufficient funds")
        newbal = row['balance'] - tx.amount
        cur.execute("UPDATE accounts SET balance=? WHERE id=?", (newbal, tx.from_account))
        cur.execute("INSERT INTO transactions (id,from_account,to_account,amount,type,status,timestamp,note) VALUES (?,?,?,?,?,?,?,?)",
                    (tid, tx.from_account, None, tx.amount, 'withdraw', status, now, tx.note))
    else: # transfer
        if not tx.from_account or not tx.to_account:
            conn.close()
            raise HTTPException(status_code=400, detail="from_account and to_account required for transfer")
        if tx.from_account == tx.to_account:
            conn.close()
            raise HTTPException(status_code=400, detail="from_account and to_account must be different")
        cur.execute("SELECT balance FROM accounts WHERE id=?", (tx.from_account,))
        rowf = cur.fetchone()
        cur.execute("SELECT balance FROM accounts WHERE id=?", (tx.to_account,))
        rowt = cur.fetchone()
        if not rowf or not rowt:
            conn.close()
            raise HTTPException(status_code=404, detail="account not found")
        if rowf['balance'] < tx.amount:
            conn.close()
            raise HTTPException(status_code=400, detail="insufficient funds")
        newf = rowf['balance'] - tx.amount
        newt = rowt['balance'] + tx.amount
        cur.execute("UPDATE accounts SET balance=? WHERE id=?", (newf, tx.from_account))
        cur.execute("UPDATE accounts SET balance=? WHERE id=?", (newt, tx.to_account))
        cur.execute("INSERT INTO transactions (id,from_account,to_account,amount,type,status,timestamp,note) VALUES (?,?,?,?,?,?,?,?)",
                    (tid, tx.from_account, tx.to_account, tx.amount, 'transfer', status, now, tx.note))
    conn.commit()
    cur.execute("SELECT * FROM transactions WHERE id=?", (tid,))
    txrow = cur.fetchone()
    conn.close()
    return TransactionOut(
        id=txrow['id'],
        from_account=txrow['from_account'],
        to_account=txrow['to_account'],
        amount=txrow['amount'],
        type=txrow['type'],
        status=txrow['status'],
        created_at=txrow['timestamp'],
        note=txrow['note']
    )

@app.get('/accounts/{account_id}/transactions', response_model=List[TransactionOut])
def get_transactions(account_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE id=?", (account_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Account not found")
    cur.execute("SELECT * FROM transactions WHERE from_account=? OR to_account=? ORDER BY timestamp DESC", (account_id, account_id))
    rows = cur.fetchall()
    conn.close()
    return [TransactionOut(**r) for r in rows]

@app.get('/accounts/{account_id}/mini-statement', response_model=List[TransactionOut])
def mini_statement(account_id: str, limit: int = 5):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts WHERE id=?", (account_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Account not found")
    cur.execute("SELECT * FROM transactions WHERE from_account=? OR to_account=? ORDER BY timestamp DESC LIMIT ?", (account_id, account_id, limit))
    rows = cur.fetchall()
    conn.close()
    return [TransactionOut(**r) for r in rows]

@app.delete('/transactions/{transaction_id}')
def delete_transaction(transaction_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Transaction not found")
    # Only allow delete if status is not 'completed' (simulates uncompleted transaction)
    if row['status'] == 'completed':
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot delete completed transaction")
    cur.execute("DELETE FROM transactions WHERE id=?", (transaction_id,))
    conn.commit()
    conn.close()
    return {"detail":"deleted"}
