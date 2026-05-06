from flask import Blueprint, render_template, request, session, redirect, flash, jsonify

iam_bp = Blueprint('iam', __name__)


@iam_bp.route('/iam')
def iam_dashboard():
    if 'user' not in session:
        return redirect('/login')
    return render_template('modules/iam/overview.html', user=session['user'])


@iam_bp.route('/iam/temp-access', methods=['POST'])
def request_temporary_access():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    flash('Temporary access request submitted. JIT access will be audited.', 'success')
    return redirect('/iam')


@iam_bp.route('/iam/firewall', methods=['POST'])
def update_firewall():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    flash('Firewall rule update recorded. Visual editor is active.', 'success')
    return redirect('/iam')
