from flask import Blueprint, render_template, request, session, redirect, flash, jsonify
import subprocess
import shlex
import json
import os

storage_bp = Blueprint('storage', __name__)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or "gcp-internal-lab"
LOCATIONS = ["US", "EU", "ASIA-EAST1"]


def run_cmd(command):
    try:
        res = subprocess.run(shlex.split(command), capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"Storage command error: {e.stderr}")
        return None


@storage_bp.route('/storage')
def storage_dashboard():
    if 'user' not in session:
        return redirect('/login')

    buckets = []
    output = run_cmd(f"gcloud storage buckets list --project={PROJECT} --format=json")
    if output:
        try:
            buckets = json.loads(output)
        except Exception:
            buckets = []

    return render_template('modules/storage/overview.html', user=session['user'], buckets=buckets, locations=LOCATIONS)


@storage_bp.route('/storage/buckets/create', methods=['POST'])
def create_bucket():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    bucket_name = request.form.get('bucket_name', '').strip()
    location = request.form.get('location', 'US')
    retention_days = int(request.form.get('retention_days', '30') or 30)
    retention_seconds = retention_days * 86400

    if not bucket_name:
        flash('Bucket name is required.', 'danger')
        return redirect('/storage')

    cmd = (
        f"gcloud storage buckets create {bucket_name} --project={PROJECT} "
        f"--location={location} --uniform-bucket-level-access --public-access-prevention=enforced "
        f"--default-storage-class=STANDARD --retention-period={retention_seconds}"
    )
    result = run_cmd(cmd)

    if result is None:
        flash('Failed to create bucket. Check logs for details.', 'danger')
    else:
        flash(f'Bucket {bucket_name} created successfully.', 'success')

    return redirect('/storage')


@storage_bp.route('/storage/access', methods=['POST'])
def manage_bucket_access():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    flash('Bucket access management is currently a guided workflow. IAM policy editing will be exposed next.', 'success')
    return redirect('/storage')
