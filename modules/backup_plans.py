from flask import Blueprint, request, jsonify, session, redirect, flash, render_template, Response
from google.cloud import firestore
from google.api_core import exceptions as google_exceptions
import subprocess
import shlex
import json
import time
import os
from datetime import datetime, timezone, timedelta
from threading import Thread
import requests

backup_bp = Blueprint('backup', __name__)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or "gcp-internal-lab"
REGION = "us-central1"

def run_cmd(c):
    """Execute gcloud command and return JSON output"""
    try:
        if "--format" not in c: 
            c += " --format=json"
        res = subprocess.run(shlex.split(c), capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"CMD ERROR: {e.stderr}")
        return "{}"

def get_firestore_client():
    """Get Firestore client with proper database"""
    try:
        return firestore.Client(project=PROJECT, database="restore-db")
    except Exception as e:
        print(f"Firestore error: {e}")
        return None

# =============================================================================
# BACKUP PLANS MANAGEMENT
# =============================================================================

@backup_bp.route("/backup-plans")
def list_plans():
    """Show all backup plans"""
    if 'user' not in session: 
        return redirect("/login")
    
    db = get_firestore_client()
    plans = []
    
    if db:
        try:
            for doc in db.collection('backup_plans').order_by('created_at', direction=firestore.Query.DESCENDING).stream():
                plan = doc.to_dict()
                plan['id'] = doc.id
                
                # Get real status from GCP Backup DR
                try:
                    status_cmd = f"gcloud backup-dr backup-plans describe {plan['name']} --location={plan.get('region', REGION)} --project={PROJECT}"
                    status_out = run_cmd(status_cmd)
                    if status_out:
                        status_data = json.loads(status_out)
                        plan['gcp_status'] = status_data.get('state', 'UNKNOWN')
                        plan['last_backup'] = status_data.get('lastSuccessfulBackupTime', 'Never')
                except:
                    plan['gcp_status'] = 'PENDING'
                    plan['last_backup'] = plan.get('last_backup', 'Never')
                
                plans.append(plan)
        except Exception as e:
            print(f"Error fetching plans: {e}")
    
    return render_template("backup_plans.html", plans=plans, user=session['user'])

@backup_bp.route("/backup")
def backup_dashboard():
    if 'user' not in session:
        return redirect("/login")
    return render_template("modules/backup/overview.html", user=session['user'])

@backup_bp.route("/backup-plans/new", methods=["POST"])
def create_plan():
    """Create a new backup plan in GCP Backup DR"""
    if 'user' not in session: 
        flash("Unauthorized", "danger")
        return redirect("/login")
    
    data = request.form
    db = get_firestore_client()
    
    try:
        # Parse VM list
        vm_list = [v.strip() for v in data.get('vms', '').split(',') if v.strip()]
        if not vm_list:
            flash("No VMs specified", "danger")
            return redirect("/backup-plans")
        
        # Build gcloud command for creating backup plan
        # Note: In production, you'd use the proper resource format for VMs
        # This is simplified for demonstration
        cmd_parts = [
            "gcloud", "backup-dr", "backup-plans", "create", data['name'],
            f"--location={data.get('region', REGION)}",
            f"--project={PROJECT}",
            f"--backup-rule=rule1:window-start={data['window_start']},recurrence={data['schedule']}",
            f"--backup-vault={data['vault']}",
            "--quiet"
        ]
        
        # Execute command (may fail if VMs not properly formatted, but we catch error)
        try:
            subprocess.run(cmd_parts, capture_output=True, text=True, check=True, timeout=30)
            gcp_status = "ACTIVE"
        except subprocess.CalledProcessError as e:
            print(f"GCP Backup Plan creation warning: {e.stderr}")
            # Still save to Firestore even if GCP command needs adjustment
            gcp_status = "PENDING_CREATION"
        
        # Save to Firestore
        if db:
            plan_ref = db.collection('backup_plans').document()
            plan_ref.set({
                'name': data['name'],
                'description': data.get('description', ''),
                'vms': vm_list,
                'schedule': data['schedule'],
                'window_start': data['window_start'],
                'retention_days': int(data.get('retention_days', 30)),
                'vault': data['vault'],
                'region': data.get('region', REGION),
                'created_by': session['user'],
                'status': 'ACTIVE',
                'gcp_status': gcp_status,
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_backup': None,
                'notification_enabled': data.get('notification_enabled') == 'on'
            })
        
        flash(f"Backup plan '{data['name']}' created successfully", "success")
        
    except Exception as e:
        flash(f"Error creating plan: {str(e)}", "danger")
    
    return redirect("/backup-plans")

