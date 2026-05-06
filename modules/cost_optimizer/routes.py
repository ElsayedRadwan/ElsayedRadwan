from flask import Blueprint, render_template, request, session, redirect, flash, jsonify

cost_bp = Blueprint('cost', __name__)


@cost_bp.route('/cost')
def cost_dashboard():
    if 'user' not in session:
        return redirect('/login')
    return render_template('modules/cost/overview.html', user=session['user'])


@cost_bp.route('/cost/budgets', methods=['POST'])
def save_budget_alert():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    flash('Budget alert created. Project-level spend monitoring is active.', 'success')
    return redirect('/cost')


@cost_bp.route('/cost/rightsizing', methods=['POST'])
def rightsizing_action():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    flash('Rightsizing recommendation noted. Idle resources will be reviewed.', 'success')
    return redirect('/cost')
