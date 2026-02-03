from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import sqlite3, subprocess, bcrypt

app = Flask(__name__)
app.secret_key = "supersecretkey"  # replace with secure random key

def get_db():
    conn = sqlite3.connect("lab.db")
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- AUTH ----------------
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        conn = get_db()
        try:
            conn.execute("INSERT INTO students (username, password_hash) VALUES (?,?)", (username, password_hash))
            conn.commit()
            return redirect(url_for('login'))
        except:
            return "Username already exists"
    return render_template("register.html")

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        student = conn.execute("SELECT * FROM students WHERE username=?", (username,)).fetchone()
        if student and bcrypt.checkpw(password.encode('utf-8'), student["password_hash"]):
            session['student_id'] = student["id"]
            session['username'] = student["username"]
            session['role'] = student["role"]
            return redirect(url_for('list_problems'))
        else:
            return "Invalid credentials"
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------- PROBLEMS ----------------
@app.route('/problems')
def list_problems():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    problems = conn.execute("SELECT * FROM problems").fetchall()
    return render_template("problems.html", problems=problems, username=session['username'])

@app.route('/problem/<int:pid>')
def show_problem(pid):
    if 'student_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    problem = conn.execute("SELECT * FROM problems WHERE id=?", (pid,)).fetchone()
    return render_template("problem.html", problem=problem, username=session['username'])

@app.route('/submit/<int:pid>', methods=['POST'])
def submit_code(pid):
    if 'student_id' not in session:
        return redirect(url_for('login'))

    code = request.form['code']
    lang = request.form['language']
    student_id = session['student_id']

    conn = get_db()
    test_cases = conn.execute("SELECT * FROM test_cases WHERE problem_id=?", (pid,)).fetchall()

    filename, run_cmd = None, None
    if lang == "python":
        filename = "program.py"
        run_cmd = ["python3", filename]
    elif lang == "c":
        filename = "program.c"
        with open(filename, "w") as f: f.write(code)
        compile_result = subprocess.run(["gcc", filename, "-o", "program"], capture_output=True, text=True)
        if compile_result.returncode != 0:
            conn.execute("INSERT INTO submissions (student_id, problem_id, code, language, score, penalty) VALUES (?,?,?,?,?,?)",
                         (student_id, pid, code, lang, 0, 0))
            conn.commit()
            return jsonify({"error": compile_result.stderr})
        run_cmd = ["./program"]
    elif lang == "cpp":
        filename = "program.cpp"
        with open(filename, "w") as f: f.write(code)
        compile_result = subprocess.run(["g++", filename, "-o", "program"], capture_output=True, text=True)
        if compile_result.returncode != 0:
            conn.execute("INSERT INTO submissions (student_id, problem_id, code, language, score, penalty) VALUES (?,?,?,?,?,?)",
                         (student_id, pid, code, lang, 0, 0))
            conn.commit()
            return jsonify({"error": compile_result.stderr})
        run_cmd = ["./program"]
    else:
        return jsonify({"error": "Language not supported"})

    with open(filename, "w") as f: f.write(code)

    total_score, penalty = 0, 0
    results = []
    for case in test_cases:
        result = subprocess.run(run_cmd, input=case["input"], capture_output=True, text=True)
        stdout = result.stdout.strip()
        if stdout == case["expected_output"].strip():
            total_score += 20
            results.append({"input": case["input"], "output": stdout, "status": "PASS"})
        else:
            penalty += 5
            results.append({"input": case["input"], "output": stdout, "status": "FAIL"})

    final_score = max(total_score - penalty, 0)

    conn.execute("INSERT INTO submissions (student_id, problem_id, code, language, score, penalty) VALUES (?,?,?,?,?,?)",
                 (student_id, pid, code, lang, final_score, penalty))
    conn.commit()

    return jsonify({"results": results, "score": final_score, "penalty": penalty})

# ---------------- ADMIN ----------------
@app.route('/admin')
def admin_dashboard():
    if 'student_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db()
    problems = conn.execute("SELECT * FROM problems").fetchall()
    return render_template("admin_dashboard.html", problems=problems)

@app.route('/admin/add_problem', methods=['GET','POST'])
def add_problem():
    if 'student_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        language = request.form['language']
        conn = get_db()
        conn.execute("INSERT INTO problems (title, description, language) VALUES (?,?,?)",
                     (title, description, language))
        conn.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template("add_problem.html")

@app.route('/admin/add_testcase/<int:pid>', methods=['GET','POST'])
def add_testcase(pid):
    if 'student_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        input_data = request.form['input']
        expected_output = request.form['expected_output']
        conn = get_db()
        conn.execute("INSERT INTO test_cases (problem_id, input, expected_output) VALUES (?,?,?)",
                     (pid, input_data, expected_output))
        conn.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template("add_testcase.html", pid=pid)

# ---------------- SCOREBOARD ----------------
@app.route('/scoreboard')
def scoreboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    scores = conn.execute("""
        SELECT s.username, 
               SUM(sub.score) as total_score, 
               SUM(sub.penalty) as total_penalty, 
               COUNT(sub.id) as attempts,
               MAX(sub.timestamp) as last_submission
        FROM students s
        LEFT JOIN submissions sub ON s.id=sub.student_id
        GROUP BY s.id
        ORDER BY total_score DESC
    """).fetchall()
    return render_template("scoreboard.html", scores=scores)

# ---------------- HISTORY ----------------
@app.route('/history')
def student_history():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    subs = conn.execute("""
        SELECT p.title, sub.score, sub.penalty, sub.timestamp
        FROM submissions sub
        JOIN problems p ON sub.problem_id=p.id
        WHERE sub.student_id=?
        ORDER BY sub.timestamp DESC
    """, (session['student_id'],)).fetchall()
    return render_template("student_history.html", subs=subs)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
