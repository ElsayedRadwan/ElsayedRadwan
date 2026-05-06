from modules.backup_plans import backup_bp
from modules.compute_factory import compute_bp
from modules.storage_manager import storage_bp
# from modules.iam_jit import iam_bp  # TODO: Implement IAM JIT module
# from modules.cost_optimizer import cost_bp  # TODO: Implement Cost Optimizer module
import os, json, subprocess, uuid, time, shlex, urllib.parse, threading
from datetime import datetime, timezone
from flask import Flask, request, render_template, redirect, session, flash, jsonify
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.cloud import datastore
from google.cloud import firestore

app = Flask(__name__)
app.register_blueprint(backup_bp)
app.register_blueprint(compute_bp)
app.register_blueprint(storage_bp)
# app.register_blueprint(iam_bp)  # TODO: Implement IAM JIT module
# app.register_blueprint(cost_bp)  # TODO: Implement Cost Optimizer module
app.secret_key = os.environ.get("FLASK_SECRET", "super-secret-key-for-production")

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or "gcp-internal-lab"
REGION = "us-central1"
ZONES = ["us-central1-a", "us-central1-b", "us-central1-c", "us-central1-f"]
CLIENT_ID = "197985624950-fi2ca7tpj40je6fabrvb178d56u196pd.apps.googleusercontent.com"
FIRESTORE_DB = "restore-db"

try:
    db_datastore = datastore.Client(project=PROJECT)
    db_firestore = firestore.Client(project=PROJECT, database=FIRESTORE_DB)
except Exception as e:
    print(f"DB Init Error: {e}")
    db_datastore = None
    db_firestore = None

def run_cmd(c):
    try:
        if "--format" not in c: 
            c += " --format=json"
        res = subprocess.run(shlex.split(c), capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"CMD ERROR: {e.stderr}")
        return "{}"

def get_backups():
    if 'backups_cache' in session and time.time() - session.get('cache_time',0) < 300: 
        return session['backups_cache']
    try:
        vms = {str(i['id']): i['name'] for i in json.loads(run_cmd(f"gcloud compute instances list --project={PROJECT}"))}
        dss = json.loads(run_cmd(f"gcloud backup-dr data-sources list --location={REGION} --project={PROJECT}"))
        ds_map = {d['name']: vms.get(d.get('dataSourceGcpResource',{}).get('gcpResourcename','').split('/')[-1], "Vaulted") for d in dss}
        bks = json.loads(run_cmd(f"gcloud backup-dr backups list --location={REGION} --project={PROJECT}"))
        data = []
        for b in bks:
            ds_path = "/".join(b['name'].split('/')[:-2])
            dt = datetime.fromisoformat(b.get('createTime','').replace('Z','+00:00')).strftime("%b %d, %I:%M %p")
            data.append({"display": f"{ds_map.get(ds_path,'Vault')} | {dt}", "value": b['name']})
        session['backups_cache'] = sorted(data, key=lambda x: x['display'], reverse=True)
        session['cache_time'] = time.time()
        return session['backups_cache']
    except: 
        return []

def get_networks():
    try:
        out = run_cmd(f"gcloud compute networks list --project={PROJECT} --format='value(name)'")
        return out.strip().split('\n')
    except: 
        return ["default"]

@app.route("/")
def index():
    if 'user' not in session: 
        return redirect("/login")
    return redirect("/home")

@app.route("/login")
def login(): 
    return render_template("login.html", cid=CLIENT_ID)

@app.route("/callback")
def callback():
    try:
        session['user'] = id_token.verify_oauth2_token(request.args.get("token"), google_requests.Request(), CLIENT_ID)['email']
        return redirect("/home")
    except: 
        return redirect("/login")

@app.route("/logout")
def logout(): 
    session.clear()
    return redirect("/login")

@app.route("/home")
def home():
    if 'user' not in session: 
        return redirect("/login")
    return render_template("home.html", backups=get_backups(), zones=ZONES, 
                           networks=get_networks(), user=session['user'], project=PROJECT)

@app.route("/restore", methods=["POST"])
def restore():
    if 'user' not in session: 
        return redirect("/login")
    vm_name = request.form['new_vm']
    user = session['user']
    
    try:
        # Save to history first and get doc reference
        doc_ref = None
        if db_firestore:
            doc_ref = db_firestore.collection('jobs').document()
            doc_ref.set({
                'vm_name': vm_name, 
                'user': user, 
                'status': 'STARTED', 
                'timestamp': firestore.SERVER_TIMESTAMP,
                'type': 'single'
            })
        
        cmd = f"gcloud backup-dr backups restore compute {request.form['backup']} --async --project={PROJECT} --name={vm_name} --target-project={PROJECT} --target-zone={request.form['zone']} --network-interface=network=projects/{PROJECT}/global/networks/{request.form['network']} --format=json"
        output = json.loads(run_cmd(cmd))
        op_id = output.get('name', '')
        
        # Update with operation_id for tracking
        if doc_ref and op_id:
            doc_ref.update({'operation_id': op_id})
            
        return redirect(f"/status/{urllib.parse.quote(op_id)}")
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect("/home")

