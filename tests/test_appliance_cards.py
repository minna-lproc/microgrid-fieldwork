import json
import pytest
from app import LEGACY_SCHEMA,SCHEMA
from test_app import env,login,survey


def submit(c,h,rows,version=None):
 d=survey();d['answers']={'C_loads':rows}
 if version:d['version']=version
 return c.post('/api/surveys',json=d,headers=h),d


def test_repeated_appliance_categories_and_multiple_other_items_roundtrip(env):
 app,c=env;h=login(c)
 rows=[{'appliance':'Electric fan','name':'Bedroom fan','qty':'1','watts':'30','hours':'6','time':'E/N','planned':'0','load_type':'DF','months':'All year','starting_current':'','source':'N','notes':'Measured label'}, {'appliance':'Electric fan','name':'Shop fan','qty':'2','watts':'50','hours':'8','time':'M/A','load_type':'DI','source':'R'}, {'appliance':'Other','name':'Incubator','qty':'1','watts':'100','hours':'24','time':'M/A/E/N','load_type':'ES','source':'N'}, {'appliance':'Other','name':'Sewing machine','qty':'1','watts':'80','time':'A','notes':'Separate productive use'}]
 r,d=submit(c,h,rows);assert r.status_code==201,r.json
 h=login(c,'admin');row=c.get('/api/dashboard').json['surveys'][0];assert row['answers']['C_loads']==rows
 exported=c.get('/api/export?format=json').json['surveys'][0]['answers']['C_loads'];assert exported==rows
 text=c.get('/api/export').text;assert 'Incubator' in text and 'Shop fan' in text and 'Sewing machine' in text


def test_old_indexed_arrays_and_time_strings_are_not_rewritten(env):
 app,c=env;h=login(c);rows=[{'qty':'0','time':'m / e','notes':'Original wording'},{},{},{'qty':'2','watts':'45','time':'E/N'}]
 r,d=submit(c,h,rows);assert r.status_code==201,r.json
 h=login(c,'admin');assert c.get('/api/dashboard').json['surveys'][0]['answers']['C_loads']==rows
 h=login(c);r,d=submit(c,h,[{'appliance':'Electric fan','qty':'2','time':'m / e'}]);assert r.status_code==201
 # Old questionnaire drafts can also use the mobile presentation without new scientific fields.
 r,d=submit(c,h,[{'appliance':'Other','notes':'Existing description','time':'E/N'}],LEGACY_SCHEMA['version']);assert r.status_code==201,r.json


@pytest.mark.parametrize('rows',[
 [{'appliance':''}], [{'appliance':'Unlisted category','qty':'1'}],
 [{'appliance':'Other'}], [{'appliance':'Other','name':'x'*201}],
 [{'appliance':'Phone charger','qty':'-1'}], [{'appliance':'Phone charger','qty':'1.5'}],
 [{'appliance':'Phone charger','hours':'25'}], [{'appliance':'Phone charger','time':'midday'}],
 [{'appliance':'Phone charger','load_type':'unknown'}], [{'appliance':'Phone charger','source':'unknown'}],
 [{'appliance':'Phone charger','extra_column':'No'}], [{'appliance':'Phone charger'},{'qty':'2'}],
 [{'appliance':'Phone charger'}]*101,
])
def test_invalid_named_inventory_is_rejected(env,rows):
 app,c=env;h=login(c);r,_=submit(c,h,rows);assert r.status_code==400,r.json


def test_maximum_named_rows_and_all_time_combinations(env):
 app,c=env;h=login(c)
 q=next(q for s in SCHEMA['sections'] for q in s['questions'] if q['id']=='C_loads')
 codes=next(f for f in q['columns'] if f['id']=='time')['options'];assert len(codes)==15
 rows=[{'appliance':'Phone charger','name':'Charger '+str(i),'qty':'1','time':codes[i%len(codes)]} for i in range(100)]
 r,_=submit(c,h,rows);assert r.status_code==201,r.json
 assert submit(c,h,[{}]*14)[0].status_code==400
 assert submit(c,h,[])[0].status_code==201
