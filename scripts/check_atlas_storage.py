"""Explicit live Atlas smoke test; creates and removes only its own synthetic data."""
import os
import uuid
from pathlib import Path
from datetime import datetime,timezone
from dotenv import load_dotenv
from fastapi import HTTPException
from backend.mongo_storage import MongoStore

def main():
    load_dotenv(Path(__file__).resolve().parents[1]/'backend'/'.env.local')
    load_dotenv(Path(__file__).resolve().parents[1]/'.env.local')
    uri=os.environ['MONGODB_URI'];database=os.getenv('MONGODB_DATABASE','grievance_clock')
    a=MongoStore(uri,database);b=MongoStore(uri,database)
    tag=uuid.uuid4().hex;owner='storage_check_'+tag;case_id='GC-CHECK-'+tag;ev_id='EV-CHECK-'+tag
    case={'id':case_id,'created_at':datetime.now(timezone.utc).isoformat(),'evidence':[{'id':ev_id}],'description':'Synthetic storage verification'}
    created=False
    try:
        a.create(owner,case);created=True
        a.write_evidence(ev_id,b'synthetic evidence bytes')
        assert b.get(owner,case_id)['description']==case['description']
        assert b.read_evidence(ev_id)==b'synthetic evidence bytes'
        assert b'Synthetic storage verification' not in a.cases.find_one({'_id':case_id})['payload']
        assert a.files.get(ev_id).read()!=b'synthetic evidence bytes'
        try:b.get('other_account',case_id)
        except HTTPException as exc:assert exc.status_code==404
        else:raise AssertionError('Ownership was not enforced')
        a.save(owner,case)
        assert b.get(owner,case_id)['revision']==1
        print('Atlas: encrypted case/evidence persistence, reconnect, ownership and revision checks passed.')
    finally:
        if created:a.delete(owner,case_id)
        assert not a.files.exists(ev_id)
        a.client.close();b.client.close()

if __name__=='__main__':main()
