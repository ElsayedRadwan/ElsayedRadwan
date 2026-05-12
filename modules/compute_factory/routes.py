from flask import Blueprint, render_template, request, session, redirect, flash, jsonify
import subprocess
import shlex
import json
import os

compute_bp = Blueprint('compute', __name__)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or "gcp-internal-lab"
ZONES = ["us-central1-a", "us-central1-b", "us-central1-c", "us-central1-f"]
NETWORKS = ["default"]
MACHINE_TEMPLATES = [
    {"value": "e2-medium", "label": "E2 Medium"},
    {"value": "e2-standard-4", "label": "E2 Standard 4"},
    {"value": "e2-highmem-8", "label": "E2 Highmem 8"}
]


def run_cmd(command):
    try:
        res = subprocess.run(shlex.split(command), capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"Compute command error: {e.stderr}")
        return None


@compute_bp.route('/compute')
def compute_dashboard():
    if 'user' not in session:
        return redirect('/login')

    return render_template('modules/compute/overview.html', user=session['user'], zones=ZONES, networks=NETWORKS, templates=MACHINE_TEMPLATES)


@compute_bp.route('/compute/create', methods=['POST'])
def create_vm():
    if 'user' not in session:
        return redirect('/login')

    vm_name = request.form.get('vm_name', '').strip()
    zone = request.form.get('zone', ZONES[0])
    machine_type = request.form.get('machine_type', MACHINE_TEMPLATES[0]['value'])
    network = request.form.get('network', NETWORKS[0])

    if not vm_name:
        flash('VM name is required.', 'danger')
        return redirect('/compute')

    cmd = f"gcloud compute instances create {vm_name} --project={PROJECT} --zone={zone} --machine-type={machine_type} --network={network} --format=json"
    result = run_cmd(cmd)

    if result is None:
        flash('Failed to create VM. Check logs for details.', 'danger')
    else:
        flash(f'VM {vm_name} creation started successfully.', 'success')

    return redirect('/compute')


@compute_bp.route('/compute/bulk-create', methods=['POST'])
def bulk_create_vms():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    flash('Bulk VM creation workflow will be enabled soon. Upload and templating support is next.', 'info')
    return redirect('/compute')


@compute_bp.route('/compute/schedule', methods=['POST'])
def schedule_vm_action():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    flash('VM schedule request recorded. Scheduler integration is planned for the next release.', 'success')
    return redirect('/compute')
