"""Mobile inventory cards and photos across offline reload, failed upload, retry and dashboard."""
import os,sys,socket,subprocess,tempfile,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];artifacts=Path(tempfile.mkdtemp(prefix='gridfield-equipment-photos-'))
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
  browser=p.chromium.launch(**launch);ctx=browser.new_context(viewport={'width':390,'height':844});page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(url);page.get_by_role('button',name='Try field collection').click();page.get_by_role('heading',name='Start with a conversation.').wait_for();page.wait_for_function('()=>state.ready')
  def cell(q,col,row=0):return page.locator(f'[data-q="{q}"][data-col="{col}"][data-row="{row}"]')
  def attach(q,row=0):
   page.locator(f'#photo-{q}-{row}-file').set_input_files(str(ROOT/'tests/fixtures/equipment-photo.jpg'))
   page.wait_for_function('()=>!state.photoBusy');page.locator('.inventory-photo-preview').first.wait_for()
  def resume():
   page.get_by_role('heading',name='Start with a conversation.').wait_for();page.locator('[data-action="menu"]').click();page.locator('[data-view="drafts"]').first.click();page.locator('[data-resume]').first.click()
  page.locator('[data-start="household"]').click();page.locator('input[name="consent"][value="Yes"]').check()
  for name in ['gps_consent','photo_consent','audio_consent']:page.locator(f'input[name="{name}"][value="No"]').check()
  page.locator('[data-step="3"]').click();page.locator('[data-add-appliance]').click();cell('C_loads','appliance').select_option('Electric fan');assert page.locator('[data-photo-picker]').count()==0
  page.locator('[data-step="0"]').click();page.locator('input[name="photo_consent"][value="Yes"]').check();page.locator('[data-step="3"]').click()
  # Old fixed-position rows display without rewriting; editing retains zeroes and old time strings.
  page.evaluate("async()=>{state.draft.answers.C_loads=[{qty:'0',time:'m / e'},{},{},{qty:'2',watts:'45'}];await persistDraft();render()}")
  assert page.locator('.appliance-card').count()==2
  assert page.evaluate("()=>!('appliance' in state.draft.answers.C_loads[0])")
  page.locator('[data-appliance-index="0"] summary').click();assert cell('C_loads','time',0).input_value()=='m / e';assert cell('C_loads','qty',0).input_value()=='0'
  page.locator('[data-appliance-index="1"] summary').click();ctx.set_offline(True);attach('C_loads',1)
  photo_id=page.evaluate("()=>state.draft.answers.C_loads[1].photo.id");assert page.evaluate("()=>state.draft.answers.C_loads[1].appliance")=='Electric fan'
  assert page.locator('#photo-C_loads-1-camera').get_attribute('capture')=='environment'
  # Replacement and invalid file leave the previous photo available until a successful save.
  attach('C_loads',1);assert page.evaluate("()=>state.draft.answers.C_loads[1].photo.id")!=photo_id
  photo_id=page.evaluate("()=>state.draft.answers.C_loads[1].photo.id")
  page.locator('#photo-C_loads-1-file').set_input_files({'name':'broken.jpg','mimeType':'image/jpeg','buffer':b'broken image'})
  page.wait_for_function('()=>!state.photoBusy');assert page.evaluate("()=>state.draft.answers.C_loads[1].photo.id")==photo_id
  # Storage failure on replacement retains the earlier durable image.
  page.evaluate("()=>{window.originalLocalWrite=localWrite;localWrite=async()=>{throw Error('Test quota failure')}}")
  attach('C_loads',1);assert page.evaluate("()=>state.draft.answers.C_loads[1].photo.id")==photo_id
  page.evaluate('()=>{localWrite=window.originalLocalWrite}')
  page.locator('[data-remove-photo="C_loads"]').click();page.get_by_role('button',name='Keep photo',exact=True).click();assert page.locator('.inventory-photo-preview').count()==1
  page.locator('[data-remove-photo="C_loads"]').click();page.locator('#confirm-remove-photo').click();page.wait_for_function("()=>!state.draft.answers.C_loads[1].photo&&!document.querySelector('#modal').open");attach('C_loads',1)
  page.locator('.question').filter(has=page.locator('[data-add-appliance]')).screenshot(path=str(artifacts/'appliance-photo-mobile.png'))
  page.locator('[data-step="4"]').click();page.locator('input[data-q="D1"][value="Yes"]').check();assert page.locator('[data-add-equipment]').count()==1
  for i,name in enumerate(['Sewing machine','Ice maker','Coffee grinder','Water pump']):
   page.locator('[data-add-equipment]').click();cell('D_equipment','name',i).fill(name);cell('D_equipment','qty',i).fill('1');cell('D_equipment','power',i).fill('0.5 hp');cell('D_equipment','hours',i).fill('8');cell('D_equipment','months',i).fill('All year');cell('D_equipment','fuel',i).fill('0');cell('D_equipment','output',i).fill('50 units/month')
  assert page.locator('.equipment-card').count()==4
  page.locator('[data-equipment-index="1"] summary').click();attach('D_equipment',1)
  page.locator('[data-remove-equipment="1"]').click();page.get_by_role('button',name='Keep equipment').click();assert page.locator('.equipment-card').count()==4
  page.locator('[data-equipment-index="3"] summary').click();page.locator('[data-remove-equipment="3"]').click();page.locator('#confirm-remove-equipment').click();page.wait_for_function("()=>state.draft.answers.D_equipment.length===3")
  for width in [320,390,768,1440]:
   page.set_viewport_size({'width':width,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
  page.set_viewport_size({'width':390,'height':844});page.locator('[data-equipment-index="1"] summary').click();page.evaluate("()=>{document.body.classList.remove('menu-open');document.querySelectorAll('.equipment-card').forEach((e,i)=>e.open=i===1)}");page.locator('.question').filter(has=page.locator('[data-add-equipment]')).screenshot(path=str(artifacts/'business-equipment-mobile.png'))
  # Consent withdrawal is explicit; cancel keeps the photographs.
  page.locator('[data-step="0"]').click();page.locator('input[name="photo_consent"][value="No"]').click();page.get_by_role('button',name='Keep photos and consent').click();assert page.locator('input[name="photo_consent"][value="Yes"]').is_checked()
  page.evaluate('()=>saveChain');page.reload();resume();page.locator('[data-step="3"]').click();page.locator('[data-add-appliance]').wait_for();assert page.locator('.inventory-photo-preview').count()==1
  page.locator('[data-step="4"]').click();page.locator('[data-add-equipment]').wait_for();assert page.locator('.equipment-card').count()==3 and page.locator('.inventory-photo-preview').count()==1
  reference=page.evaluate('()=>state.draft.respondent');identifier=page.evaluate('()=>state.draft.id')
  page.locator('[data-step]').last.click();page.locator('#review-confirm').check();page.get_by_role('button',name='Finish interview').click();page.wait_for_function("()=>state.local.some(d=>d.status==='queued')")
  assert page.evaluate("()=>state.local[0].answers.D_equipment[1].photo.data.length>0")
  # Offline queue and image bytes survive an app restart.
  page.reload();page.get_by_role('heading',name='Start with a conversation.').wait_for();assert page.evaluate("()=>state.local[0].answers.C_loads[1].photo.data.length>0")
  ctx.route('**/api/surveys',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"Temporary test upload failure"}'))
  ctx.set_offline(False);page.wait_for_function("()=>!state.syncing&&state.local.some(d=>d.sync_error)")
  assert page.evaluate("()=>state.local[0].answers.D_equipment[1].photo.data.length>0")
  ctx.unroute('**/api/surveys');page.locator('[data-action="menu"]').click();page.locator('[data-view="drafts"]').first.click();page.get_by_role('button',name='Sync now').click();page.wait_for_function('()=>!state.syncing&&state.local.length===0')
  admin=browser.new_context(viewport={'width':1440,'height':1000});ap=admin.new_page();ap.on('pageerror',lambda e:errors.append(str(e)));ap.goto(url);ap.get_by_role('button',name='Open dashboard').click();ap.get_by_role('heading',name='Every conversation counts.').wait_for()
  record=next(d for d in admin.request.get(url+'/api/dashboard').json()['surveys'] if d['id']==identifier)
  assert record['answers']['C_loads'][0]['qty']=='0' and record['answers']['C_loads'][0]['time']=='m / e'
  assert len(record['answers']['D_equipment'])==3 and record['answers']['D_equipment'][1]['name']=='Ice maker'
  ap.locator('[data-view="responses"]').first.click();ap.locator('[data-survey="'+identifier+'"]').first.click();assert ap.locator('.synced-photo').count()==2
  ap.locator('.synced-photo').last.scroll_into_view_if_needed();ap.wait_for_function("()=>[...document.querySelectorAll('.synced-photo img')].every(i=>i.complete&&i.naturalWidth>0)")
  for img in ap.locator('.synced-photo img').all():
   resp=admin.request.get(url+img.get_attribute('src'));assert resp.status==200 and resp.headers['cache-control']=='no-store'
  ap.screenshot(path=str(artifacts/'equipment-photos-dashboard.png'),full_page=True)
  assert not errors,errors;browser.close()
 print('PASS: appliance and business equipment cards; consent; camera/gallery controls; offline photos, replacement/removal, quota failure rollback, restart, failed sync/retry, dashboard images and responsive layouts.')
 print('Browser artifacts:',artifacts)
finally:server.terminate();server.wait(timeout=10);log.close()
