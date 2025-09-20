from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import json

# ---------- Config ----------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = 'change_this_secret'  # change for production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'db.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# ---------- Models ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)  # plain for MVP (not recommended in prod)
    role = db.Column(db.String(20), nullable=False)  # 'company' or 'student'


class Internship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    test_json = db.Column(db.Text, nullable=True)  # JSON string with questions
    cutoff_percent = db.Column(db.Integer, default=50)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey('internship.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    passed = db.Column(db.Boolean, default=False)
    score_percent = db.Column(db.Integer, default=0)
    resume_filename = db.Column(db.String(300), nullable=True)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)

# ---------- Helpers ----------
def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return User.query.get(uid)

# ---------- Routes ----------
@app.route('/')
def index():
    internships = Internship.query.order_by(Internship.created_at.desc()).all()
    return render_template('index.html', internships=internships, user=current_user())

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username'].strip()
        pwd = request.form['password'].strip()
        role = request.form['role']
        if User.query.filter_by(username=uname).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        u = User(username=uname, password=pwd, role=role)
        db.session.add(u)
        db.session.commit()
        flash('Registered! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username'].strip()
        pwd = request.form['password'].strip()
        u = User.query.filter_by(username=uname, password=pwd).first()
        if not u:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('login'))
        session['user_id'] = u.id
        flash('Logged in', 'success')
        if u.role == 'company':
            return redirect(url_for('company_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('index'))

# ---------- Company ----------
@app.route('/company')
def company_dashboard():
    u = current_user()
    if not u or u.role != 'company':
        flash('Login as company to access', 'danger')
        return redirect(url_for('login'))
    posts = Internship.query.filter_by(company_id=u.id).order_by(Internship.created_at.desc()).all()
    return render_template('company_dashboard.html', posts=posts, user=u)

@app.route('/company/new', methods=['GET', 'POST'])
def new_post():
    u = current_user()
    if not u or u.role != 'company':
        flash('Login as company', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['description']
        cutoff = int(request.form.get('cutoff_percent', 50))
        test_json_raw = request.form['test_json']
        try:
            test_obj = json.loads(test_json_raw)
            assert isinstance(test_obj, list)
        except Exception:
            flash('Invalid test JSON. Use valid JSON list of questions.', 'danger')
            return redirect(url_for('new_post'))
        post = Internship(company_id=u.id, title=title, description=desc,
                          test_json=json.dumps(test_obj), cutoff_percent=cutoff)
        db.session.add(post)
        db.session.commit()
        flash('Internship posted!', 'success')
        return redirect(url_for('company_dashboard'))
    example = json.dumps([
        {"q": "OOP stands for?", "options": ["Object Oriented Programming", "Order Of Process", "Other", "None"], "ans": 0},
        {"q": "Which is a Java keyword?", "options": ["class", "function", "var", "let"], "ans": 0}
    ], indent=2)
    return render_template('new_post.html', example=example, user=u)

@app.route('/company/<int:post_id>/resumes')
def view_resumes(post_id):
    u = current_user()
    post = Internship.query.get_or_404(post_id)
    if not u or u.role != 'company' or post.company_id != u.id:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    apps = Application.query.filter_by(internship_id=post.id, passed=True).order_by(Application.score_percent.desc()).all()
    return render_template('view_resumes.html', post=post, apps=apps, user=u)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ---------- Student ----------
@app.route('/student')
def student_dashboard():
    u = current_user()
    if not u or u.role != 'student':
        flash('Login as student to access', 'danger')
        return redirect(url_for('login'))
    internships = Internship.query.order_by(Internship.created_at.desc()).all()
    my_apps = Application.query.filter_by(student_id=u.id).all()
    applied_post_ids = [a.internship_id for a in my_apps]
    return render_template('student_dashboard.html', internships=internships,
                           user=u, applied_post_ids=applied_post_ids)

@app.route('/internship/<int:post_id>/apply', methods=['GET', 'POST'])
def apply(post_id):
    u = current_user()
    if not u or u.role != 'student':
        flash('Login as student', 'danger')
        return redirect(url_for('login'))
    post = Internship.query.get_or_404(post_id)
    existing = Application.query.filter_by(internship_id=post.id, student_id=u.id).first()
    if existing:
        flash('You have already applied or attempted this internship', 'info')
        return redirect(url_for('student_dashboard'))
    app_entry = Application(internship_id=post.id, student_id=u.id, passed=False)
    db.session.add(app_entry)
    db.session.commit()
    return redirect(url_for('take_test', app_id=app_entry.id))

@app.route('/test/<int:app_id>', methods=['GET', 'POST'])
def take_test(app_id):
    u = current_user()
    if not u or u.role != 'student':
        flash('Login as student', 'danger')
        return redirect(url_for('login'))
    app_entry = Application.query.get_or_404(app_id)
    if app_entry.student_id != u.id:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    post = Internship.query.get_or_404(app_entry.internship_id)
    questions = json.loads(post.test_json)
    if request.method == 'POST':
        total = len(questions)
        correct = 0
        for idx, q in enumerate(questions):
            ans = request.form.get(f'q_{idx}')
            if ans and int(ans) == q.get('ans'):
                correct += 1
        percent = int((correct / total) * 100) if total > 0 else 0
        app_entry.score_percent = percent
        app_entry.passed = (percent >= post.cutoff_percent)
        db.session.commit()
        if app_entry.passed:
            flash(f'Congrats! You passed the test ({percent}%). Please upload your resume.', 'success')
            return redirect(url_for('upload_resume', app_id=app_entry.id))
        else:
            flash(f'You did not pass the test ({percent}%). Required: {post.cutoff_percent}%.', 'warning')
            return redirect(url_for('student_dashboard'))
    return render_template('take_test.html', questions=questions, post=post, app_entry=app_entry, user=u)

@app.route('/upload_resume/<int:app_id>', methods=['GET', 'POST'])
def upload_resume(app_id):
    u = current_user()
    if not u or u.role != 'student':
        flash('Login as student', 'danger')
        return redirect(url_for('login'))
    app_entry = Application.query.get_or_404(app_id)
    if app_entry.student_id != u.id:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    if not app_entry.passed:
        flash('You must pass the test first', 'danger')
        return redirect(url_for('student_dashboard'))
    if request.method == 'POST':
        f = request.files.get('resume')
        if not f or f.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        fname = secure_filename(f.filename)
        fname = f"{app_entry.student_id}_{int(datetime.utcnow().timestamp())}_{fname}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        f.save(save_path)
        app_entry.resume_filename = fname
        db.session.commit()
        flash('Resume uploaded successfully!', 'success')
        return redirect(url_for('student_dashboard'))
    return render_template('upload_resume.html', app_entry=app_entry, user=u)

# ---------- Init DB ----------
@app.cli.command('initdb')
def initdb_command():
    with app.app_context():
        db.create_all()
    print('Initialized the database.')

if __name__ == '__main__':
    if not os.path.exists(os.path.join(BASE_DIR, 'db.sqlite3')):
        with app.app_context():
            db.create_all()
        print("DB created.")
    app.run(debug=True)
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from eduvision_mvp.models import User
from eduvision_mvp.utils import generate_otp, send_sms

app = Flask(__name__)
app.secret_key = "super_secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
db = SQLAlchemy(app)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        uname = request.form["username"]
        pwd = request.form["password"]
        role = request.form["role"]
        mobile = request.form["mobile"]

        if User.query.filter_by(username=uname).first():
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))

        otp = generate_otp()
        session["temp_user"] = {
            "username": uname,
            "password": pwd,
            "role": role,
            "mobile": mobile,
            "otp": otp
        }

        print("OTP sent:", otp)   # testing
        # send_sms(mobile, otp)   # uncomment after API integration

        return redirect(url_for("verify_otp"))
    return render_template("register.html")


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    temp_user = session.get("temp_user")
    if not temp_user:
        flash("No registration data found. Try again.", "danger")
        return redirect(url_for("register"))

    if request.method == "POST":
        entered_otp = request.form["otp"]
        if str(temp_user["otp"]) == entered_otp:
            u = User(
                username=temp_user["username"],
                password=temp_user["password"],
                role=temp_user["role"],
                mobile=temp_user["mobile"],
                is_verified=True
            )
            db.session.add(u)
            db.session.commit()
            session.pop("temp_user")
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
        else:
            flash("Invalid OTP. Try again.", "danger")
    return render_template("verify_otp.html")
