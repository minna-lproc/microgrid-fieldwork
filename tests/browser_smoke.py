"""Real-browser integration check with an isolated temporary demo database."""
import os, sys, socket, subprocess, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
artifacts=Path(tempfile.mkdtemp(prefix='gridfield-browser-'))
env=dict(os.environ,DATABASE=str(artifacts/'test.sqlite'),DEMO='1')
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
env['PORT']=str(port)
subprocess.run([sys.executable,'-m','flask','--app','app','seed-demo'],cwd=ROOT,env=env,check=True,capture_output=True)
log=open(artifacts/'server.log','w')
server=subprocess.Popen([sys.executable,'app.py'],cwd=ROOT,env=env,stdout=log,stderr=log)
url=f'http://127.0.0.1:{port}'
try:
    for attempt in range(100):
        try: urllib.request.urlopen(url,timeout=1);break
        except Exception:time.sleep(.1)
    else:raise RuntimeError('Test server did not start')
    with sync_playwright() as p:
        launch={'headless':True}
        if os.environ.get('CHROMIUM_PATH'):launch['executable_path']=os.environ['CHROMIUM_PATH']
        browser=p.chromium.launch(**launch)
        context=browser.new_context(viewport={'width':1440,'height':1050})
        page=context.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url);page.get_by_role('button',name='Open dashboard').click()
        page.get_by_role('heading',name='Every conversation counts.').wait_for()
        assert page.locator('.stat .value').first.inner_text()=='74'
        page.screenshot(path=str(artifacts/'dashboard.png'),full_page=True)
        page.get_by_role('button',name='Add enumerator',exact=True).click()
        page.locator('#enum-name').fill('Browser Test')
        page.locator('#enum-username').fill('browser-test')
        page.locator('#enum-password').fill('BrowserTest!2026')
        page.locator('#enum-community').fill('Test community')
        page.get_by_role('button',name='Create enumerator').click()
        page.get_by_role('dialog').wait_for(state='hidden')
        page.locator('[data-view="enumerators"]').first.click()
        page.get_by_role('heading',name='Your field team').wait_for()
        assert page.get_by_text('Browser Test',exact=True).count()==1
        page.locator('[data-view="responses"]').first.click()
        page.locator('[data-survey]').first.click()
        page.get_by_role('button',name='Verify interview').click()
        page.get_by_role('dialog').get_by_text('verified',exact=True).wait_for()
        page.get_by_role('button',name='Close dialog').click()
        # Deletion requires a second dialog and exact respondent confirmation.
        rows_before=page.request.get(url+'/api/dashboard').json()['surveys']
        to_delete=rows_before[0]
        page.locator('[data-survey]').first.click()
        page.get_by_role('button',name='Delete interview',exact=True).click()
        assert page.get_by_role('button',name='Delete permanently').is_disabled()
        page.get_by_role('button',name='Keep interview').click()
        assert len(page.request.get(url+'/api/dashboard').json()['surveys'])==len(rows_before)
        page.get_by_role('button',name='Delete interview',exact=True).click()
        page.locator('#delete-submission-confirm').fill('WRONG-REFERENCE')
        assert page.get_by_role('button',name='Delete permanently').is_disabled()
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.get_by_role('dialog').screenshot(path=str(artifacts/'delete-interview-mobile.png'))
        page.set_viewport_size({'width':1440,'height':1050})
        page.locator('#delete-submission-confirm').fill(to_delete['respondent'])
        page.get_by_role('button',name='Delete permanently').click()
        page.get_by_role('dialog').wait_for(state='hidden')
        rows_after=page.request.get(url+'/api/dashboard').json()['surveys']
        assert len(rows_after)==len(rows_before)-1
        assert not any(r['id']==to_delete['id'] for r in rows_after)
        assert page.locator('[data-survey="'+to_delete['id']+'"]').count()==0
        page.locator('[data-view="insights"]').first.click()
        page.get_by_role('heading',name='Listen to the bigger picture.').wait_for()
        page.get_by_role('button',name='Sign out',exact=True).click()
        page.get_by_role('button',name='Try field collection').click()
        page.get_by_role('heading',name='Start with a conversation.').wait_for()
        page.wait_for_function("() => document.querySelector('.notice').textContent.includes('Offline app files are ready')")
        context.set_offline(True)
        page.locator('[data-start="household"]').click()
        page.locator('#respondent').fill('OFFLINE-BROWSER-001')
        page.locator('input[name="consent"][value="Yes"]').check()
        page.locator('input[name="gps_consent"][value="No"]').check()
        page.locator('input[name="photo_consent"][value="No"]').check()
        page.locator('input[name="audio_consent"][value="No"]').check()
        page.locator('#meta-municipality_province').fill('Davao / Davao del Sur')
        page.locator('#meta-language').fill('Cebuano')
        page.get_by_role('button',name='Continue',exact=True).click()
        page.locator('input[data-q="A1"][value="Female"]').check()
        page.get_by_role('button',name='Save & close').click()
        page.get_by_role('heading',name='Every interview has a place.').wait_for()
        page.reload()
        page.get_by_role('heading',name='Start with a conversation.').wait_for()
        page.locator('[data-view="drafts"]').first.click()
        page.locator('[data-resume]').first.click()
        page.locator('input[data-q="A1"][value="Female"]').wait_for()
        assert page.locator('input[data-q="A1"][value="Female"]').is_checked()
        page.locator('[data-step]').last.click()
        page.locator('#review-confirm').check()
        page.get_by_role('button',name='Finish interview').click()
        page.get_by_text('Waiting to sync',exact=True).wait_for()
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(artifacts/'mobile-queue.png'),full_page=True)
        context.set_offline(False)
        page.wait_for_function("() => document.querySelectorAll('[data-resume]').length === 0")
        page.locator('.draft-item strong').filter(has_text='OFFLINE-BROWSER-001').first.wait_for()
        # Exactly one server row after reconnect, with the correct account ownership.
        summary=page.request.get(url+'/api/my-surveys').json()['surveys']
        assert len([s for s in summary if s['respondent']=='OFFLINE-BROWSER-001'])==1
        assert page.request.get(url+'/api/dashboard').status==403
        page.locator('[data-action="menu"]').click()
        page.locator('[data-view="collect"]').first.click()
        page.locator('[data-start="community"]').click()
        page.locator('#respondent').fill('COMMUNITY-TEST')
        page.locator('input[name="consent"][value="Yes"]').check()
        page.locator('input[name="gps_consent"][value="No"]').check()
        page.locator('input[name="photo_consent"][value="No"]').check()
        page.locator('input[name="audio_consent"][value="No"]').check()
        page.locator('#meta-municipality_province').fill('Davao / Davao del Sur')
        page.locator('#meta-language').fill('Cebuano')
        page.get_by_role('button',name='Continue',exact=True).click()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(artifacts/'mobile-survey.png'),full_page=True)
        assert not errors, errors
        browser.close()
    print('PASS: dashboard, accounts, review, insights, offline reload, reconnect sync, role boundary, mobile layout, confirmed single-interview deletion.')
    print('Browser artifacts:',artifacts)
finally:
    server.terminate()
    server.wait(timeout=10)
    log.close()