@app.route("/status/<path:op_id>")
def status_page(op_id):
    if 'user' not in session: 
        return redirect("/login")
    return render_template("status.html", op_id=op_id, user=session['user'], project=PROJECT)

@app.route("/api/check_status/<path:op_id>")
def api_check_status(op_id):
    try:
        res = json.loads(run_cmd(f"gcloud backup-dr operations describe {op_id} --project={PROJECT} --location={REGION}"))
        done = res.get('done', False)
        error = res.get('error', None)
        return jsonify({"done": done, "error": error})
    except: 
        return jsonify({"done": False, "error": "Unknown"})

def run_task_thread(exec_id, task_idx, task, user):
    try:
        fs = firestore.Client(project=PROJECT, database=FIRESTORE_DB)
        
        # Save starting status
        fs.collection('plan_executions').document(exec_id).collection('tasks').document(f'task_{task_idx}').set({
            'task_index': task_idx,
            'vm_name': task['vm'],
            'status': 'STARTED',
            'user': user,
            'time': firestore.SERVER_TIMESTAMP,
            'project': task.get('project', PROJECT)
        })
        
        # Use project from task or default
        target_project = task.get('project', PROJECT)
        
        # Run restore
        cmd = f"gcloud backup-dr backups restore compute {task['backup']} --async --project={PROJECT} --name={task['vm']} --target-project={target_project} --target-zone={task['zone']} --network-interface=network=projects/{PROJECT}/global/networks/{task['net']} --format=json"
        result = subprocess.run(shlex.split(cmd), capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        op_id = output.get('name', 'unknown')
        
        # Update with operation_id
        fs.collection('plan_executions').document(exec_id).collection('tasks').document(f'task_{task_idx}').update({
            'operation_id': op_id
        })
        
        # Save to global history
        fs.collection('jobs').add({
            'vm_name': task['vm'], 
            'user': user, 
            'status': 'STARTED', 
            'timestamp': firestore.SERVER_TIMESTAMP,
            'type': 'plan',
            'operation_id': op_id
        })
    except Exception as e:
        print(f"Task error: {e}")
        try:
            fs = firestore.Client(project=PROJECT, database=FIRESTORE_DB)
            fs.collection('plan_executions').document(exec_id).collection('tasks').document(f'task_{task_idx}').update({
                'status': 'FAILED',
                'error': str(e)
            })
        except: 
            pass

@app.route("/plan/run/<pid>", methods=["POST"])
def run_plan(pid):
    if 'user' not in session: 
        return redirect("/login")
    if not db_datastore:
        flash("Database not available", "danger")
        return redirect("/plans")
    
    plan = db_datastore.get(db_datastore.key('restore_plans', pid))
    if not plan or not plan.get('tasks'):
        flash("Plan is empty", "danger")
        return redirect("/plans")
    
    user = session['user']
    exec_id = str(uuid.uuid4())
    
    # Create execution record
    try:
        db_firestore.collection('plan_executions').document(exec_id).set({
            'plan_name': plan['name'],
            'started_by': user,
            'start_time': firestore.SERVER_TIMESTAMP,
            'total_tasks': len(plan['tasks'])
        })
    except Exception as e:
        print(f"Exec record error: {e}")
    
    # Start all tasks
    for idx, task in enumerate(plan['tasks']):
        t = threading.Thread(target=run_task_thread, args=(exec_id, idx, task, user))
        t.daemon = False
        t.start()
        time.sleep(0.5)
    
    flash(f"Started {len(plan['tasks'])} restore tasks", "success")
    return redirect(f"/plan/execution/{exec_id}")

@app.route("/plan/execution/<exec_id>")
def plan_execution_status(exec_id):
    if 'user' not in session: 
        return redirect("/login")
    return render_template("plan_execution.html", exec_id=exec_id, user=session['user'], project=PROJECT)

@app.route("/api/plan_execution/<exec_id>")
def api_plan_execution(exec_id):
    try:
        fs = firestore.Client(project=PROJECT, database=FIRESTORE_DB)
        tasks = []
        task_docs = list(fs.collection('plan_executions').document(exec_id).collection('tasks').stream())
        
        for doc in task_docs:
            t = doc.to_dict()
            
            # Check operation status if STARTED
            if t.get('operation_id') and t.get('status') == 'STARTED':
                try:
                    op_res = json.loads(run_cmd(f"gcloud backup-dr operations describe {t['operation_id']} --project={PROJECT} --location={REGION}"))
                    if op_res.get('done'):
                        new_status = 'COMPLETED' if not op_res.get('error') else 'FAILED'
                        # Update Firestore
                        doc.reference.update({'status': new_status})
                        t['status'] = new_status
                        
                        # Update history too
                        try:
                            history = fs.collection('jobs').where('operation_id', '==', t['operation_id']).limit(1).stream()
                            for h in history:
                                h.reference.update({'status': new_status})
                        except: 
                            pass
                except: 
                    pass
            tasks.append(t)
        
        tasks.sort(key=lambda x: x.get('task_index', 0))
        all_done = len(tasks) > 0 and all(t.get('status') in ['COMPLETED', 'FAILED'] for t in tasks)
        
        return jsonify({"tasks": tasks, "all_done": all_done})
    except Exception as e:
        print(f"API ERROR: {e}")
        return jsonify({"error": str(e), "tasks": []})

@app.route("/history")
def jobs():
    if 'user' not in session: 
        return redirect("/login")
    jobs_list = []
    try:
        if db_firestore: 
            # Update any completed operations (both single and plan)
            pending = db_firestore.collection('jobs').where('status', '==', 'STARTED').stream()
            for doc in pending:
                job = doc.to_dict()
                if job.get('operation_id'):
                    try:
                        op_res = json.loads(run_cmd(f"gcloud backup-dr operations describe {job['operation_id']} --project={PROJECT} --location={REGION}"))
                        if op_res.get('done'):
                            new_status = 'COMPLETED' if not op_res.get('error') else 'FAILED'
                            doc.reference.update({'status': new_status})
                    except: 
                        pass
            
            # Fetch updated list
            jobs_list = [doc.to_dict() for doc in db_firestore.collection('jobs').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(20).stream()]
    except Exception as e: 
        print(f"History error: {e}")
    return render_template("history.html", jobs=jobs_list, user=session['user'])

@app.route("/plans")
def plans():
    if 'user' not in session: 
        return redirect("/login")
    items = []
    try:
        if db_datastore:
            q = db_datastore.query(kind='restore_plans')
            q.order = ['-createdAt']
            items = [dict(e, id=e.key.name) for e in q.fetch()]
    except: 
        pass
    return render_template("plans.html", plans=items, user=session['user'])

@app.route("/plan/create", methods=["POST"])
def create_plan():
    if db_datastore:
        try:
            key = db_datastore.key('restore_plans', str(uuid.uuid4()))
            entity = datastore.Entity(key=key)
            entity.update({
                'name': request.form['name'], 
                'tasks': [], 
                'createdBy': session.get('user'), 
                'createdAt': datetime.now(timezone.utc)
            })
            db_datastore.put(entity)
        except Exception as e: 
            print(f"Create error: {e}")
    return redirect("/plans")

@app.route("/plan/delete/<pid>", methods=["POST"])
def delete_plan(pid):
    if db_datastore:
        db_datastore.delete(db_datastore.key('restore_plans', pid))
    return redirect("/plans")

@app.route("/plan/edit/<pid>")
def edit_plan(pid):
    if 'user' not in session: 
        return redirect("/login")
    plan = None
    if db_datastore: 
        plan = db_datastore.get(db_datastore.key('restore_plans', pid))
    return render_template("edit_plan.html", plan=dict(plan, id=pid) if plan else None, 
                           backups=get_backups(), zones=ZONES, networks=get_networks(), 
                           project=PROJECT, user=session['user'])

@app.route("/plan/task/add/<pid>", methods=["POST"])
def add_task(pid):
    if db_datastore:
        p = db_datastore.get(db_datastore.key('restore_plans', pid))
        if p:
            p['tasks'].append({
                'backup': request.form['backup'], 
                'vm': request.form['vm'], 
                'zone': request.form['zone'], 
                'net': request.form['net'],
                'project': request.form.get('project', PROJECT)
            })
            db_datastore.put(p)
    return redirect(f"/plan/edit/{pid}")

@app.route("/plan/task/del/<pid>/<int:tid>", methods=["POST"])
def del_task(pid, tid):
    if db_datastore:
        p = db_datastore.get(db_datastore.key('restore_plans', pid))
        if p and tid < len(p['tasks']): 
            p['tasks'].pop(tid)
            db_datastore.put(p)
    return redirect(f"/plan/edit/{pid}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)
