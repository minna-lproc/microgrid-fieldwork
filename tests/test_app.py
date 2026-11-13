import json,uuid,sqlite3
from datetime import datetime,timezone
import pytest
from werkzeug.security import generate_password_hash
from app import create_app,SCHEMA

@pytest.fixture
def env(tmp_path):
 app=create_app({'TESTING':True,'SECRET_KEY':'testing-only','DATABASE':str(tmp_path/'test.sqlite')})
 con=sqlite3.connect(app.config['DATABASE'])
 for name,role in [('admin','admin'),('field','enumerator'),('other','enumerator')]:
  con.execute('INSERT INTO users(id,username,name,password,role,community) VALUES(?,?,?,?,?,?)',(name,name,name,generate_password_hash('a-good-password-2026'),role,'Bucana'))
 con.commit();con.close()
 return app,app.test_client()

def login(c,user='field'):
 r=c.post('/api/login',json={'username':user,'password':'a-good-password-2026'}); assert r.status_code==200
 return {'X-CSRF-Token':r.json['csrf']}

def survey(**kw):
 t=datetime.now(timezone.utc).isoformat()
 return dict(id=str(uuid.uuid4()),version=SCHEMA['version'],instrument='household',community='Bucana',respondent='BUC-001',consent='Yes',gps_consent='No',location=None,answers={'A1':'Female','D1':'No (skip to Part E)'},metadata={'municipality_province':'Davao / Davao del Sur','language':'Cebuano'},photo_consent='No',audio_consent='No',started_at=t,completed_at=t,**kw)

def test_role_access_and_csrf(env):
 app,c=env
 assert c.get('/api/dashboard').status_code==401
 h=login(c)
 assert c.get('/api/dashboard').status_code==403
 assert c.get('/api/export').status_code==403
 assert c.post('/api/users',json={}).status_code==403
 assert c.post('/api/surveys',json=survey()).status_code==403
 assert c.post('/api/surveys',json=survey(),headers=h).status_code==201
 assert c.get('/api/my-surveys').json['surveys'][0]['respondent']=='BUC-001'
 assert c.get('/api/session').headers['Cache-Control']=='no-store'

def test_idempotent_sync_and_owner(env):
 app,c=env;h=login(c);s=survey();s['user_id']='other';s['owner']='other'
 assert c.post('/api/surveys',json=s,headers=h).status_code==201
 r=c.post('/api/surveys',json=s,headers=h);assert r.status_code==200 and r.json['duplicate']
 assert len(c.get('/api/my-surveys').json['surveys'])==1
 h=login(c,'other')
 assert c.get('/api/my-surveys').json['surveys']==[]
 assert c.post('/api/surveys',json=s,headers=h).status_code==409
 h=login(c,'admin');row=c.get('/api/dashboard').json['surveys'][0];assert row['user_id']=='field'

def test_consent_and_gps(env):
 app,c=env;h=login(c);s=survey();s['location']={'lat':7,'lng':125,'accuracy':20}
 assert c.post('/api/surveys',json=s,headers=h).status_code==400
 s['gps_consent']='Yes';assert c.post('/api/surveys',json=s,headers=h).status_code==201
 s=survey();s['consent']='No';s['answers']={'A1':'Female'}
 assert c.post('/api/surveys',json=s,headers=h).status_code==201
 h=login(c,'admin');rows=c.get('/api/dashboard').json['surveys'];assert next(r for r in rows if r['id']==s['id'])['answers']=={}

def test_validation_and_skip_rules(env):
 app,c=env;h=login(c)
 for ans in [{'A1':'invented'},{'A3':{'members':'3','under5':'4'}},{'C_loads':[{'hours':'25'}]},{'B1':['None','Grid / distribution utility']},{'A3':{'members':'2.4'}},{'C_loads':[{'time':'midday'}]}]:
  s=survey();s['answers']=ans;assert c.post('/api/surveys',json=s,headers=h).status_code==400
 s=survey();s['answers'].update(D2=['Sari-sari store'],D3='Unsure');assert c.post('/api/surveys',json=s,headers=h).status_code==201
 h=login(c,'admin');row=c.get('/api/dashboard').json['surveys'][0];assert 'D2' not in row['answers']

