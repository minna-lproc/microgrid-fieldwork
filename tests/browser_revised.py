"""Revised forms, GPS separation, legacy IndexedDB upgrade and offline version compatibility."""
import os,sys,socket,subprocess,tempfile,time,urllib.request,json,uuid
from pathlib import Path
from datetime import datetime,timezone
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];artifacts=Path(tempfile.mkdtemp(prefix='gridfield-revised-'))
env=dict(os.environ,DATABASE=str(artifacts/'test.sqlite'),DEMO='1')
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
env['PORT']=str(port)
subprocess.run([sys.executable,'-m','flask','--app','app','seed-demo'],cwd=ROOT,env=env,check=True,capture_output=True)
log=open(artifacts/'server.log','w');server=subprocess.Popen([sys.executable,'app.py'],cwd=ROOT,env=env,stdout=log,stderr=log);url=f'http://127.0.0.1:{port}'
try:
 for _ in range(100):
  try:urllib.request.urlopen(url,timeout=1);break
  except Exception:time.sleep(.1)
 with sync_playwright() as p:
  launch={'headless':True}
  if os.environ.get('CHROMIUM_PATH'):launch['executable_path']=os.environ['CHROMIUM_PATH']
  browser=p.chromium.launch(**launch);ctx=browser.new_context(viewport={'width':390,'height':844},geolocation={'latitude':7.123456,'longitude':125.987654},permissions=['geolocation']);page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(url);page.get_by_role('button',name='Try field collection').click();page.get_by_role('heading',name='Start with a conversation.').wait_for()
  def start(kind,reference,gps='No',photo='No'):
   if page.locator('[data-start]').count()==0:
    page.locator('[data-action="menu"]').click();page.locator('[data-view="collect"]').first.click()
   page.locator('[data-start="'+kind+'"]').click();assert page.locator('#respondent').input_value().startswith('maria-');assert page.locator('#meta-municipality_province').input_value()=='Davao City / Davao del Sur';assert page.locator('#meta-language').input_value()=='Cebuano';page.locator('input[name="consent"][value="Yes"]').check();page.locator('input[name="gps_consent"][value="'+gps+'"]').check();page.locator('input[name="photo_consent"][value="'+photo+'"]').check();page.locator('input[name="audio_consent"][value="No"]').check()
  def finish():
   page.locator('[data-step]').last.click();page.locator('#review-confirm').check();page.get_by_role('button',name='Finish interview').click();page.wait_for_function("() => state.view==='drafts' && state.draft===null && !state.syncing && state.local.every(x=>x.status!=='queued')")
  def cell(q,col,row=0,group=None):
   return page.locator(f'[data-q="{q}"][data-col="{col}"][data-row="{row}"]'+(f'[data-group="{group}"]' if group is not None else ''))
  def field(q,col):return page.locator(f'[data-q="{q}"][data-col="{col}"]')
  start('household','REVISED-HH-001',gps='Yes');page.get_by_role('button',name='Capture GPS location').click();page.wait_for_function("() => document.querySelector('#gps-status').textContent.includes('7.12346')")
  # A record's answers and dwelling coordinates persist in different stores.
  stored=page.evaluate("""async()=>{const d=await new Promise(r=>{const q=indexedDB.open('gridfield-v1',3);q.onsuccess=()=>r(q.result)});const read=n=>new Promise(r=>{const q=d.transaction(n).objectStore(n).getAll();q.onsuccess=()=>r(q.result)});return {surveys:await read('surveys'),locations:await read('locations')}}""")
  assert 'location' not in stored['surveys'][0] and len(stored['locations'])==1
  page.locator('[data-step="2"]').click();field('B5','interruptions').fill('3');field('B5','longest').fill('8');field('B5','total').fill('20');page.locator('input[data-q="B10"]').first.check()
  page.locator('[data-step="3"]').click();cell('C_loads','qty').fill('1');cell('C_loads','watts').fill('15');cell('C_loads','hours').fill('4');cell('C_loads','time').fill('E');cell('C_loads','load_type').select_option('ES');cell('C_loads','months').fill('All year');cell('C_loads','source').select_option('N');page.locator('textarea[data-q="C4"]').fill('Cold storage')
  page.screenshot(path=str(artifacts/'revised-appliances-mobile.png'),full_page=True)
  page.locator('[data-step="4"]').click();page.locator('input[data-q="D1"][value="Yes"]').check();page.locator('input[data-q="D2"][value="Boat charging"]').check();page.locator('input[data-q="D5"][value="Morning"]').check();page.locator('input[data-q="D1"][value^="No"]').check();page.wait_for_function("() => !document.querySelector('[data-q=\"D5\"]')");assert page.locator('[data-q="D5"]').count()==0
  page.locator('[data-step="6"]').click();field('F8','pattern').select_option('Varies by season');field('F8','lowest').fill('June');field('F8','best').fill('December');cell('F10','terms').fill('Discussion: first 30 kWh at ₱4/kWh');cell('F10','kwh').fill('30');cell('F10','response').select_option('Depends');finish()
  start('community','REVISED-COMM-001');page.locator('[data-step="2"]').click();page.locator('[data-add-facility]').click();page.locator('[data-facility-name][data-group="0"]').fill('Health station A');cell('J_equipment','equipment',group=0).fill('Vaccine refrigerator');cell('J_equipment','qty',group=0).fill('1');cell('J_equipment','watts',group=0).fill('100');cell('J_equipment','critical',group=0).select_option('Y');cell('J_equipment','backup_hours',group=0).fill('72');cell('J_equipment','source',group=0).select_option('N');page.locator('[data-add-facility]').click();page.locator('[data-facility-name][data-group="1"]').fill('School B');cell('J_equipment','equipment',group=1).fill('Emergency lights');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(artifacts/'facility-inventory-mobile.png'),full_page=True)
  page.locator('[data-step="3"]').click();field('K9','solar').fill('June to August');page.locator('[data-step="4"]').click();field('L2','legal').fill('Confirm FPIC applicability under NCIP rules');field('L2','customary').fill('Customary leaders deliberate separately');field('L2','household').fill('Voluntary interview consent');page.locator('input[data-q="L6"]').first.check();page.locator('input[data-q="L6"]').nth(1).check();finish()
  start('observation','REVISED-SITE-001',photo='Yes');page.locator('[data-step="1"]').click();cell('O_checklist','answer',0).select_option('Yes');cell('O_checklist','value',0).fill('Generator: 10 kW; condition fair');cell('O_checklist','answer',6).select_option('Yes');cell('O_checklist','notes',6).fill('External photo reference, separately consented');finish()
  admin=browser.new_context(viewport={'width':1440,'height':1000});ap=admin.new_page();ap.on('pageerror',lambda e:errors.append(str(e)));ap.goto(url);ap.get_by_role('button',name='Open dashboard').click();ap.get_by_role('heading',name='Every conversation counts.').wait_for();data=admin.request.get(url+'/api/dashboard').json();new=[r for r in data['surveys'] if r.get('reference_mode')=='allocated-v1'];assert len(new)==3
  hh=next(r for r in new if r['instrument']=='household');assert set(k for k in hh['answers'] if k.startswith('D'))=={'D1'};assert 'location' not in hh and hh['has_location'];assert hh['coarse_location']['lat']==7.12
  ap.locator('[data-view="responses"]').first.click();ap.locator('#version-filter').select_option(json.loads((ROOT/'static/survey.json').read_text(encoding='utf-8-sig'))['version']);assert ap.locator('tbody tr').count()==3;ap.locator('[data-survey="'+hh['id']+'"]').first.click();ap.get_by_role('button',name='View restricted exact GPS').click();ap.locator('#restricted-gps').filter(has_text='7.123456').wait_for();ap.get_by_role('button',name='Close dialog').click();ap.locator('[data-view="insights"]').first.click();ap.get_by_text('Tariff scenarios — responses by exact terms').wait_for();ap.screenshot(path=str(artifacts/'revised-dashboard.png'),full_page=True)
  # Simulate an older phone upgrading from the original one-store IndexedDB.
  legacy=browser.new_context(viewport={'width':390,'height':844});lp=legacy.new_page();lp.on('pageerror',lambda e:errors.append(str(e)));lp.goto(url+'/static/icon.svg');u=legacy.request.post(url+'/api/login',data={'username':'maria','password':'FieldworkDemo!2026'}).json()['user'];now=datetime.now(timezone.utc).isoformat();queued_id=str(uuid.uuid4());draft_id=str(uuid.uuid4())
  base=dict(owner=u['id'],version='2026-pilot-1',community='Bucana',consent='Yes',gps_consent='Yes',location={'lat':7.112233,'lng':125.445566,'accuracy':20},started_at=now,updated_at=now,step=1)
  old=[dict(base,id=queued_id,respondent='LEGACY-QUEUED',instrument='community',answers={'L2':'Earlier free-text process'},status='queued',completed_at=now),dict(base,id=draft_id,respondent='LEGACY-DRAFT',instrument='household',answers={'A1':'Female'},status='draft')]
  lp.evaluate("""async arg=>{localStorage.setItem('gridfield-user',JSON.stringify(arg.user));await new Promise((resolve,reject)=>{const r=indexedDB.open('gridfield-v1',1);r.onupgradeneeded=()=>r.result.createObjectStore('surveys',{keyPath:'id'});r.onsuccess=()=>{const tx=r.result.transaction('surveys','readwrite');arg.records.forEach(x=>tx.objectStore('surveys').put(x));tx.oncomplete=()=>{r.result.close();resolve()};tx.onerror=()=>reject(tx.error)}})}""",{'user':u,'records':old})
  lp.goto(url);lp.get_by_role('heading',name='Start with a conversation.').wait_for();lp.wait_for_function("() => document.querySelector('.notice').textContent.includes('Offline app files are ready')");lp.wait_for_function("() => !state.syncing")
  migrated=lp.evaluate("""async()=>{const records=await storage('readonly',s=>s.getAll());const points=await storage('readonly',s=>s.getAll(),'locations');return {records,points}}""");assert len(migrated['records'])==1 and 'location' not in migrated['records'][0] and len(migrated['points'])==1
  legacy.set_offline(True);lp.locator('[data-action="menu"]').click();lp.locator('[data-view="drafts"]').first.click();lp.locator('[data-resume="'+draft_id+'"]').click();assert lp.locator('input[data-q="A1"][value="Female"]').is_checked();lp.locator('[data-step="0"]').click();assert lp.locator('#meta-language').count()==0 and lp.locator('input[name="photo_consent"]').count()==0;lp.locator('[data-step]').last.click();lp.locator('#review-confirm').check();lp.get_by_role('button',name='Finish interview').click();lp.get_by_text('Waiting to sync',exact=True).wait_for();lp.reload();lp.get_by_role('heading',name='Start with a conversation.').wait_for();legacy.set_offline(False);lp.wait_for_function("() => state.local.length===0")
  all_rows=admin.request.get(url+'/api/dashboard').json()['surveys'];old_rows=[r for r in all_rows if r['id'] in [queued_id,draft_id]];assert len(old_rows)==2 and all(r['version']=='2026-pilot-1' and r['photo_consent']=='Not asked' for r in old_rows);assert next(r for r in old_rows if r['id']==queued_id)['answers']['L2']=='Earlier free-text process';assert not errors,errors
  browser.close()
 print('PASS: revised household/community/observation flows, repeat inventories, metadata and separate consents, GPS separation, version reporting, legacy IndexedDB upgrade and offline resume/sync.')
 print('Browser artifacts:',artifacts)
finally:server.terminate();server.wait(timeout=10);log.close()
