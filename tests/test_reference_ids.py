import json,sqlite3,uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from app import REFERENCE_BLOCK_SIZE,create_app
from test_app import env,login,survey


def configure(c,user='field',**changes):
 h=login(c,'admin');data={'community':'Bucana','municipality_province':'Davao / Davao del Sur','language':'Cebuano'};data.update(changes)
 response=c.patch('/api/users/'+user,headers=h,json=data);assert response.status_code==200,response.json
 return login(c,user)


def reserve(c,h,instrument='household',device=None,request=None):
 u=c.get('/api/session').json['user']
 data={'user_id':u['id'],'instrument':instrument,'device_id':device or str(uuid.uuid4()),'request_id':request or str(uuid.uuid4()),'assignment_version':u['assignment_version']}
 return c.post('/api/reference-ranges',headers=h,json=data),data


def allocated_payload(grant,sequence=None):
 sequence=grant['start'] if sequence is None else sequence
 d=survey();code={'household':'HE','community':'CI','observation':'SO'}[grant['instrument']]
 d.update(instrument=grant['instrument'],respondent=grant['username']+'-'+code+'-'+str(sequence).zfill(3),reference_mode='allocated-v1',reference_allocation_id=grant['id'],reference_sequence=sequence,assignment_version=grant['assignment_version'],community=grant['assignment']['community'],metadata={k:grant['assignment'][k] for k in ['municipality_province','language']})
 if d['instrument']!='household':d['answers']={}
 return d


def test_admin_assignments_required_and_update_without_changing_history(env):
 app,c=env;h=login(c,'admin')
 base={'name':'New Enum','username':'newenum','password':'a-good-password-2026','community':'Bucana'}
 assert c.post('/api/users',headers=h,json=base).status_code==400
 base.update(municipality_province=' Davao / Davao del Sur ',language=' Cebuano ')
 assert c.post('/api/users',headers=h,json=base).status_code==201
 uid=next(u['id'] for u in c.get('/api/dashboard').json['users'] if u['username']=='newenum')
 f=login(c,'newenum');u=c.get('/api/session').json['user'];assert u['language']=='Cebuano' and u['assignment_version']==0
 assert c.patch('/api/users/'+uid,headers=f,json={'language':'English'}).status_code==403
 h=login(c,'admin');assert c.patch('/api/users/'+uid,headers=h,json={'language':'English'}).status_code==200
 u=next(u for u in c.get('/api/dashboard').json['users'] if u['id']==uid);assert u['assignment_version']==1 and u['language']=='English'
 assert c.patch('/api/users/'+uid,headers=h,json={'target':50}).status_code==200
 assert next(u for u in c.get('/api/dashboard').json['users'] if u['id']==uid)['assignment_version']==1
 assert c.patch('/api/users/'+uid,headers=h,json={'community':''}).status_code==400


def test_reference_endpoint_permissions_and_incomplete_legacy_accounts(env):
 app,c=env
 assert c.post('/api/reference-ranges',json={}).status_code==401
 h=login(c,'admin');assert c.post('/api/reference-ranges',headers=h,json={}).status_code==403
 h=login(c);r,data=reserve(c,h);assert r.status_code==409
 # Existing manually coded offline interviews remain accepted without resetting accounts.
 assert c.post('/api/surveys',headers=h,json=survey()).status_code==201
 h=configure(c);r,data=reserve(c,h);assert r.status_code==201
 data['user_id']='other';assert c.post('/api/reference-ranges',headers=h,json=data).status_code==403
 data['user_id']='field';data['device_id']='invalid';assert c.post('/api/reference-ranges',headers=h,json=data).status_code==400


def test_independent_ranges_idempotent_reservations_and_multiple_devices(env):
 app,c=env;h=configure(c);device=str(uuid.uuid4())
 grants=[]
 for kind in ['household','community','observation']:
  r,data=reserve(c,h,kind,device);assert r.status_code==201,r.json
  grant=r.json['allocation'];grants.append(grant)
  assert grant['start']==1 and grant['end']==REFERENCE_BLOCK_SIZE
  retry=c.post('/api/reference-ranges',headers=h,json=data)
  assert retry.status_code==200 and retry.json['allocation']==grant
  d=allocated_payload(grant);assert c.post('/api/surveys',headers=h,json=d).status_code==201
  assert d['respondent']=={'household':'field-HE-001','community':'field-CI-001','observation':'field-SO-001'}[kind]
 r,_=reserve(c,h,'household');assert r.json['allocation']['start']==REFERENCE_BLOCK_SIZE+1
 h=configure(c,'other');r,_=reserve(c,h);assert r.json['allocation']['start']==1
 assert c.post('/api/surveys',headers=h,json=allocated_payload(grants[0])).status_code==400


def test_claims_reject_tampering_and_duplicate_numbers(env):
 app,c=env;h=configure(c);r,_=reserve(c,h);g=r.json['allocation'];valid=allocated_payload(g)
 for updates in [{'respondent':'invented-HE-001'},{'community':'Other barangay'},{'metadata':{'municipality_province':'Other','language':'Cebuano'}},{'reference_sequence':g['end']+1},{'reference_sequence':True},{'reference_allocation_id':str(uuid.uuid4())},{'assignment_version':999999},{'instrument':'community'}]:
  d=allocated_payload(g);d.update(updates)
  assert c.post('/api/surveys',headers=h,json=d).status_code==400,updates
 assert c.post('/api/surveys',headers=h,json=valid).status_code==201
 assert c.post('/api/surveys',headers=h,json=valid).json['duplicate']
 d=allocated_payload(g);assert c.post('/api/surveys',headers=h,json=d).status_code==409
 # Legacy clients also cannot take a number already reserved or claimed by another interview.
 legacy=survey();legacy['respondent']='field-HE-002';assert c.post('/api/surveys',headers=h,json=legacy).status_code==409


