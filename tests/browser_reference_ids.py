"""Generated IDs and admin assignments through real online/offline browser flows."""
import os,sys,socket,subprocess,tempfile,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];artifacts=Path(tempfile.mkdtemp(prefix='gridfield-reference-'))
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
  args={'headless':True}
  if os.environ.get('CHROMIUM_PATH'):args['executable_path']=os.environ['CHROMIUM_PATH']
  browser=p.chromium.launch(**args);errors=[]
  def watch(page):page.on('pageerror',lambda e:errors.append(str(e)));return page
  def ready(page):page.wait_for_function("() => state.references?.length===3 && state.references.every(x=>x.status==='ready')")
  def collect(page,kind):
   if page.locator('[data-start]').count()==0:
    if page.viewport_size['width']<700:page.locator('[data-action="menu"]').click()
    page.locator('[data-view="collect"]').first.click()
   page.locator('[data-start="'+kind+'"]').click();page.locator('#respondent').wait_for()
   return page.locator('#respondent').input_value()
  def close_draft(page):page.get_by_role('button',name='Save & close').click();page.get_by_role('heading',name='Every interview has a place.').wait_for()
  context=browser.new_context(viewport={'width':1280,'height':1000});page=watch(context.new_page());page.goto(url);page.get_by_role('button',name='Try field collection').click();ready(page)
  original=page.evaluate("() => structuredClone(state.references.find(r=>r.instrument==='household'))")
  assert collect(page,'household')=='maria-HE-001'
  for selector in ['#respondent','#community','#meta-municipality_province','#meta-language']:assert page.locator(selector).get_attribute('readonly') is not None
  assert page.locator('#community').input_value()=='Bucana' and page.locator('#meta-language').input_value()=='Cebuano'
  close_draft(page);assert collect(page,'household')=='maria-HE-002';close_draft(page)
  # Repeating a delayed grant response must not reset the locally consumed counter.
  page.evaluate("async row=>{await saveReservation(row,row);await loadReferences();}",original)
  page.reload();ready(page);assert collect(page,'household')=='maria-HE-003';third=page.evaluate('() => state.draft.id');close_draft(page)
  page.locator('[data-delete="'+third+'"]').click();page.locator('#confirm-delete').click();assert collect(page,'household')=='maria-HE-004';close_draft(page)
  assert collect(page,'community')=='maria-CI-001';close_draft(page)
  assert collect(page,'observation')=='maria-SO-001';close_draft(page)
  # Same browser installation, two open tabs: atomic allocation prevents duplicates.
  other_tab=watch(context.new_page());other_tab.goto(url);ready(other_tab)
  page.locator('[data-view="collect"]').first.click()
  page.evaluate("() => {window.creation=startInterview('household');}")
  other_tab.evaluate("() => {window.creation=startInterview('household');}")
  page.locator('#respondent').wait_for();other_tab.locator('#respondent').wait_for()
  assert {page.locator('#respondent').input_value(),other_tab.locator('#respondent').input_value()}=={'maria-HE-005','maria-HE-006'}
  close_draft(page);close_draft(other_tab);other_tab.close()
  # Offline reopen keeps the next counter and administrator defaults.
  page.wait_for_function('() => state.ready');context.set_offline(True);page.reload();page.get_by_role('heading',name='Start with a conversation.').wait_for();page.set_viewport_size({'width':390,'height':844});assert collect(page,'household')=='maria-HE-007';old_id=page.evaluate('() => state.draft.id');assert page.locator('#meta-language').input_value()=='Cebuano';assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(artifacts/'generated-id-mobile.png'),full_page=True)
  # Another device reserves a disjoint range, not the same 001 sequence.
  device2=browser.new_context(viewport={'width':1280,'height':1000});p2=watch(device2.new_page());p2.goto(url);p2.get_by_role('button',name='Try field collection').click();ready(p2);assert collect(p2,'household')=='maria-HE-101';close_draft(p2)
  # Administrator changes defaults. Existing offline interviews must keep old values.
  admin=browser.new_context(viewport={'width':1280,'height':1000});ap=watch(admin.new_page());ap.goto(url);ap.get_by_role('button',name='Open dashboard').click();ap.get_by_role('heading',name='Every conversation counts.').wait_for();roster=admin.request.get(url+'/api/dashboard').json()['users'];maria=next(u for u in roster if u['username']=='maria');ap.locator('[data-view="enumerators"]').first.click();ap.locator('[data-edit-user="'+maria['id']+'"]').click();ap.locator('#enum-community').fill('New barangay');ap.locator('#enum-municipality').fill('New municipality / Province');ap.locator('#enum-language').fill('English');ap.get_by_role('dialog').screenshot(path=str(artifacts/'administrator-assignment.png'));ap.get_by_role('button',name='Save changes',exact=True).click();ap.get_by_role('dialog').wait_for(state='hidden')
  context.set_offline(False);page.wait_for_function("() => state.user.language==='English' && !referencePreparation")
  assert page.locator('#community').input_value()=='Bucana' and page.locator('#meta-language').input_value()=='Cebuano'
  page.locator('input[name="consent"][value="Yes"]').check();page.locator('input[name="gps_consent"][value="No"]').check();page.locator('input[name="photo_consent"][value="No"]').check();page.locator('input[name="audio_consent"][value="No"]').check();page.locator('[data-step]').last.click();page.locator('#review-confirm').check();page.get_by_role('button',name='Finish interview').click();page.wait_for_function("id => !state.local.some(x=>x.id===id)",arg=old_id)
  stored=next(r for r in admin.request.get(url+'/api/dashboard').json()['surveys'] if r['id']==old_id);assert stored['respondent']=='maria-HE-007' and stored['metadata']['language']=='Cebuano'
  assert collect(page,'household')=='maria-HE-008';assert page.locator('#community').input_value()=='New barangay' and page.locator('#meta-language').input_value()=='English';close_draft(page)
  # Exhausted offline pool must block a new interview without altering saved drafts.
  page.evaluate("""async()=>{await new Promise((resolve,reject)=>{const tx=db.transaction('allocations','readwrite'),s=tx.objectStore('allocations'),r=s.get(referenceKey(state.user,'household'));r.onsuccess=()=>{const row=r.result;row.next=row.end+1;s.put(row)};tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)});await loadReferences();}""")
  context.set_offline(True);page.evaluate("() => startInterview('household')");assert page.evaluate('() => state.draft===null');assert 'No reserved HE IDs remain' in page.locator('#toast').inner_text()
  context.set_offline(False);page.wait_for_function("() => state.references.some(r=>r.instrument==='household' && referenceRemaining(r)>0)");assert collect(page,'household')=='maria-HE-201';close_draft(page)
  # A different enumerator on the second device gets a separate username/counter.
  p2.get_by_role('button',name='Sign out',exact=True).click();p2.locator('#username').fill('juan');p2.locator('#password').fill('FieldworkDemo!2026');p2.get_by_role('button',name='Sign in to workspace').click();ready(p2);assert collect(p2,'household')=='juan-HE-001';assert p2.locator('#community').input_value()=='Talomo'
  assert not errors,errors;browser.close()
 print('PASS: per-type/per-enumerator IDs, readonly defaults, refresh, deletion without reuse, late-grant retry, concurrent tabs, independent devices, offline allocation/exhaustion, administrator edits and old-assignment sync.')
 print('Browser artifacts:',artifacts)
finally:server.terminate();server.wait(timeout=10);log.close()
