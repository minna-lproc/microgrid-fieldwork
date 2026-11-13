import json, sqlite3, uuid
import pytest
from app import SCHEMA,LEGACY_SCHEMA,SCHEMAS,create_app,validate_survey
from test_app import env,login,survey


def post(c,h,**updates):
 d=survey();d.update(updates)
 return c.post('/api/surveys',json=d,headers=h),d


def test_complete_revised_questionnaire_and_codebook():
 counts={'A':10,'B':11,'C':4,'D':8,'E':7,'F':10,'G':5,'H':12,'I':4,'J':3,'K':13,'L':13}
 q={q['id']:q for sec in SCHEMA['sections'] for q in sec['questions']}
 assert sum(counts.values())==100
 for letter,n in counts.items():assert all(letter+str(i) in q for i in range(1,n+1))
 assert len(q['O_checklist']['rows'])==15
 assert q['J_equipment']['type']=='repeat_table' and len(q['J_equipment']['rows'])==5
 assert {'load_type','months','starting_current','source'}<={f['id'] for f in q['C_loads']['columns']}
 assert 'This survey is not a commitment' in SCHEMA['consent']
 assert isinstance(SCHEMA.get('protocol'), list)
 assert all(isinstance(item, str) for item in SCHEMA['protocol'])
 assert 'legal' in {f['id'] for f in q['L2']['fields']}
 assert LEGACY_SCHEMA['version']!=SCHEMA['version'] and len(SCHEMAS)==2


def test_revised_extended_answers_roundtrip(env):
 app,c=env;h=login(c)
 answers={'B5':{'interruptions':'3','longest':'8','total':'20'},'B10':['Brownouts (dim lights, appliances not working properly)'],'B11':'Sometimes','C_loads':[{'qty':'1','watts':'90','hours':'12','time':'E/N','planned':'1','load_type':'ES','months':'All year','starting_current':'4.5','source':'N'}],'C4':'Cold storage','D1':'Yes','D2':['Fish drying','Boat charging'],'D_equipment':[{'name':'Cold room','output':'200 kg/month'}],'D5':['Morning'],'D6':{'peak':'100 kg','lean':'30 kg','market':'Within the community'},'D7':['Capital'],'D8':'Yes','E6':['Lighting'],'E7':'6–12 hours','F8':{'pattern':'Varies by season','lowest':'June','best':'December'},'F9':['Borrow'],'F10':[{'terms':'Project-team discussion: first 30 kWh at ₱4/kWh','kwh':'30','response':'Depends'}],'H8':['Local jobs'],'H9':'Yes','H10':'Yes, shared ownership with an operator','H11':'Yes, and I would be heard','H12':['Community meeting'],'A7_details':'Consultation indicator only'}
 r,d=post(c,h,answers=answers);assert r.status_code==201,r.json
 h=login(c,'admin');saved=next(x for x in c.get('/api/dashboard').json['surveys'] if x['id']==d['id'])
 assert saved['answers']==answers and saved['version']==SCHEMA['version']
 export=c.get('/api/export?format=json').json
 assert set(export['schemas'])==set(SCHEMAS)
 assert saved['metadata']['language']=='Cebuano'
 assert 'Consultation indicator only' in c.get('/api/export').text


def test_community_repeat_facility_and_governance(env):
 app,c=env;h=login(c)
 r,d=post(c,h,instrument='community',answers={'I4':'Yes (copy or attach)','J_facilities':[{'present':'Y','critical_kw':'2','backup_hours':'48','source':'M'}],'J_equipment':[{'name':'School A','rows':[{'equipment':'Emergency light','qty':'5','watts':'10','schedule':'Night','critical':'Y','backup_hours':'48','source':'N'}]},{'name':'Health station','rows':[{'equipment':'Vaccine refrigerator','qty':'1','watts':'100','critical':'Y','backup_hours':'72','source':'B'}]}],'K9':{'solar':'June–August','hydro':'Dry: March; flood: July'},'K10':'Irrigation; verify ecological flow','K13':'Approved recycler, LGU to clarify costs','L1':['Indigenous Peoples Mandatory Representative (IPMR)','Indigenous Political Structure / customary leaders'],'L1_stakeholders':[{'name':'Representative','role':'Formal role','contact':'Project-authorised contact reference'}],'L2':{'legal':'Confirm FPIC applicability','customary':'Customary council deliberation','household':'Individual voluntary interview consent'},'L6':['Electricians / technicians in the community','Trained solar or generator operators'],'L6_details':'3 skilled people','L7':'Yes, with support','L7_details':'Technician: paid; committee: stipend','L9':'Shared:','L9_details':'Operator and cooperative','L13':'Sometimes'})
 assert r.status_code==201,r.json
 h=login(c,'admin');saved=c.get('/api/dashboard').json['surveys'][0]
 assert len(saved['answers']['J_equipment'])==2
 assert saved['answers']['L2']['legal']=='Confirm FPIC applicability'


@pytest.mark.parametrize('answers',[
 {'B5':{'longest':'20','total':'10'}}, {'B5':{'total':'721'}},
 {'C_loads':[{'load_type':'invented'}]}, {'C_loads':[{'source':'Z'}]},
 {'C_loads':[{'hours':'25'}]}, {'C_loads':[{'starting_current':'-1'}]},
 {'F10':[{'response':'Yes'}]}, {'F10':[{}, {'terms':'Discounted rate','response':'Yes','kwh':'10'}]},
 {'D6':{'market':'invented'}}, {'F8':{'pattern':'invented'}}
])
def test_revised_validation_rejects_invalid_structured_answers(env,answers):
 app,c=env;h=login(c);r,_=post(c,h,answers=answers);assert r.status_code==400,r.json


