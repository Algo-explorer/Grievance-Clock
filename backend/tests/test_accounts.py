import copy
import time
from types import SimpleNamespace
import jwt
import mongomock
import mongomock.gridfs
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend import authentication,main
from backend.mongo_storage import MongoStore

@pytest.fixture
def mongo(monkeypatch):
    mongomock.gridfs.enable_gridfs_integration()
    monkeypatch.setenv('DATA_ENCRYPTION_KEY',Fernet.generate_key().decode())
    return MongoStore('unused',client=mongomock.MongoClient())

def test_mongo_encryption_ownership_revisions_and_evidence(mongo):
    case={'id':'GC-test','created_at':'2026-10-03','evidence':[{'id':'EV-test'}],'description':'private complaint'}
    mongo.create('user_alice',case)
    assert b'private complaint' not in mongo.cases.find_one({'_id':case['id']})['payload']
    assert mongo.list('user_bob')==[]
    for action in [lambda:mongo.get('user_bob',case['id']),lambda:mongo.delete('user_bob',case['id'])]:
        with pytest.raises(HTTPException) as err:action()
        assert err.value.status_code==404
    stale=copy.deepcopy(case)
    mongo.save('user_alice',case)
    with pytest.raises(HTTPException) as err:mongo.save('user_alice',stale)
    assert err.value.status_code==409
    assert stale['revision']==0
    with pytest.raises(HTTPException):mongo.save('user_bob',case)
    mongo.write_evidence('EV-test',b'private image')
    assert mongo.files.get('EV-test').read()!=b'private image'
    assert mongo.read_evidence('EV-test')==b'private image'
    mongo.delete('user_alice',case['id'])
    assert not mongo.files.exists('EV-test')
    mongo.account('user_alice');mongo.account('user_alice')
    assert mongo.db.users.count_documents({})==1

@pytest.fixture
def accounts(monkeypatch,mongo):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    monkeypatch.setenv('AUTH_MODE','clerk')
    monkeypatch.setenv('CLERK_ISSUER_URL','https://test.clerk.accounts.dev')
    monkeypatch.setenv('AI_MODE','demo')
    monkeypatch.setattr(authentication,'key_client',lambda url:SimpleNamespace(get_signing_key_from_jwt=lambda token:SimpleNamespace(key=key.public_key())))
    monkeypatch.setattr(main,'store',mongo)
    main.rate_buckets.clear()
    def token(user='user_alice',**changes):
        stamp=int(time.time())
        claims={'sub':user,'sid':'sess_test','iss':'https://test.clerk.accounts.dev','iat':stamp,'nbf':stamp-1,'exp':stamp+60,'azp':'http://127.0.0.1:3000'}
        claims.update(changes)
        return jwt.encode(claims,key,algorithm='RS256',headers={'kid':'test'})
    with TestClient(main.app) as client:yield client,token,mongo

def test_verified_accounts_return_to_data_and_cannot_access_others(accounts):
    client,token,mongo=accounts
    alice={'Authorization':'Bearer '+token()}
    assert client.post('/api/session',headers=alice).status_code==200
    case=client.post('/api/cases',json={},headers=alice).json()
    base='/api/cases/'+case['id']
    assert client.get('/api/cases',headers={'Authorization':'Bearer '+token()}).json()[0]['id']==case['id']
    bob={'Authorization':'Bearer '+token('user_bob')}
    assert client.get('/api/cases',headers=bob).json()==[]
    for method,path,kwargs in [('get',base,{}),('delete',base,{}),('post',base+'/resolve',{}),
                              ('get',base+'/documents/dossier.zip',{}),('get',base+'/evidence/EV-test?preview=true',{}),
                              ('post',base+'/speech',{'json':{'text':'नमस्ते'}})]:
        assert getattr(client,method)(path,headers=bob,**kwargs).status_code==404
    assert mongo.db.users.find_one({'_id':'user_alice'}) is not None

@pytest.mark.parametrize('changes',[{'exp':1},{'nbf':9999999999},{'iss':'https://attacker.example'},
                                  {'azp':'https://attacker.example'},{'sub':'admin'},{'sts':'pending'},{'sid':''}])
def test_bad_claims_cannot_open_workspace(accounts,changes):
    client,token,_=accounts
    assert client.get('/api/cases',headers={'Authorization':'Bearer '+token(**changes)}).status_code==401

def test_unsigned_tampered_missing_and_legacy_sessions_rejected(accounts):
    client,token,_=accounts
    assert client.get('/api/cases').status_code==401
    client.cookies.set('gc_session','old-anonymous-cookie')
    assert client.post('/api/session').status_code==401
    assert client.get('/api/cases',headers={'Authorization':'Bearer '+token()[:-8]+'garbage!'}).status_code==401
    unsigned=jwt.encode({'sub':'user_alice'},key='',algorithm='none')
    assert client.get('/api/cases',headers={'Authorization':'Bearer '+unsigned}).status_code==401
    client.cookies.set('__session',token())
    assert client.get('/api/cases').status_code==200

def test_missing_issuer_and_production_guest_fail_closed(monkeypatch):
    monkeypatch.delenv('CLERK_ISSUER_URL',raising=False)
    with pytest.raises(HTTPException) as err:authentication.issuer()
    assert err.value.status_code==503
    monkeypatch.setenv('APP_ENV','production');monkeypatch.setenv('AUTH_MODE','local')
    with pytest.raises(RuntimeError):authentication.mode()
