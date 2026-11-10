"""Community microgrid survey. Flask API + installable, offline-first client."""
import csv, io, json, os, secrets, sqlite3, time, uuid
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path
import click
from flask import Flask, request, session, jsonify, send_from_directory, Response, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE = Path(__file__).parent
SCHEMA = json.loads((BASE / 'static/survey.json').read_text())
QUESTIONS = {q['id']: q for s in SCHEMA['sections'] for q in s['questions']}

def now(): return datetime.now(timezone.utc).isoformat()

def create_app(test_config=None):
    app = Flask(__name__, static_folder='static')
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY'), DATABASE=os.environ.get('DATABASE', str(BASE/'instance/survey.sqlite')), MAX_CONTENT_LENGTH=1024*1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE')=='1', PERMANENT_SESSION_LIFETIME=timedelta(days=7), DEMO=os.environ.get('DEMO')=='1')
    if test_config: app.config.update(test_config)
    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    if not app.config['SECRET_KEY']:
        # Durable local key. Set SECRET_KEY through the environment on production hosts.
        keyfile=Path(app.config['DATABASE']).parent/'secret.key'
        if not keyfile.exists():
            try:
                fd=os.open(keyfile, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
                with os.fdopen(fd,'w') as f: f.write(secrets.token_hex(32))
            except FileExistsError: pass
        app.config['SECRET_KEY']=keyfile.read_text()
    def db():
        if 'db' not in g:
            g.db=sqlite3.connect(app.config['DATABASE'],timeout=20)
            g.db.row_factory=sqlite3.Row
            g.db.execute('PRAGMA foreign_keys=ON')
        return g.db
    @app.teardown_appcontext
    def close(error=None):
        if 'db' in g: g.db.close()
    with app.app_context():
        db().executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','enumerator')), community TEXT DEFAULT '', target INTEGER DEFAULT 30, active INTEGER DEFAULT 1, last_seen TEXT, location TEXT);
        CREATE TABLE IF NOT EXISTS surveys(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), instrument TEXT NOT NULL, community TEXT NOT NULL, respondent TEXT NOT NULL, consent TEXT NOT NULL, gps_consent TEXT, location TEXT, answers TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT NOT NULL, received_at TEXT NOT NULL, version TEXT NOT NULL, review TEXT DEFAULT 'pending');
        CREATE INDEX IF NOT EXISTS surveys_user ON surveys(user_id);
        CREATE TABLE IF NOT EXISTS survey_deletions(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), deleted_by TEXT NOT NULL REFERENCES users(id), deleted_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(ip TEXT NOT NULL, timestamp REAL NOT NULL);
        ''')
    def public_user(u): return {k:u[k] for k in ['id','username','name','role','community','target']}
    def login_required(role=None):
        def decorate(fn):
            @wraps(fn)
            def check(*a,**kw):
                u=db().execute('SELECT * FROM users WHERE id=? AND active=1',(session.get('uid'),)).fetchone()
                if not u: return jsonify(error='Sign in to continue. Your offline drafts are retained.'),401
                if role and u['role']!=role: return jsonify(error='Administrator access required.'),403
                g.user=u
                if request.method not in ('GET','HEAD') and (not session.get('csrf') or not secrets.compare_digest(request.headers.get('X-CSRF-Token',''), session['csrf'])): return jsonify(error='Session token expired. Sign in again.'),403
                return fn(*a,**kw)
            return check
        return decorate
    @app.after_request
    def headers(r):
        r.headers['X-Content-Type-Options']='nosniff'
        r.headers['Referrer-Policy']='same-origin'
        r.headers['Permissions-Policy']='geolocation=(self)'
        r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        if request.path.startswith('/api/'): r.headers['Cache-Control']='no-store'
        return r
    @app.get('/')
    def index(): return send_from_directory(BASE/'templates','index.html')
    @app.get('/sw.js')
    def sw():
        r=send_from_directory(BASE/'static','sw.js'); r.headers['Cache-Control']='no-cache'; return r
    @app.get('/api/session')
    def current_session():
        u=db().execute('SELECT * FROM users WHERE id=? AND active=1',(session.get('uid'),)).fetchone()
        return jsonify(user=public_user(u) if u else None,csrf=session.get('csrf'),demo=app.config['DEMO'])
    @app.post('/api/login')
    def login():
        if request.headers.get('Sec-Fetch-Site')=='cross-site': return jsonify(error='Cross-site request rejected'),403
        data=request.get_json(silent=True) or {}; ip=request.remote_addr or ''
        db().execute('DELETE FROM login_attempts WHERE timestamp<?',(time.time()-900,))
        if db().execute('SELECT count(*) FROM login_attempts WHERE ip=?',(ip,)).fetchone()[0]>=20: return jsonify(error='Too many attempts. Try again in 15 minutes.'),429
        u=db().execute('SELECT * FROM users WHERE username=? AND active=1',(str(data.get('username','')).strip().lower(),)).fetchone()
        if not u or not check_password_hash(u['password'],str(data.get('password',''))):
            db().execute('INSERT INTO login_attempts VALUES (?,?)',(ip,time.time())); db().commit()
            return jsonify(error='Username or password is incorrect.'),401
        session.clear(); session.permanent=True; session.update(uid=u['id'],csrf=secrets.token_hex(24))
        db().execute('UPDATE users SET last_seen=? WHERE id=?',(now(),u['id'])); db().commit()
        return jsonify(user=public_user(u),csrf=session['csrf'],demo=app.config['DEMO'])
    @app.post('/api/logout')
    @login_required()
    def logout(): session.clear(); return jsonify(ok=True)
    @app.post('/api/checkin')
    @login_required()
    def checkin():
        data=request.get_json(silent=True) or {}; loc=data.get('location')
        if loc and not valid_location(loc): return jsonify(error='Invalid location'),400
        # Omitting location clears it when an enumerator turns sharing off.
        db().execute('UPDATE users SET last_seen=?,location=? WHERE id=?',(now(),json.dumps(dict(loc,recorded_at=now())) if loc else None,g.user['id'])); db().commit()
        return jsonify(ok=True,server_time=now())
    @app.post('/api/surveys')
    @login_required()
    def submit():
        data=request.get_json(silent=True)
        try: clean=validate_survey(data)
        except (ValueError,TypeError,KeyError) as e: return jsonify(error=str(e)),400
        # Serialize deletion and sync so a delayed offline retry cannot restore a deleted interview.
        db().execute('BEGIN IMMEDIATE')
        deleted=db().execute('SELECT user_id FROM survey_deletions WHERE id=?',(clean['id'],)).fetchone()
        if deleted:
            db().rollback()
            if deleted['user_id']!=g.user['id']: return jsonify(error='Survey ID already used.'),409
            return jsonify(ok=True,id=clean['id'],deleted=True)
        existing=db().execute('SELECT user_id FROM surveys WHERE id=?',(clean['id'],)).fetchone()
        if existing:
            db().rollback()
            if existing['user_id']!=g.user['id']: return jsonify(error='Survey ID already used.'),409
            return jsonify(ok=True,id=clean['id'],duplicate=True)
        db().execute('INSERT INTO surveys(id,user_id,instrument,community,respondent,consent,gps_consent,location,answers,started_at,completed_at,received_at,version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(clean['id'],g.user['id'],clean['instrument'],clean['community'],clean['respondent'],clean['consent'],clean['gps_consent'],json.dumps(clean.get('location')),json.dumps(clean['answers']),clean['started_at'],clean['completed_at'],now(),SCHEMA['version']))
        db().execute('UPDATE users SET last_seen=? WHERE id=?',(now(),g.user['id'])); db().commit()
        return jsonify(ok=True,id=clean['id']),201
    @app.get('/api/my-surveys')
    @login_required()
    def my_surveys(): return jsonify(surveys=[dict(r) for r in db().execute('SELECT id,instrument,community,respondent,completed_at,review FROM surveys WHERE user_id=? ORDER BY received_at DESC LIMIT 200',(g.user['id'],))])
    @app.get('/api/dashboard')
    @login_required('admin')
    def dashboard():
        users=[dict(r) for r in db().execute("SELECT id,name,username,community,target,active,last_seen,location,(SELECT count(*) FROM surveys WHERE user_id=users.id AND consent='Yes') AS completed FROM users WHERE role='enumerator' ORDER BY name")]
        surveys=[dict(r) for r in db().execute('SELECT s.*,u.name AS enumerator FROM surveys s JOIN users u ON u.id=s.user_id ORDER BY received_at DESC')]
        for s in surveys: s['answers']=json.loads(s['answers']); s['location']=json.loads(s['location'])
        for u in users: u['location']=json.loads(u['location']) if u['location'] else None
        return jsonify(users=users,surveys=surveys,server_time=now())
    @app.post('/api/users')
    @login_required('admin')
    def add_user():
        d=request.get_json(silent=True) or {}; username=str(d.get('username','')).lower().strip(); password=str(d.get('password','')); name=str(d.get('name','')).strip()
        if not name or len(name)>100 or not username or len(username)>60 or not all(c.isalnum() or c in '._-' for c in username) or len(password)<12: return jsonify(error='Use a name, valid username, and password of at least 12 characters.'),400
        try: target=int(d.get('target',30)); assert 0<=target<=100000
        except (ValueError,TypeError,AssertionError): return jsonify(error='Target must be 0–100,000.'),400
        try:
            db().execute('INSERT INTO users(id,username,name,password,role,community,target) VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),username,name,generate_password_hash(password),'enumerator',str(d.get('community',''))[:150],target)); db().commit()
        except sqlite3.IntegrityError: return jsonify(error='Username is already in use.'),409
        return jsonify(ok=True),201
    @app.patch('/api/users/<uid>')
    @login_required('admin')
    def update_user(uid):
        d=request.get_json(silent=True) or {}
        u=db().execute("SELECT * FROM users WHERE id=? AND role='enumerator'",(uid,)).fetchone()
        if not u: return jsonify(error='Enumerator not found'),404
        try: target=int(d.get('target',u['target'])); assert 0<=target<=100000
        except (ValueError,TypeError,AssertionError): return jsonify(error='Invalid target'),400
        db().execute('UPDATE users SET community=?,target=?,active=? WHERE id=?',(str(d.get('community',u['community']))[:150],target,int(bool(d.get('active',u['active']))),uid))
        if d.get('password'):
            if len(str(d['password']))<12: db().rollback(); return jsonify(error='Password must be at least 12 characters'),400
            db().execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(d['password']),uid))
        db().commit(); return jsonify(ok=True)
    @app.patch('/api/surveys/<sid>')
    @login_required('admin')
    def review(sid):
        status=(request.get_json(silent=True) or {}).get('review')
        if status not in ['pending','verified','flagged']: return jsonify(error='Invalid review status'),400
        cur=db().execute('UPDATE surveys SET review=? WHERE id=?',(status,sid)); db().commit()
        return (jsonify(ok=True),200) if cur.rowcount else (jsonify(error='Survey not found'),404)
    @app.delete('/api/surveys/<sid>')
    @login_required('admin')
    def delete_survey(sid):
        data=request.get_json(silent=True) or {}
        if not isinstance(data,dict) or not isinstance(data.get('confirm_respondent'),str):
            return jsonify(error='Enter the respondent ID to confirm deletion.'),400
        db().execute('BEGIN IMMEDIATE')
        record=db().execute('SELECT respondent,user_id FROM surveys WHERE id=?',(sid,)).fetchone()
        if not record:
            db().rollback()
            return jsonify(error='Interview not found. Refresh the submission list.'),404
        if data['confirm_respondent']!=record['respondent']:
            db().rollback()
            return jsonify(error='The confirmation must exactly match the respondent ID.'),400
        # Retain only IDs and deletion metadata, never the answers, location or respondent code.
        db().execute('INSERT INTO survey_deletions(id,user_id,deleted_by,deleted_at) VALUES(?,?,?,?)',
                     (sid,record['user_id'],g.user['id'],now()))
        db().execute('DELETE FROM surveys WHERE id=?',(sid,))
        db().commit()
        return jsonify(ok=True,id=sid)
    @app.get('/api/export')
    @login_required('admin')
    def export():
        rows=[dict(r) for r in db().execute('SELECT s.*,u.name AS enumerator FROM surveys s JOIN users u ON u.id=s.user_id ORDER BY received_at DESC')]
        if request.args.get('format')=='json': return Response(json.dumps(dict(schema=SCHEMA,surveys=rows),ensure_ascii=False),mimetype='application/json',headers={'Content-Disposition':'attachment; filename=microgrid-surveys.json'})
        out=io.StringIO(); cols=['id','enumerator','instrument','community','respondent','consent','gps_consent','location','started_at','completed_at','received_at','review']+list(QUESTIONS)
        w=csv.DictWriter(out,fieldnames=cols); w.writeheader()
        for row in rows:
            answers=json.loads(row['answers']); cells={k:row.get(k,answers.get(k,'')) for k in cols}
            for k,v in cells.items():
                if isinstance(v,(dict,list)): v=json.dumps(v,ensure_ascii=False)
                if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@','\t','\r')): v="'"+v
                cells[k]=v
            w.writerow(cells)
        return Response('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=microgrid-surveys.csv'})
    @app.cli.command('create-admin')
    @click.option('--username',prompt=True)
    @click.option('--name',prompt=True)
    @click.password_option(confirmation_prompt=True)
    def admin(username,name,password):
        if len(password)<12: raise click.ClickException('Password must contain at least 12 characters.')
        try:
            db().execute('INSERT INTO users(id,username,name,password,role) VALUES(?,?,?,?,?)',(str(uuid.uuid4()),username.strip().lower(),name,generate_password_hash(password),'admin')); db().commit()
        except sqlite3.IntegrityError: raise click.ClickException('Username already exists.')
        click.echo('Administrator created.')
    @app.cli.command('seed-demo')
    def seed():
        if db().execute('SELECT count(*) FROM users').fetchone()[0]: raise click.ClickException('Demo seeding requires an empty database.')
        demo_seed(db()); click.echo('Synthetic demo ready. admin / MicrogridDemo!2026 or maria / FieldworkDemo!2026')
    return app

def valid_location(v):
    return isinstance(v,dict) and isinstance(v.get('lat'),(int,float)) and isinstance(v.get('lng'),(int,float)) and -90<=v['lat']<=90 and -180<=v['lng']<=180 and isinstance(v.get('accuracy'),(int,float)) and 0<=v['accuracy']<=100000

def validate_survey(d):
    if not isinstance(d,dict): raise ValueError('Invalid survey')
    if str(uuid.UUID(str(d.get('id'))))!=d['id']: raise ValueError('Invalid survey ID')
    if d.get('version')!=SCHEMA['version']: raise ValueError('Survey version changed. Reopen the app before starting a new interview.')
    if d.get('instrument') not in ('household','community','observation'): raise ValueError('Invalid instrument')
    for f in ['community','respondent']:
        if not isinstance(d.get(f),str) or not d[f].strip() or len(d[f])>150: raise ValueError('Community and respondent / observation IDs are required.')
    if d.get('consent') not in ['Yes','No']: raise ValueError('Record interview consent before submitting.')
    if d.get('gps_consent') not in ['Yes','No']: raise ValueError('Record GPS consent.')
    if d.get('instrument')=='observation' and d.get('consent')!='Yes': raise ValueError('Confirm site observation authorization.')
    if d.get('location') and (d['gps_consent']!='Yes' or d['consent']!='Yes' or not valid_location(d['location'])): raise ValueError('Location requires separate consent and valid coordinates.')
    answers=d.get('answers')
    if not isinstance(answers,dict) or len(json.dumps(answers))>500000: raise ValueError('Invalid survey answers')
    allowed={q['id']:q for s in SCHEMA['sections'] if s['instrument']==d['instrument'] for q in s['questions']}
    if d['consent']=='No': d['answers']={}; d['location']=None
    else:
        if answers.get('D1','').startswith('No'):
            for k in ['D2','D_equipment','D3','D4','D2_details','D3_details','D4_details']: answers.pop(k,None)
        for key,value in answers.items():
            if key.endswith('_details') and key[:-8] in allowed:
                if not isinstance(value,str) or len(value)>5000: raise ValueError('Invalid additional details')
                continue
            q=allowed.get(key)
            if not q: raise ValueError('Unrecognized question '+key)
            validate_answer(q,value)
        a=answers.get('A3',{})
        if isinstance(a,dict) and a.get('members') not in ('',None):
            for k in ['under5','over60','equipment']:
                if a.get(k) not in ('',None) and float(a[k])>float(a['members']): raise ValueError('A3: subgroup count cannot exceed household members.')
            if a.get('under5') not in ('',None) and a.get('over60') not in ('',None) and float(a['under5'])+float(a['over60'])>float(a['members']): raise ValueError('A3: age groups exceed household members.')
    for key in ['started_at','completed_at']:
        try:
            dt=datetime.fromisoformat(d[key].replace('Z','+00:00'))
            if dt.tzinfo is None or dt>datetime.now(timezone.utc)+timedelta(days=1): raise ValueError()
        except (ValueError,KeyError,AttributeError): raise ValueError('Invalid interview timestamp')
    if datetime.fromisoformat(d['completed_at'].replace('Z','+00:00'))<datetime.fromisoformat(d['started_at'].replace('Z','+00:00')): raise ValueError('Completion must follow start time.')
    return d

def validate_answer(q,v):
    if q['type']=='select':
        if v not in q['options'] and v!='': raise ValueError(q['id']+': invalid selection')
    elif q['type']=='multi':
        if not isinstance(v,list) or any(x not in q['options'] for x in v): raise ValueError(q['id']+': invalid choices')
        if len(v)>1 and any(x in ('None','None known','None yet') for x in v): raise ValueError(q['id']+': None cannot be combined with other choices')
    elif q['type']=='text':
        if not isinstance(v,str) or len(v)>5000: raise ValueError(q['id']+': invalid text')
    elif q['type']=='fields':
        if not isinstance(v,dict) or any(k not in {f['id'] for f in q['fields']} for k in v): raise ValueError(q['id']+': invalid fields')
        for f in q['fields']: validate_cell(q['id'],f,v.get(f['id'],''))
    elif q['type']=='table':
        if not isinstance(v,list) or len(v)>len(q['rows']): raise ValueError(q['id']+': invalid table')
        for row in v:
            if not isinstance(row,dict) or any(k not in {c['id'] for c in q['columns']} for k in row): raise ValueError(q['id']+': invalid row')
            for c in q['columns']: validate_cell(q['id'],c,row.get(c['id'],''))

def validate_cell(qid,f,v):
    if v in ('',None): return
    if f['type']=='number':
        try:
            n=float(v)
            if not 0<=n<=1e12: raise ValueError()
            if f['id']=='hours' and n>24: raise ValueError()
            if qid=='A3' and n!=int(n): raise ValueError()
            if f['id'] in ['qty','planned','interruptions'] and n!=int(n): raise ValueError()
        except (ValueError,TypeError,OverflowError): raise ValueError(qid+': enter valid non-negative quantities (hours/day ≤ 24).')
    elif not isinstance(v,str) or len(v)>5000: raise ValueError(qid+': invalid text')
    if f['id']=='time' and any(c not in 'MAEN /,' for c in str(v).upper()): raise ValueError(qid+': use M / A / E / N for time of use')
    if f['id']=='answer' and v not in ['Yes','No','']: raise ValueError('Observation answer must be Yes or No')
    if f['id']=='present' and str(v).upper() not in ['Y','N','YES','NO','']: raise ValueError('Facility present must be Y or N')

def demo_seed(db):
    admin=str(uuid.uuid4()); db.execute('INSERT INTO users(id,username,name,password,role) VALUES(?,?,?,?,?)',(admin,'admin','Alex Rivera',generate_password_hash('MicrogridDemo!2026'),'admin'))
    people=[('Maria Santos','maria','Bucana',24,17),('Juan Dela Cruz','juan','Talomo',24,13),('Ana Reyes','ana','Matina Aplaya',20,11),('Paolo Garcia','paolo','Bucana',24,9),('Lea Mendoza','lea','Sirawan',20,8),('Miguel Torres','miguel','Talomo',24,7),('Sofia Lim','sofia','Sirawan',20,5),('Carlo Ramos','carlo','Matina Aplaya',24,4)]
    for i,(name,user,community,target,count) in enumerate(people):
        uid=str(uuid.uuid4()); seen=(datetime.now(timezone.utc)-timedelta(minutes=[2,4,9,18,42,85,140,1440][i])).isoformat()
        loc=json.dumps(dict(lat=7.04+i*.009,lng=125.56+i*.005,accuracy=25,recorded_at=seen)) if i<3 else None
        db.execute('INSERT INTO users(id,username,name,password,role,community,target,last_seen,location) VALUES(?,?,?,?,?,?,?,?,?)',(uid,user,name,generate_password_hash('FieldworkDemo!2026'),'enumerator',community,target,seen,loc))
        for j in range(count):
            dt=(datetime.now(timezone.utc)-timedelta(days=j%7,hours=i,minutes=15*j)).isoformat(); typ='community' if j==0 else 'household'
            answers={'H2':['Support','Strongly support','Neutral / need more information'][j%3],'B2':['24 hours','8–12 hours','4–7 hours'][j%3],'F2':['₱300–₱599','₱600–₱999','₱1,000–₱1,499'][j%3]} if typ=='household' else {'I1':'Underserved'}
            db.execute('INSERT INTO surveys(id,user_id,instrument,community,respondent,consent,gps_consent,location,answers,started_at,completed_at,received_at,version,review) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),uid,typ,community,f'DEMO-{i+1:02}-{j+1:03}','Yes','No','null',json.dumps(answers),dt,dt,dt,SCHEMA['version'],'flagged' if j==3 else 'verified' if j>3 else 'pending'))
    db.commit()

if __name__=='__main__': create_app().run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
