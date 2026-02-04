from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta
from sqlalchemy import func
import matplotlib.pyplot as plt
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///habits.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

CHART_DIR = 'static/charts'

# ================= MODELS =================

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    logs = db.relationship(
        'HabitLog',
        backref='habit',
        cascade='all, delete',
        lazy=True
    )

class HabitLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    day = db.Column(db.Date, nullable=False)
    status = db.Column(db.Boolean, default=False)

# ================= UTILITIES =================

def month_dates():
    today = date.today()
    start = today.replace(day=1)
    dates = []
    d = start
    while d.month == today.month:
        dates.append(d)
        d += timedelta(days=1)
    return dates

def habit_accuracy(habit_id):
    total = db.session.query(func.count(HabitLog.id))\
            .filter_by(habit_id=habit_id).scalar()

    done = db.session.query(func.count(HabitLog.id))\
           .filter_by(habit_id=habit_id, status=True).scalar()

    return round((done / total) * 100, 2) if total else 0

def generate_charts():
    os.makedirs(CHART_DIR, exist_ok=True)

    logs = HabitLog.query.all()
    total = len(logs)
    completed = sum(log.status for log in logs)
    pending = total - completed

    # Pie chart
    plt.figure()
    plt.pie(
        [completed, pending],
        labels=['Completed', 'Pending'],
        autopct='%1.1f%%'
    )
    plt.title('Overall Habit Completion')
    plt.savefig(f'{CHART_DIR}/pie.png')
    plt.close()

    # Bar chart
    habits = Habit.query.order_by(Habit.name).all()
    names, percentages = [], []

    for h in habits:
        names.append(h.name)
        percentages.append(habit_accuracy(h.id))

    plt.figure()
    plt.bar(names, percentages)
    plt.ylabel('Completion %')
    plt.title('Habit-wise Accuracy')
    plt.savefig(f'{CHART_DIR}/bar.png')
    plt.close()

# ================= ROUTES =================

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST':
        name = request.form['habit'].strip()
        if name:
            habit = Habit(name=name)
            db.session.add(habit)
            db.session.commit()

            for d in month_dates():
                db.session.add(HabitLog(habit_id=habit.id, day=d))

            db.session.commit()
        return redirect(url_for('dashboard'))

    habits = Habit.query.all()

    habit_data = []
    for h in habits:
        habit_data.append((h, habit_accuracy(h.id)))

    habit_data.sort(key=lambda x: (-x[1], x[0].name.lower()))

    total_logs = db.session.query(func.count(HabitLog.id)).scalar()
    done_logs = db.session.query(func.count(HabitLog.id))\
                .filter_by(status=True).scalar()

    overall_accuracy = round((done_logs / total_logs) * 100, 2) if total_logs else 0

    return render_template(
        'index.html',
        habit_data=habit_data,
        overall_accuracy=overall_accuracy
    )

@app.route('/toggle/<int:log_id>')
def toggle(log_id):
    log = HabitLog.query.get_or_404(log_id)
    log.status = not log.status
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/reset_habit/<int:habit_id>')
def reset_habit(habit_id):
    HabitLog.query.filter_by(habit_id=habit_id)\
        .update({HabitLog.status: False})
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/reset_month')
def reset_month():
    HabitLog.query.update({HabitLog.status: False})
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete_habit/<int:habit_id>')
def delete_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    db.session.delete(habit)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/update_charts')
def update_charts():
    generate_charts()
    return redirect(url_for('dashboard'))

# ================= MAIN =================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        os.makedirs(CHART_DIR, exist_ok=True)
    app.run()