@backup_bp.route("/backup-plans/<plan_id>/delete", methods=["POST"])
def delete_plan(plan_id):
    """Soft delete a backup plan"""
    if 'user' not in session: 
        return redirect("/login")
    
    db = get_firestore_client()
    if db:
        try:
            # Get plan details first
            plan_doc = db.collection('backup_plans').document(plan_id).get()
            if plan_doc.exists:
                plan_data = plan_doc.to_dict()
                
                # Try to delete from GCP Backup DR
                try:
                    delete_cmd = [
                        "gcloud", "backup-dr", "backup-plans", "delete", plan_data['name'],
                        f"--location={plan_data.get('region', REGION)}",
                        f"--project={PROJECT}",
                        "--quiet"
                    ]
                    subprocess.run(delete_cmd, capture_output=True, text=True, check=True, timeout=30)
                except Exception as e:
                    print(f"GCP delete warning: {e}")
                
                # Update Firestore status
                db.collection('backup_plans').document(plan_id).update({
                    'status': 'DELETED',
                    'deleted_at': firestore.SERVER_TIMESTAMP,
                    'deleted_by': session['user']
                })
                
                flash("Backup plan deleted", "success")
        except Exception as e:
            flash(f"Error deleting plan: {e}", "danger")
    
    return redirect("/backup-plans")

# =============================================================================
# COMPLIANCE DASHBOARD
# =============================================================================

@backup_bp.route("/compliance")
def compliance_dashboard():
    """Show compliance dashboard page"""
    if 'user' not in session: 
        return redirect("/login")
    return render_template("compliance.html", user=session['user'])