def test_admin_workflow_export_and_disable(env):
 app,c=env;h=login(c);s=survey();s['respondent']='=HYPERLINK("bad")';c.post('/api/surveys',json=s,headers=h)
 h=login(c,'admin');r=c.post('/api/users',headers=h,json={'name':'New Person','username':'new','password':'long-password-2026','community':'Island','municipality_province':'Davao / Davao del Sur','language':'Cebuano','target':42});assert r.status_code==201
 u=next(x for x in c.get('/api/dashboard').json['users'] if x['username']=='new');assert u['target']==42
 assert c.patch('/api/users/'+u['id'],headers=h,json={'active':False,'target':50}).status_code==200
 assert c.post('/api/login',json={'username':'new','password':'long-password-2026'}).status_code==401
 assert c.patch('/api/surveys/'+s['id'],headers=h,json={'review':'verified'}).status_code==200
 r=c.get('/api/export');assert r.status_code==200 and "'=HYPERLINK" in r.text
 j=c.get('/api/export?format=json').json;assert len(j['surveys'])==1 and j['schema']['version']==SCHEMA['version']
 assert c.get('/sw.js').headers['Cache-Control']=='no-cache'

def test_schema_coverage(env):
 ids={q['id'] for s in SCHEMA['sections'] for q in s['questions']}
 counts={'A':10,'B':9,'C':3,'D':4,'E':5,'F':7,'G':5,'H':7,'I':3,'J':3,'K':8,'L':8}
 for letter,n in counts.items(): assert all(letter+str(i) in ids for i in range(1,n+1))
 for table in ['C_loads','D_equipment','I_profile','J_facilities','O_checklist']:assert table in ids
 assert 'Data Privacy Act of 2012' in SCHEMA['consent']

def test_delete_requires_admin_and_exact_confirmation(env):
 app,c=env;field_headers=login(c);s=survey()
 assert c.post('/api/surveys',json=s,headers=field_headers).status_code==201
 url='/api/surveys/'+s['id']
 assert c.delete(url,json={'confirm_respondent':s['respondent']},headers=field_headers).status_code==403
 c.post('/api/logout',headers=field_headers)
 assert c.delete(url,json={'confirm_respondent':s['respondent']}).status_code==401
 admin_headers=login(c,'admin')
 assert c.delete(url,json={'confirm_respondent':s['respondent']}).status_code==403
 for body in [{},{'confirm_respondent':'wrong'},{'confirm_respondent':s['respondent']+' '},['invalid']]:
  assert c.delete(url,json=body,headers=admin_headers).status_code==400
 assert len(c.get('/api/dashboard').json['surveys'])==1
 assert c.delete('/api/surveys/'+str(uuid.uuid4()),json={'confirm_respondent':s['respondent']},headers=admin_headers).status_code==404


def test_delete_one_updates_history_exports_and_counts_without_recreating(env):
 app,c=env;h=login(c);deleted=survey();retained=survey();retained['respondent']='BUC-002'
 for item in [deleted,retained]:assert c.post('/api/surveys',json=item,headers=h).status_code==201
 h=login(c,'admin')
 response=c.delete('/api/surveys/'+deleted['id'],json={'confirm_respondent':deleted['respondent']},headers=h)
 assert response.status_code==200 and response.json['id']==deleted['id']
 dashboard=c.get('/api/dashboard').json
 assert [s['id'] for s in dashboard['surveys']]==[retained['id']]
 assert next(u for u in dashboard['users'] if u['id']=='field')['completed']==1
 assert deleted['id'] not in c.get('/api/export').text
 assert deleted['respondent'] not in c.get('/api/export').text
 assert [s['id'] for s in c.get('/api/export?format=json').json['surveys']]==[retained['id']]
 h=login(c)
 assert [s['id'] for s in c.get('/api/my-surveys').json['surveys']]==[retained['id']]
 retry=c.post('/api/surveys',json=deleted,headers=h)
 assert retry.status_code==200 and retry.json['deleted'] is True
 assert [s['id'] for s in c.get('/api/my-surveys').json['surveys']]==[retained['id']]
 h=login(c,'other')
 assert c.post('/api/surveys',json=deleted,headers=h).status_code==409
 con=sqlite3.connect(app.config['DATABASE']);con.row_factory=sqlite3.Row
 tombstone=con.execute('SELECT * FROM survey_deletions').fetchone()
 assert set(tombstone.keys())=={'id','user_id','deleted_by','deleted_at'}
 assert tombstone['id']==deleted['id'] and tombstone['deleted_by']=='admin'
 assert con.execute('SELECT count(*) FROM users').fetchone()[0]==3
 con.close()
