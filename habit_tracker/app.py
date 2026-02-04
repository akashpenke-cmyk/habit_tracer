from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta
import matplotlib.pyplot as plt
import os
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///habits.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

CHART_DIR = 'static/charts'
CHART_TTL = 10  # seconds (cache lifetime)

# ================= MODELS =================

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    logs = db.relationship('HabitLog', backref='habit', lazy=True)

class HabitLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    day = db.Column(db.Date, nullable=False)
    status = db.Column(db.Boolean, default=False)

# ================= UTILITIES =================

def month_dates():
    today = date.today()
    start = today.replace(day=1)
    return [
        start + timedelta(days=i)
        for i in range(31)
        if (start + timedelta(days=i)).month == today.month
    ]

def charts_are_fresh():
    pie = os.path.join(CHART_DIR, 'pie.png')
    bar = os.path.join(CHART_DIR, 'bar.png')

    if not os.path.exists(pie) or not os.path.exists(bar):
        return False

    return (time.time() - os.path.getmtime(pie)) < CHART_TTL

def generate_charts():
    if charts_are_fresh():
        return  # 🔥 PERFORMANCE WIN

    os.makedirs(CHART_DIR, exist_ok=True)

    logs = HabitLog.query.all()
    total = len(logs)
    completed = sum(log.status for log in logs)
    pending = total - completed

    # Pie Chart
    plt.figure()
    plt.pie(
        [completed, pending],
        labels=['Completed', 'Pending'],
        autopct='%1.1f%%'
    )
    plt.title('Overall Completion')
    plt.savefig(f'{CHART_DIR}/pie.png')
    plt.close()

    # Bar Chart
    habits = Habit.query.all()
    names, percentages = [], []

    for habit in habits:
        total_logs = len(habit.logs)
        done = sum(log.status for log in habit.logs)
        percent = (done / total_logs) * 100 if total_logs else 0
        names.append(habit.name)
        percentages.append(percent)

    plt.figure()
    plt.bar(names, percentages)
    plt.ylabel('Completion %')
    plt.title('Habit Accuracy')
    plt.savefig(f'{CHART_DIR}/bar.png')
    plt.close()

# ================= ROUTES =================

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST':
        habit = Habit(name=request.form['habit'])
        db.session.add(habit)
        db.session.commit()

        for d in month_dates():
            db.session.add(HabitLog(habit_id=habit.id, day=d))

        db.session.commit()
        generate_charts()
        return redirect(url_for('dashboard'))

    habits = Habit.query.all()
    logs = HabitLog.query.all()

    total = len(logs)
    completed = sum(log.status for log in logs)
    accuracy = round((completed / total) * 100, 2) if total else 0

    generate_charts()

    return render_template(
        'index.html',
        habits=habits,
        accuracy=accuracy
    )

@app.route('/toggle/<int:log_id>')
def toggle(log_id):
    log = HabitLog.query.get_or_404(log_id)
    log.status = not log.status
    db.session.commit()
    generate_charts()
    return redirect(url_for('dashboard'))

@app.route('/reset_month')
def reset_month():
    HabitLog.query.update({HabitLog.status: False})
    db.session.commit()
    generate_charts()
    return redirect(url_for('dashboard'))

@app.route('/reset_habit/<int:habit_id>')
def reset_habit(habit_id):
    HabitLog.query.filter_by(habit_id=habit_id).update(
        {HabitLog.status: False}
    )
    db.session.commit()
    generate_charts()
    return redirect(url_for('dashboard'))

# ================= MAIN =================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        os.makedirs(CHART_DIR, exist_ok=True)
    app.run(debug=True)