def test_assignment_changes_preserve_old_offline_snapshot(env):
 app,c=env;h=configure(c);r,_=reserve(c,h);g=r.json['allocation'];old=allocated_payload(g)
 h=login(c,'admin');assert c.patch('/api/users/field',headers=h,json={'community':'New barangay','municipality_province':'New municipality / province','language':'English'}).status_code==200
 h=login(c);assert c.post('/api/surveys',headers=h,json=old).status_code==201
 r,_=reserve(c,h);new=r.json['allocation'];assert new['start']==101 and new['assignment_version']==g['assignment_version']+1
 assert new['assignment']['community']=='New barangay' and new['assignment']['language']=='English'
 fresh=allocated_payload(new);assert c.post('/api/surveys',headers=h,json=fresh).status_code==201
 h=login(c,'admin');rows=c.get('/api/dashboard').json['surveys'];assert next(x for x in rows if x['id']==old['id'])['metadata']['language']=='Cebuano';assert next(x for x in rows if x['id']==fresh['id'])['metadata']['language']=='English'
 assert 'reference_sequence' in c.get('/api/export').text


def test_deleted_reference_is_never_reused_and_refusal_keeps_identity(env):
 app,c=env;h=configure(c);r,_=reserve(c,h);g=r.json['allocation'];d=allocated_payload(g)
 assert c.post('/api/surveys',headers=h,json=d).status_code==201
 a=login(c,'admin');assert c.delete('/api/surveys/'+d['id'],headers=a,json={'confirm_respondent':d['respondent']}).status_code==200
 h=login(c);assert c.post('/api/surveys',headers=h,json=d).json['deleted']
 replacement=allocated_payload(g);assert c.post('/api/surveys',headers=h,json=replacement).status_code==409
 declined=allocated_payload(g,g['start']+1);declined['consent']='No'
 assert c.post('/api/surveys',headers=h,json=declined).status_code==201
 h=login(c,'admin');row=c.get('/api/dashboard').json['surveys'][0];assert row['respondent']=='field-HE-002' and row['metadata']=={} and row['reference_mode']=='allocated-v1'


def test_existing_formatted_manual_ids_seed_next_number(env):
 app,c=env;h=login(c);d=survey();d['respondent']='field-HE-008';assert c.post('/api/surveys',headers=h,json=d).status_code==201
 h=configure(c);r,_=reserve(c,h);assert r.json['allocation']['start']==9


def test_concurrent_devices_receive_disjoint_ranges(env):
 app,c=env;configure(c)
 def allocate(_):
  client=app.test_client();h=login(client);r,_=reserve(client,h);assert r.status_code==201;return r.json['allocation']
 with ThreadPoolExecutor(max_workers=2) as pool:grants=list(pool.map(allocate,range(2)))
 assert sorted(g['start'] for g in grants)==[1,101]
 assert len({g['id'] for g in grants})==2


def test_additive_account_migration_preserves_records(env):
 app,c=env;h=login(c);d=survey();assert c.post('/api/surveys',headers=h,json=d).status_code==201
 con=sqlite3.connect(app.config['DATABASE'])
 for name in ['municipality_province','language','assignment_version']:con.execute('ALTER TABLE users DROP COLUMN '+name)
 for name in ['reference_mode','reference_allocation_id','reference_sequence']:con.execute('ALTER TABLE surveys DROP COLUMN '+name)
 con.commit();con.close()
 for _ in range(2):
  updated=create_app({'TESTING':True,'SECRET_KEY':'testing-only','DATABASE':app.config['DATABASE']});client=updated.test_client();login(client,'admin');dash=client.get('/api/dashboard').json
  assert len(dash['users'])==2 and len(dash['surveys'])==1 and dash['surveys'][0]['id']==d['id']
  assert dash['surveys'][0]['reference_mode']=='manual'
  assert all(u['municipality_province']=='' and u['language']=='' for u in dash['users'])


def test_one_reserved_range_can_use_new_defaults_without_resetting_sequence(env):
 app,c=env;h=configure(c);r,_=reserve(c,h);grant=r.json['allocation'];first=allocated_payload(grant)
 assert c.post('/api/surveys',headers=h,json=first).status_code==201
 h=login(c,'admin');assert c.patch('/api/users/field',headers=h,json={'community':'New barangay','language':'English'}).status_code==200
 h=login(c);profile=c.get('/api/session').json['user'];second=allocated_payload(grant,grant['start']+1)
 second.update(assignment_version=profile['assignment_version'],community=profile['community'],metadata={k:profile[k] for k in ['municipality_province','language']})
 assert second['respondent']=='field-HE-002'
 assert c.post('/api/surveys',headers=h,json=second).status_code==201
 checkin=c.post('/api/checkin',headers=h,json={}).json
 assert checkin['user']['language']=='English'


def test_initial_pool_covers_a_large_assigned_target(env):
 app,c=env;configure(c);h=login(c,'admin');assert c.patch('/api/users/field',headers=h,json={'target':500}).status_code==200
 h=login(c);r,_=reserve(c,h);assert r.json['allocation']['start']==1 and r.json['allocation']['end']==500
