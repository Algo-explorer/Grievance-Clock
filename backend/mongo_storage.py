"""Encrypted Atlas storage; ownership and revision checks stay in every query."""
import os
from datetime import datetime,timezone
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError
from gridfs import GridFS, NoFile
from .storage import Store

class MongoStore:
    encode=Store.encode
    decode=Store.decode

    def __init__(self,uri,database='grievance_clock',client=None):
        key=os.getenv('DATA_ENCRYPTION_KEY')
        if not key: raise RuntimeError('Set DATA_ENCRYPTION_KEY before using MongoDB; retain a secure backup of this key.')
        self.cipher=Fernet(key)
        self.client=client or MongoClient(uri,serverSelectionTimeoutMS=5000,connectTimeoutMS=5000)
        self.db=self.client[database]
        self.db.command('ping')
        self.cases=self.db.cases
        self.cases.create_index([('owner',ASCENDING),('created_at',ASCENDING)])
        self.files=GridFS(self.db,collection='evidence')

    def account(self,owner):
        stamp=datetime.now(timezone.utc)
        self.db.users.update_one({'_id':owner},{'$set':{'last_seen_at':stamp},'$setOnInsert':{'created_at':stamp}},upsert=True)

    def create(self,owner,case):
        case['revision']=0
        try:self.cases.insert_one({'_id':case['id'],'owner':owner,'revision':0,'created_at':case['created_at'],'payload':self.encode(case)})
        except DuplicateKeyError:raise HTTPException(409,'Case already exists') from None
        return case

    def get(self,owner,case_id):
        row=self.cases.find_one({'_id':case_id,'owner':owner})
        if not row:raise HTTPException(404,'Case not found')
        return self.decode(row['payload'])

    def list(self,owner):
        return [self.decode(row['payload']) for row in self.cases.find({'owner':owner}).sort('created_at',-1)]

    def save(self,owner,case):
        revision=case['revision']
        updated={**case,'revision':revision+1}
        result=self.cases.update_one({'_id':case['id'],'owner':owner,'revision':revision},
            {'$set':{'revision':revision+1,'payload':self.encode(updated)}})
        if result.matched_count!=1:raise HTTPException(409,'Case changed. Refresh and try again.')
        case['revision']=revision+1
        return case

    def delete(self,owner,case_id):
        # Atomically return the deleted version, including all its evidence IDs.
        row=self.cases.find_one_and_delete({'_id':case_id,'owner':owner})
        if not row:raise HTTPException(404,'Case not found')
        for ev in self.decode(row['payload'])['evidence']:self.delete_evidence(ev['id'])

    def all_cases(self):
        return [(row['owner'],self.decode(row['payload'])) for row in self.cases.find({})]

    def write_evidence(self,evidence_id,data):
        self.files.put(self.cipher.encrypt(data),_id=evidence_id,contentType='application/octet-stream')

    def read_evidence(self,evidence_id):
        try:return self.cipher.decrypt(self.files.get(evidence_id).read())
        except NoFile:raise HTTPException(404,'Evidence not found') from None

    def delete_evidence(self,evidence_id):
        self.files.delete(evidence_id)

def configured_store(root):
    uri=os.getenv('MONGODB_URI','')
    if uri:
        if os.getenv('AUTH_MODE','clerk')=='local':
            raise RuntimeError('MongoDB requires Clerk account authentication; use SQLite for anonymous local testing')
        return MongoStore(uri,os.getenv('MONGODB_DATABASE','grievance_clock'))
    if os.getenv('APP_ENV')=='production':
        raise RuntimeError('MONGODB_URI is required in production; local fallback is disabled')
    return Store(root)
