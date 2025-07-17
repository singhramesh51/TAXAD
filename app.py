from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from werkzeug.utils import secure_filename
import uuid
from dotenv import load_dotenv
from tax_calculator import calculate_tax
import json
import requests
import csv
import psycopg2

app = Flask(__name__, template_folder='templates', static_folder='static')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

load_dotenv()
DB_URL = os.getenv('DB_URL')

print("FLASK_APP:", os.getenv("FLASK_APP"))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'pdf_file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['pdf_file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            # Simulate extraction with dummy data
            dummy_data = {
                'gross_salary': 1200000.00,
                'basic_salary': 600000.00,
                'hra_received': 200000.00,
                'rent_paid': 180000.00,
                'deduction_80c': 150000.00,
                'deduction_80d': 25000.00,
                'standard_deduction': 50000.00,
                'professional_tax': 2500.00,
                'tds': 90000.00,
                'selected_regime': 'new'
            }
            return render_template('form.html', extracted=True, data=dummy_data, pdf_filename=filename)
        else:
            flash('Invalid file type. Please upload a PDF.')
            return redirect(request.url)
    return render_template('form.html', extracted=False)

@app.route('/extract', methods=['POST'])
def extract():
    reviewed_data = {
        'gross_salary': request.form.get('gross_salary'),
        'basic_salary': request.form.get('basic_salary'),
        'hra_received': request.form.get('hra_received'),
        'rent_paid': request.form.get('rent_paid'),
        'deduction_80c': request.form.get('deduction_80c'),
        'deduction_80d': request.form.get('deduction_80d'),
        'standard_deduction': request.form.get('standard_deduction'),
        'professional_tax': request.form.get('professional_tax'),
        'tds': request.form.get('tds'),
        'selected_regime': request.form.get('selected_regime'),
    }
    tax_old, tax_new, best_regime = calculate_tax(reviewed_data)
    session_id = str(uuid.uuid4())
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        # Insert into UserFinancials
        cur.execute('''
            INSERT INTO UserFinancials (
                session_id, gross_salary, basic_salary, hra_received, rent_paid, deduction_80c, deduction_80d, standard_deduction, professional_tax, tds
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (
            session_id,
            reviewed_data['gross_salary'],
            reviewed_data['basic_salary'],
            reviewed_data['hra_received'],
            reviewed_data['rent_paid'],
            reviewed_data['deduction_80c'],
            reviewed_data['deduction_80d'],
            reviewed_data['standard_deduction'],
            reviewed_data['professional_tax'],
            reviewed_data['tds']
        ))
        # Insert into TaxComparison
        cur.execute('''
            CREATE TABLE IF NOT EXISTS TaxComparison (
                session_id UUID PRIMARY KEY,
                tax_old_regime NUMERIC(15,2),
                tax_new_regime NUMERIC(15,2),
                best_regime VARCHAR(10),
                selected_regime VARCHAR(10),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            INSERT INTO TaxComparison (
                session_id, tax_old_regime, tax_new_regime, best_regime, selected_regime
            ) VALUES (%s,%s,%s,%s,%s)
        ''', (
            session_id, tax_old, tax_new, best_regime, reviewed_data['selected_regime']
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return f"<h2>Database Error</h2><pre>{e}</pre><a href='/'>Back to Home</a>"
    return render_template('results.html', tax_old=tax_old, tax_new=tax_new, best_regime=best_regime, selected_regime=reviewed_data['selected_regime'], session_id=session_id)

def get_gemini_followup(data):
    # Compose a contextual follow-up question prompt
    prompt = f"""
You are a tax advisor for Indian salaried employees. Based on the following user data, ask ONE smart, relevant follow-up question to help optimize their tax savings. Do NOT give advice yet, just ask a question.

User Data:
Gross Salary: {data['gross_salary']}
Basic Salary: {data['basic_salary']}
HRA Received: {data['hra_received']}
Rent Paid: {data['rent_paid']}
Deduction 80C: {data['deduction_80c']}
Deduction 80D: {data['deduction_80d']}
Standard Deduction: {data['standard_deduction']}
Professional Tax: {data['professional_tax']}
TDS: {data['tds']}
Selected Regime: {data['selected_regime']}
"""
    return gemini_api_call(prompt)

def get_gemini_suggestion(data, user_answer):
    # Compose a prompt for personalized suggestions
    prompt = f"""
You are a tax advisor for Indian salaried employees. Based on the following user data and their answer to your follow-up question, provide actionable, personalized investment and tax-saving suggestions. Format your response as a clear, readable HTML list or cards.

User Data:
Gross Salary: {data['gross_salary']}
Basic Salary: {data['basic_salary']}
HRA Received: {data['hra_received']}
Rent Paid: {data['rent_paid']}
Deduction 80C: {data['deduction_80c']}
Deduction 80D: {data['deduction_80d']}
Standard Deduction: {data['standard_deduction']}
Professional Tax: {data['professional_tax']}
TDS: {data['tds']}
Selected Regime: {data['selected_regime']}

User's Answer: {user_answer}
"""
    return gemini_api_call(prompt)

def gemini_api_call(prompt):
    api_key = os.getenv('GEMINI_API_KEY')
    url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=' + api_key
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(data))
        resp.raise_for_status()
        result = resp.json()
        # Extract the text from Gemini's response
        return result['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"AI Error: {e}"

@app.route('/advisor', methods=['GET', 'POST'])
def advisor():
    if request.method == 'GET':
        session_id = request.args.get('session_id')
        if not session_id:
            return "<h2>Session ID missing.</h2><a href='/'>Back to Home</a>"
        # Fetch user data from CSVs
        user_data = None
        with open('user_financials.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['session_id'] == session_id:
                    user_data = row
                    break
        if not user_data:
            return "<h2>Session not found.</h2><a href='/'>Back to Home</a>"
        # Add selected_regime from tax_comparison.csv
        with open('tax_comparison.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['session_id'] == session_id:
                    user_data['selected_regime'] = row['selected_regime']
                    break
        followup_question = get_gemini_followup(user_data)
        log_ai_conversation(session_id, {'role': 'ai', 'type': 'question', 'content': followup_question})
        return render_template('ask.html', followup_question=followup_question, session_id=session_id, ai_suggestion=None)
    else:
        session_id = request.form.get('session_id')
        user_answer = request.form.get('user_answer')
        if not session_id or not user_answer:
            return "<h2>Missing data.</h2><a href='/'>Back to Home</a>"
        # Fetch user data from CSVs
        user_data = None
        with open('user_financials.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['session_id'] == session_id:
                    user_data = row
                    break
        if not user_data:
            return "<h2>Session not found.</h2><a href='/'>Back to Home</a>"
        with open('tax_comparison.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['session_id'] == session_id:
                    user_data['selected_regime'] = row['selected_regime']
                    break
        ai_suggestion = get_gemini_suggestion(user_data, user_answer)
        log_ai_conversation(session_id, {'role': 'user', 'type': 'answer', 'content': user_answer})
        log_ai_conversation(session_id, {'role': 'ai', 'type': 'suggestion', 'content': ai_suggestion})
        return render_template('ask.html', ai_suggestion=ai_suggestion, session_id=session_id)

def log_ai_conversation(session_id, message):
    log_file = 'ai_conversation_log.json'
    try:
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        else:
            logs = {}
        if session_id not in logs:
            logs[session_id] = []
        logs[session_id].append(message)
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        pass  # Fail silently for logging

@app.route('/sessions', methods=['GET', 'POST'])
def sessions():
    session_ids = []
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute('SELECT session_id FROM UserFinancials')
        session_ids = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
    except Exception:
        pass
    if request.method == 'POST':
        session_id = request.form.get('session_id')
        if session_id:
            return redirect(url_for('session_detail', session_id=session_id))
    return render_template('sessions.html', session_ids=session_ids)

@app.route('/session/<session_id>')
def session_detail(session_id):
    user_data = None
    tax_data = None
    ai_log = []
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        # Get user financials
        cur.execute('SELECT * FROM UserFinancials WHERE session_id = %s', (session_id,))
        row = cur.fetchone()
        if row:
            user_fields = [desc[0] for desc in cur.description]
            user_data = dict(zip(user_fields, row))
        # Get tax comparison
        cur.execute('SELECT * FROM TaxComparison WHERE session_id = %s', (session_id,))
        row = cur.fetchone()
        if row:
            tax_fields = [desc[0] for desc in cur.description]
            tax_data = dict(zip(tax_fields, row))
        cur.close()
        conn.close()
    except Exception:
        pass
    # Get AI conversation log
    try:
        with open('ai_conversation_log.json', encoding='utf-8') as f:
            logs = json.load(f)
            ai_log = logs.get(session_id, [])
    except Exception:
        pass
    return render_template('session_detail.html', session_id=session_id, user_data=user_data, tax_data=tax_data, ai_log=ai_log)

@app.route('/admin/analytics')
def admin_analytics():
    num_sessions = 0
    regime_counts = {'old': 0, 'new': 0}
    total_tax_old = 0
    total_tax_new = 0
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute('SELECT selected_regime, tax_old_regime, tax_new_regime FROM TaxComparison')
        rows = cur.fetchall()
        for row in rows:
            num_sessions += 1
            regime = row[0]
            if regime in regime_counts:
                regime_counts[regime] += 1
            total_tax_old += float(row[1])
            total_tax_new += float(row[2])
        cur.close()
        conn.close()
    except Exception:
        pass
    avg_tax_old = round(total_tax_old / num_sessions, 2) if num_sessions else 0
    avg_tax_new = round(total_tax_new / num_sessions, 2) if num_sessions else 0
    return render_template('admin_analytics.html', num_sessions=num_sessions, regime_counts=regime_counts, avg_tax_old=avg_tax_old, avg_tax_new=avg_tax_new)

if __name__ == '__main__':
    app.run(debug=True) 