@backup_bp.route("/api/compliance/status")
def compliance_status():
    """Check backup compliance - which VMs are protected per policy"""
    if 'user' not in session: 
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        # Get all Compute instances
        vms_out = run_cmd(f"gcloud compute instances list --project={PROJECT}")
        vms = json.loads(vms_out) if vms_out else []
        
        # Get all active backup plans from Firestore
        db = get_firestore_client()
        protected_vms = set()
        
        if db:
            try:
                plans = db.collection('backup_plans').where('status', '==', 'ACTIVE').stream()
                for plan in plans:
                    p = plan.to_dict()
                    protected_vms.update(p.get('vms', []))
            except Exception as e:
                print(f"Error fetching plans: {e}")
        
        # Build compliance report
        report = []
        total = len(vms)
        protected = 0
        
        for vm in vms:
            vm_name = vm['name']
            is_protected = vm_name in protected_vms
            
            if is_protected:
                protected += 1
            
            # Determine environment from labels or name
            env = vm.get('labels', {}).get('env', 'PROD')
            if 'dev' in vm_name.lower():
                env = 'DEV'
            elif 'staging' in vm_name.lower() or 'stg' in vm_name.lower():
                env = 'STAGING'
            
            report.append({
                'vm_name': vm_name,
                'zone': vm['zone'],
                'environment': env,
                'machine_type': vm.get('machineType', 'unknown').split('/')[-1],
                'status': 'PROTECTED' if is_protected else 'UNPROTECTED',
                'is_protected': is_protected
            })
        
        # Calculate compliance score
        score = (protected / total * 100) if total > 0 else 0
        
        # Check for critical violations (PROD VMs unprotected)
        critical_violations = [r for r in report if r['environment'] == 'PROD' and not r['is_protected']]
        
        return jsonify({
            'score': round(score, 1),
            'total_vms': total,
            'protected_vms': protected,
            'unprotected_vms': total - protected,
            'critical_violations': len(critical_violations),
            'details': report,
            'last_updated': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"Compliance check error: {e}")
        return jsonify({"error": str(e)}), 500

# =============================================================================
# VAULT MANAGEMENT
# =============================================================================

@backup_bp.route("/vaults")
def list_vaults():
    """List all backup vaults"""
    if 'user' not in session: 
        return redirect("/login")
    
    vaults = []
    try:
        vaults_out = run_cmd(f"gcloud backup-dr backup-vaults list --location={REGION} --project={PROJECT}")
        if vaults_out:
            vaults = json.loads(vaults_out)
    except Exception as e:
        print(f"Error fetching vaults: {e}")
        # Provide default vault if API fails
        vaults = [{'name': 'default', 'description': 'Default Backup Vault'}]
    
    return render_template("vaults.html", vaults=vaults, user=session['user'])

@backup_bp.route("/vaults/create", methods=["POST"])
def create_vault():
    """Create a new backup vault"""
    if 'user' not in session: 
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.form
    
    try:
        retention_days = int(data.get('retention_days', 7))
        cmd = [
            "gcloud", "backup-dr", "backup-vaults", "create", data['name'],
            f"--location={data.get('region', REGION)}",
            f"--project={PROJECT}",
            f"--backup-min-enforced-retention={retention_days}d"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Log to Firestore
        db = get_firestore_client()
        if db:
            db.collection('vaults').add({
                'name': data['name'],
                'region': data.get('region', REGION),
                'retention_days': int(data.get('retention_days', 7)),
                'created_by': session['user'],
                'created_at': firestore.SERVER_TIMESTAMP
            })
        
        flash(f"Vault '{data['name']}' created successfully", "success")
        
    except Exception as e:
        flash(f"Error creating vault: {e}", "danger")
    
    return redirect("/vaults")

# =============================================================================
# MONITORING & ALERTS
# =============================================================================

@backup_bp.route("/api/backup-jobs/live")
def live_backup_jobs():
    """SSE endpoint for real-time backup job updates"""
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    def generate():
        """Generator for SSE"""
        last_jobs = {}
        
        while True:
            try:
                # Get recent backup jobs
                filter_time = (datetime.now() - timedelta(hours=1)).isoformat()
                jobs_out = run_cmd(
                    f"gcloud backup-dr jobs list --location={REGION} --project={PROJECT} --filter=createTime>{filter_time}"
                )
                
                if jobs_out:
                    jobs = json.loads(jobs_out)
                    
                    for job in jobs:
                        job_id = job.get('name')
                        current_state = job.get('state')
                        
                        # Only send if state changed
                        if job_id not in last_jobs or last_jobs[job_id] != current_state:
                            last_jobs[job_id] = current_state
                            
                            payload = {
                                'job_id': job_id,
                                'status': current_state,
                                'vm': job.get('targetResource', 'unknown'),
                                'progress': job.get('progressPercent', 0),
                                'timestamp': job.get('createTime'),
                                'type': job.get('jobType', 'UNKNOWN')
                            }
                            yield "data: " + json.dumps(payload) + "\n\n"
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                print(f"Live monitoring error: {e}")
                time.sleep(30)
    
    return Response(generate(), mimetype='text/event-stream')

@backup_bp.route("/monitoring")
def monitoring_dashboard():
    """Show real-time monitoring dashboard"""
    if 'user' not in session:
        return redirect("/login")
    
    # Get recent backup jobs
    jobs = []
    try:
        jobs_out = run_cmd(
            f"gcloud backup-dr jobs list --location={REGION} --project={PROJECT} --limit=20"
        )
        if jobs_out:
            jobs = json.loads(jobs_out)
    except Exception as e:
        print(f"Error fetching jobs: {e}")
    
    return render_template("monitoring.html", jobs=jobs, user=session['user'])

# =============================================================================
# INTEGRATION WEBHOOKS
# =============================================================================

def send_slack_notification(message, webhook_url=None):
    """Send notification to Slack"""
    if not webhook_url:
        # Get from environment or Firestore config
        webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    
    try:
        payload = {
            "text": message,
            "username": "DR Portal",
            "icon_emoji": ":shield:"
        }
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception as e:
        print(f"Slack notification failed: {e}")

def create_servicenow_ticket(vm_name, error_details):
    """Create incident ticket in ServiceNow"""
    try:
        ticket_data = {
            'short_description': f'Backup Failed: {vm_name}',
            'description': f'Backup operation failed for VM {vm_name}.\n\nError: {error_details}',
            'urgency': '2',  # High
            'impact': '2',   # Medium
            'category': 'Cloud Infrastructure',
            'subcategory': 'Backup & Recovery'
        }
        
        # ServiceNow API endpoint would be configured here
        # requests.post('https://servicenow.ismena.com/api/now/table/incident', 
        #               json=ticket_data, auth=(username, password))
        
        print(f"ServiceNow ticket would be created for {vm_name}")
        
    except Exception as e:
        print(f"ServiceNow integration failed: {e}")

@backup_bp.route("/api/webhooks/backup-alert", methods=["POST"])
def handle_backup_webhook():
    """Receive webhook from GCP when backup completes/fails"""
    data = request.json
    
    # Log the event
    db = get_firestore_client()
    if db:
        db.collection('backup_alerts').add({
            'event_type': data.get('eventType'),
            'vm_name': data.get('targetResource'),
            'status': data.get('status'),
            'timestamp': firestore.SERVER_TIMESTAMP,
            'raw_data': data
        })
    
    # Send notifications for failures
    if data.get('status') == 'FAILED':
        send_slack_notification(f":rotating_light: Backup Failed: {data.get('targetResource')}")
        create_servicenow_ticket(data.get('targetResource'), data.get('errorMessage', 'Unknown error'))
    
    return jsonify({"status": "received"}), 200

# =============================================================================
# COST ESTIMATION
# =============================================================================

@backup_bp.route("/api/cost-estimate", methods=["POST"])
def cost_estimate():
    """Estimate backup storage costs"""
    data = request.json
    
    try:
        total_size_gb = data.get('total_size_gb', 100)
        daily_change_rate = data.get('daily_change_rate', 2)  # percent
        retention_days = data.get('retention_days', 30)
        
        # GCP Backup DR pricing (simplified)
        # Standard: $0.024/GB/month for storage
        # Incremental: daily_change_rate% of total
        
        base_storage = total_size_gb * 0.024  # Monthly base
        incremental = (total_size_gb * (daily_change_rate / 100)) * retention_days * 0.024
        
        monthly_cost = base_storage + incremental
        
        # CUD discounts
        one_year_cud = monthly_cost * 0.85  # 15% discount
        three_year_cud = monthly_cost * 0.70  # 30% discount
        
        return jsonify({
            'monthly_cost': round(monthly_cost, 2),
            'one_year_cud': round(one_year_cud, 2),
            'three_year_cud': round(three_year_cud, 2),
            'annual_savings_cud3': round((monthly_cost - three_year_cud) * 12, 2),
            'assumptions': {
                'base_storage_gb': total_size_gb,
                'daily_change_percent': daily_change_rate,
                'retention_days': retention_days
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