def test_revised_business_skip_removes_all_followups(env):
 app,c=env;h=login(c);r,d=post(c,h,answers={'D1':'No (skip to Part E)','D5':['Morning'],'D6':{'peak':'10 kg'},'D7':['Capital'],'D8':'Yes','D8_details':'Discard this'})
 assert r.status_code==201
 h=login(c,'admin');assert c.get('/api/dashboard').json['surveys'][0]['answers']=={'D1':'No (skip to Part E)'}


def test_separate_consent_metadata_and_observation_rules(env):
 app,c=env;h=login(c)
 for updates in [{'photo_consent':''},{'audio_consent':''},{'metadata':{'municipality_province':'Davao'}},{'metadata':{'municipality_province':'Davao','language':'Cebuano','replacement':'Yes'}},{'instrument':'observation','answers':{'O_checklist':[{}, {}, {}, {}, {}, {}, {'answer':'Yes'}]},'photo_consent':'No'}]:
  r,_=post(c,h,**updates);assert r.status_code==400,r.json
 r,d=post(c,h,instrument='observation',photo_consent='Yes',audio_consent='No',answers={'O_checklist':[{'answer':'Yes','value':'Length 50 m; width 30 m; area 1500 m²'}, {}, {}, {}, {}, {}, {'answer':'Yes','notes':'External consented photo reference'}]})
 assert r.status_code==201,r.json
 r,declined=post(c,h,consent='No',metadata={'field_notes':'must not be retained'},answers={'A1':'Female'},photo_consent='Yes',audio_consent='Yes')
 assert r.status_code==201
 h=login(c,'admin');row=next(x for x in c.get('/api/dashboard').json['surveys'] if x['id']==declined['id'])
 assert row['answers']=={} and row['metadata']=={} and row['photo_consent']=='Not asked'


def test_gps_separate_restricted_and_coarsened_exports(env):
 app,c=env;h=login(c);location={'lat':7.123456789,'lng':125.987654321,'accuracy':12.34}
 r,d=post(c,h,gps_consent='Yes',location=location);assert r.status_code==201
 assert c.get('/api/surveys/'+d['id']+'/location').status_code==403
 con=sqlite3.connect(app.config['DATABASE'])
 assert con.execute('SELECT location FROM surveys WHERE id=?',(d['id'],)).fetchone()[0]=='null'
 assert json.loads(con.execute('SELECT coordinates FROM survey_locations WHERE survey_id=?',(d['id'],)).fetchone()[0])==location;con.close()
 h=login(c,'admin');row=c.get('/api/dashboard').json['surveys'][0]
 assert 'location' not in row and row['coarse_location']['lat']==7.12 and row['coarse_location']['lng']==125.99
 assert c.get('/api/surveys/'+d['id']+'/location').json['location']==location
 for url in ['/api/export','/api/export?format=json','/api/dashboard']:
  text=c.get(url).text;assert '7.123456789' not in text and '125.987654321' not in text
 assert c.delete('/api/surveys/'+d['id'],headers=h,json={'confirm_respondent':d['respondent']}).status_code==200
 assert c.get('/api/surveys/'+d['id']+'/location').status_code==404


def test_old_offline_submissions_keep_old_schema_and_permissions(env):
 app,c=env;h=login(c);d=survey();d['version']=LEGACY_SCHEMA['version'];d.pop('metadata');d.pop('photo_consent');d.pop('audio_consent');d['answers']={'L2':'Earlier free-text consent process'};d['instrument']='community'
 assert c.post('/api/surveys',json=d,headers=h).status_code==201
 h=login(c,'admin');row=c.get('/api/dashboard').json['surveys'][0]
 assert row['version']==LEGACY_SCHEMA['version'] and row['answers']['L2']=='Earlier free-text consent process'
 assert row['photo_consent']=='Not asked' and row['audio_consent']=='Not asked' and row['metadata']=={}
 # Older pilot choices do not silently become the revised choices.
 h=login(c);d['id']=str(uuid.uuid4());d['instrument']='household';d['answers']={'D1':'Yes','D2':['Boat charging']}
 assert c.post('/api/surveys',json=d,headers=h).status_code==400
 d['version']='unrecognised-version';assert c.post('/api/surveys',json=d,headers=h).status_code==400


def test_repeatable_migration_preserves_old_records_and_moves_gps(env):
 app,c=env;h=login(c);r,d=post(c,h);assert r.status_code==201
 point={'lat':7.11112222,'lng':125.22223333,'accuracy':20}
 con=sqlite3.connect(app.config['DATABASE'])
 con.execute('UPDATE surveys SET version=?,location=? WHERE id=?',(LEGACY_SCHEMA['version'],json.dumps(point),d['id']))
 for column in ['metadata','photo_consent','audio_consent']:con.execute('ALTER TABLE surveys DROP COLUMN '+column)
 con.execute('DROP TABLE survey_locations');con.commit();con.close()
 config={'TESTING':True,'SECRET_KEY':'testing-only','DATABASE':app.config['DATABASE']}
 for _ in range(2):
  migrated=create_app(config);client=migrated.test_client();login(client,'admin')
  row=client.get('/api/dashboard').json['surveys'][0]
  assert row['id']==d['id'] and row['version']==LEGACY_SCHEMA['version'] and row['photo_consent']=='Not asked'
  assert client.get('/api/surveys/'+d['id']+'/location').json['location']==point
  con=sqlite3.connect(app.config['DATABASE']);assert con.execute('SELECT count(*) FROM survey_locations').fetchone()[0]==1;assert con.execute('SELECT count(*) FROM users').fetchone()[0]==3;con.close()
