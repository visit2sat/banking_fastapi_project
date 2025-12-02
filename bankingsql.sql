
CREATE TABLE accounts (
        id VARCHAR(10) PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        balance REAL NOT NULL DEFAULT 0.0,
        interest_rate REAL NOT NULL DEFAULT 0.0,
        created_at TEXT NOT NULL,
        last_interest_applied TEXT
);

INSERT INTO accounts (id, name, type, balance, interest_rate, created_at, last_interest_applied)
VALUES
    ('ACC001', 'Rahul Sharma', 'Savings', 15000.00, 4.5, '2025-01-10T10:30:00', '2025-02-10T10:30:00'),

    ('ACC002', 'Priya Singh', 'Current', 50000.00, 0.0, '2025-01-12T14:20:00', NULL),

    ('ACC003', 'John Mathew', 'Savings', 22000.50, 5.0, '2025-01-15T09:00:00', '2025-02-15T09:00:00'),

    ('ACC004', 'Anitha Raj', 'Current', 120000.00, 0.0, '2025-01-18T12:45:00', NULL),

    ('ACC005', 'Karthik Kumar', 'Savings', 8000.75, 4.0, '2025-01-20T16:10:00', '2025-02-20T16:10:00');



SELECT * FROM accounts;
DROP   TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS transactions;

CREATE TABLE IF NOT EXISTS transactions (
    id VARCHAR(10) PRIMARY KEY,
    account_id VARCHAR(10) NOT NULL,
    type TEXT NOT NULL,                     -- Deposit, Withdraw, Transfer
    amount REAL NOT NULL,
    balance_after REAL NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

INSERT INTO transactions (id, account_id, type, amount, balance_after, description, created_at)
VALUES
    TXN001,

    ('TXN002', 'ACC002', 'Withdraw', 10000.00, 40000.00, 'ATM Withdrawal', '2025-02-02T11:30:00'),

    ('TXN003', 'ACC003', 'Transfer', 2000.50, 20000.00, 'Transferred to ACC005', '2025-02-03T14:15:00'),

    ('TXN004', 'ACC004', 'Deposit', 15000.00, 135000.00, 'Freelance payment', '2025-02-04T09:45:00'),

    ('TXN005', 'ACC005', 'Withdraw', 500.75, 7500.00, 'Grocery shopping', '2025-02-05T16:20:00');   
SELECT * FROM transactions;

INSERT INTO transactions (id,from_account,to_account,amount,type,status,timestamp,note) VALUES (
   'TXN001', 'ACC001', NULL, 5000.00, 'deposit', 'completed', '2025-02-01T10:00:00', 'Initial deposit'