"""Encrypted case aggregates and immutable evidence; owner-scoped queries and CAS writes."""
import hashlib
import json
import os
import secrets
import sqlite3
from pathlib import Path
from cryptography.fernet import Fernet
from fastapi import HTTPException

class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'evidence').mkdir(exist_ok=True)
        key = os.getenv('DATA_ENCRYPTION_KEY')
        keyfile = self.root / 'encryption.key'
        if not key:
            if not keyfile.exists():
                try:
                    with keyfile.open('xb') as f:
                        f.write(Fernet.generate_key())
                except FileExistsError:
                    pass
            key = keyfile.read_bytes()
        self.cipher = Fernet(key)
        self.db = str(self.root / 'clock.sqlite3')
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, owner TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, owner TEXT NOT NULL, revision INTEGER NOT NULL, payload BLOB NOT NULL);
            CREATE INDEX IF NOT EXISTS cases_owner ON cases(owner);
            ''')

    def connect(self):
        return sqlite3.connect(self.db, timeout=20)

    def account(self,owner):
        # Local development persists cases under the verified account subject.
        pass

    def delete_evidence(self,evidence_id):
        (self.root/'evidence'/evidence_id).unlink(missing_ok=True)

    def session(self, token):
        if not token:
            return None
        with self.connect() as db:
            row = db.execute('SELECT owner FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        return row[0] if row else None

    def new_session(self):
        token, owner = secrets.token_urlsafe(40), secrets.token_hex(16)
        with self.connect() as db:
            db.execute('INSERT INTO sessions VALUES (?,?)', (hashlib.sha256(token.encode()).hexdigest(), owner))
        return token, owner

    def encode(self, value):
        return self.cipher.encrypt(json.dumps(value, ensure_ascii=False).encode())

    def decode(self, value):
        return json.loads(self.cipher.decrypt(value))

    def create(self, owner, case):
        case['revision'] = 0
        with self.connect() as db:
            db.execute('INSERT INTO cases VALUES (?,?,?,?)', (case['id'], owner, 0, self.encode(case)))
        return case

    def get(self, owner, case_id):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM cases WHERE id=? AND owner=?', (case_id, owner)).fetchone()
        if not row:
            raise HTTPException(404, 'Case not found')
        return self.decode(row[0])

    def list(self, owner):
        with self.connect() as db:
            rows = db.execute('SELECT payload FROM cases WHERE owner=? ORDER BY rowid DESC', (owner,)).fetchall()
        return [self.decode(row[0]) for row in rows]

    def save(self, owner, case):
        revision = case['revision']
        case['revision'] += 1
        with self.connect() as db:
            n = db.execute('UPDATE cases SET payload=?, revision=? WHERE id=? AND owner=? AND revision=?',
                           (self.encode(case), case['revision'], case['id'], owner, revision)).rowcount
        if not n:
            raise HTTPException(409, 'Case changed. Refresh and try again.')
        return case

    def delete(self, owner, case_id):
        case = self.get(owner, case_id)
        with self.connect() as db:
            db.execute('DELETE FROM cases WHERE id=? AND owner=?', (case_id, owner))
        for ev in case['evidence']:
            self.delete_evidence(ev['id'])

    def all_cases(self):
        with self.connect() as db:
            rows = db.execute('SELECT owner,payload FROM cases').fetchall()
        return [(owner, self.decode(payload)) for owner, payload in rows]

    def write_evidence(self, evidence_id, data):
        with (self.root / 'evidence' / evidence_id).open('xb') as f:
            f.write(self.cipher.encrypt(data))

    def read_evidence(self, evidence_id):
        return self.cipher.decrypt((self.root / 'evidence' / evidence_id).read_bytes())
