"""Offline-upload contract, access control, consent, exports and photo lifecycle."""
import base64
import copy
import sqlite3
import uuid
from pathlib import Path
import pytest
from app import LEGACY_SCHEMA,MAX_PHOTO_BYTES,create_app,jpeg_info
from test_app import env,login,survey

JPEG=(Path(__file__).parent/'fixtures/equipment-photo.jpg').read_bytes()


def photo(image=JPEG):
 return {'id':str(uuid.uuid4()),'mime':'image/jpeg','data':base64.b64encode(image).decode('ascii')}


def interview():
 d=survey();d['photo_consent']='Yes';d['answers']={'D1':'Yes','C_loads':[{'appliance':'Electric fan','name':'Bedroom fan','qty':'1','photo':photo()}],'D_equipment':[{'name':'Sewing machine','qty':'2','power':'0.5 hp','hours':'6','months':'All year','fuel':'0','output':'50 garments','photo':photo()}]};return d


def test_photo_roundtrip_access_export_and_cascade_delete(env):
 app,c=env;h=login(c);d=interview();assert c.post('/api/surveys',json=d,headers=h).status_code==201
 urls=[f"/api/surveys/{d['id']}/photos/{d['answers'][key][0]['photo']['id']}" for key in ['C_loads','D_equipment']]
 expected=jpeg_info(JPEG)[0]
 for url in urls:
  r=c.get(url);assert r.status_code==200 and r.data==expected
  assert r.mimetype=='image/jpeg' and r.headers['Cache-Control']=='no-store'
  assert 'attachment' in c.get(url+'?download=1').headers['Content-Disposition']
 other=app.test_client();login(other,'other')
 for url in urls:assert other.get(url).status_code==404
 anon=app.test_client()
 for url in urls:assert anon.get(url).status_code==401
 # Retried sync is idempotent and does not duplicate photos.
 assert c.post('/api/surveys',json=d,headers=h).json['duplicate']
 with sqlite3.connect(app.config['DATABASE']) as con:assert con.execute('SELECT count(*) FROM survey_photos').fetchone()[0]==2
 h=login(c,'admin');rows=c.get('/api/dashboard').json['surveys'];assert len(rows)==1
 for key in ['C_loads','D_equipment']:
  attachment=rows[0]['answers'][key][0]['photo'];assert set(attachment)=={'id','mime','size','width','height'};assert attachment['width']==80 and attachment['height']==60
 for url in urls:assert c.get(url).status_code==200
 for path in ['/api/dashboard','/api/export','/api/export?format=json']:
  text=c.get(path).text;assert d['answers']['C_loads'][0]['photo']['data'] not in text and 'Sewing machine' in text
 assert c.delete('/api/surveys/'+d['id'],json={'confirm_respondent':d['respondent']},headers=h).status_code==200
 for url in urls:assert c.get(url).status_code==404
 with sqlite3.connect(app.config['DATABASE']) as con:assert con.execute('SELECT count(*) FROM survey_photos').fetchone()[0]==0
 h=login(c);assert c.post('/api/surveys',json=d,headers=h).json['deleted']
 with sqlite3.connect(app.config['DATABASE']) as con:assert con.execute('SELECT count(*) FROM survey_photos').fetchone()[0]==0


@pytest.mark.parametrize('change', ['no_consent','legacy','invalid_base64','not_jpeg','empty','too_large','large_dimensions','duplicate','descriptor_only','extra_key','bad_id'])
def test_invalid_or_unconsented_photo_fails_without_partial_records(env,change):
 app,c=env;h=login(c);d=interview();p=d['answers']['D_equipment'][0]['photo']
 if change=='no_consent':d['photo_consent']='No'
 elif change=='legacy':d['version']=LEGACY_SCHEMA['version']
 elif change=='invalid_base64':p['data']='not base64!'
 elif change=='not_jpeg':p.update(photo(b'not an image'))
 elif change=='empty':p['data']=''
 elif change=='too_large':p.update(photo(b'x'*(MAX_PHOTO_BYTES+1)))
 elif change=='large_dimensions':
  image=bytearray(JPEG);i=image.index(b'\xff\xc0');image[i+7:i+9]=(1281).to_bytes(2,'big');p.update(photo(bytes(image)))
 elif change=='duplicate':p['id']=d['answers']['C_loads'][0]['photo']['id']
 elif change=='descriptor_only':p.pop('data');p['size']=100
 elif change=='extra_key':p['filename']='sensitive-original.jpg'
 elif change=='bad_id':p['id']='../../other'
 r=c.post('/api/surveys',json=d,headers=h);assert r.status_code==400,r.json
 with sqlite3.connect(app.config['DATABASE']) as con:
  assert con.execute('SELECT count(*) FROM surveys').fetchone()[0]==0
  assert con.execute('SELECT count(*) FROM survey_photos').fetchone()[0]==0


def test_photo_budget_and_json_request_error(env):
 app,c=env;h=login(c);d=interview()
 # Valid JPEG with COM metadata increases payload size; metadata is not retained.
 block=b'\xff\xfe'+(60002).to_bytes(2,'big')+b'x'*60000
 large=JPEG[:2]+block*5+JPEG[2:]
 d['answers']['D_equipment']=[{'name':'Machine','photo':photo(large)} for _ in range(14)]
 r=c.post('/api/surveys',json=d,headers=h);assert r.status_code==400 and '4 MiB' in r.json['error']
 r=c.post('/api/surveys',data=b'x'*(6*1024*1024+1),content_type='application/json',headers=h);assert r.status_code==413 and r.is_json


def test_jpeg_metadata_is_removed_and_corruption_rejected():
 payload=b'Exif\x00\x00Camera GPS coordinates and original filename'
 segment=b'\xff\xe1'+(len(payload)+2).to_bytes(2,'big')+payload
 cleaned,dims=jpeg_info(JPEG[:2]+segment+JPEG[2:]);assert payload not in cleaned and dims==(80,60)
 # Metadata inserted after scan data is removed too.
 cleaned,dims=jpeg_info(JPEG[:-2]+segment+JPEG[-2:]);assert payload not in cleaned
 for broken in [JPEG[:-2],b'\xff\xd8\xff\xd9',JPEG[:20]+b'\xff\xd9']:
  with pytest.raises(ValueError):jpeg_info(broken)


def test_variable_business_equipment_and_existing_arrays(env):
 app,c=env;h=login(c)
 for rows in [[{}, {'power':'1 hp','qty':'0'}],[],[{'name':'Machine '+str(i),'qty':'1','hours':'8'} for i in range(100)]]:
  d=survey();d['answers']={'D1':'Yes','D_equipment':rows};r=c.post('/api/surveys',json=d,headers=h);assert r.status_code==201,r.json
 for rows in [[{'name':'Machine'}]*101,[{'qty':'-1'}],[{'hours':'25'}],[{'unrecognized':'value'}]]:
  d=survey();d['answers']={'D1':'Yes','D_equipment':rows};assert c.post('/api/surveys',json=d,headers=h).status_code==400
 login(c,'admin');assert len(c.get('/api/dashboard').json['surveys'])==3
 # Restart/additive schema migration preserves data and photo tables.
 again=create_app({'TESTING':True,'SECRET_KEY':'testing-only','DATABASE':app.config['DATABASE']});ac=again.test_client();login(ac,'admin');assert len(ac.get('/api/dashboard').json['surveys'])==3
