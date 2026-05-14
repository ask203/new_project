from datetime import datetime
from decimal import Decimal

from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///splitwifi.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)


class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    payer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="General")
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    split_type = db.Column(db.String(20), nullable=False, default="equal")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ExpenseShare(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey("expense.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    owed_amount = db.Column(db.Numeric(10, 2), nullable=False)


class Settlement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def get_group_members(group_id: int):
    members = (
        db.session.query(User)
        .join(GroupMember, GroupMember.user_id == User.id)
        .filter(GroupMember.group_id == group_id)
        .order_by(User.name)
        .all()
    )
    return members


def calculate_balances(group_id: int):
    members = get_group_members(group_id)
    balances = {m.id: Decimal("0.00") for m in members}

    expenses = Expense.query.filter_by(group_id=group_id).all()
    for exp in expenses:
        balances[exp.payer_id] += Decimal(str(exp.amount))
        shares = ExpenseShare.query.filter_by(expense_id=exp.id).all()
        for share in shares:
            balances[share.user_id] -= Decimal(str(share.owed_amount))

    settlements = Settlement.query.filter_by(group_id=group_id).all()
    for s in settlements:
        amt = Decimal(str(s.amount))
        balances[s.from_user_id] += amt
        balances[s.to_user_id] -= amt

    named_balances = {User.query.get(uid).name: round(val, 2) for uid, val in balances.items()}
    return named_balances


def simplify_debts(named_balances):
    creditors = []
    debtors = []
    for name, bal in named_balances.items():
        if bal > 0:
            creditors.append([name, Decimal(str(bal))])
        elif bal < 0:
            debtors.append([name, Decimal(str(-bal))])

    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    tx = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        pay_amt = min(debtors[i][1], creditors[j][1])
        if pay_amt > Decimal("0.00"):
            tx.append(
                {
                    "from": debtors[i][0],
                    "to": creditors[j][0],
                    "amount": float(round(pay_amt, 2)),
                }
            )
        debtors[i][1] -= pay_amt
        creditors[j][1] -= pay_amt
        if debtors[i][1] <= Decimal("0.009"):
            i += 1
        if creditors[j][1] <= Decimal("0.009"):
            j += 1
    return tx


@app.route("/")
def home():
    groups = Group.query.order_by(Group.name).all()
    users = User.query.order_by(User.name).all()
    return render_template("index.html", groups=groups, users=users)


@app.post("/users")
def create_user():
    name = request.form.get("name", "").strip()
    if name and not User.query.filter_by(name=name).first():
        db.session.add(User(name=name))
        db.session.commit()
    return redirect(url_for("home"))


@app.post("/groups")
def create_group():
    name = request.form.get("name", "").strip()
    member_ids = request.form.getlist("member_ids")
    if name and not Group.query.filter_by(name=name).first():
        group = Group(name=name)
        db.session.add(group)
        db.session.flush()
        for member_id in member_ids:
            db.session.add(GroupMember(group_id=group.id, user_id=int(member_id)))
        db.session.commit()
    return redirect(url_for("home"))


@app.route("/groups/<int:group_id>")
def group_detail(group_id):
    group = Group.query.get_or_404(group_id)
    members = get_group_members(group_id)
    expenses = Expense.query.filter_by(group_id=group_id).order_by(Expense.created_at.desc()).all()

    balances = calculate_balances(group_id)
    suggestions = simplify_debts(balances)

    monthly_category_rows = (
        db.session.query(
            func.strftime("%Y-%m", Expense.created_at).label("month"),
            Expense.category,
            func.sum(Expense.amount).label("total"),
        )
        .filter(Expense.group_id == group_id)
        .group_by("month", Expense.category)
        .order_by("month")
        .all()
    )

    monthly = {}
    for row in monthly_category_rows:
        monthly.setdefault(row.month, {})[row.category] = float(row.total)

    return render_template(
        "group.html",
        group=group,
        members=members,
        expenses=expenses,
        balances=balances,
        suggestions=suggestions,
        monthly=monthly,
    )


@app.post("/groups/<int:group_id>/expenses")
def add_expense(group_id):
    payer_id = int(request.form["payer_id"])
    description = request.form["description"].strip()
    category = request.form.get("category", "General").strip() or "General"
    amount = Decimal(request.form["amount"])
    split_type = request.form.get("split_type", "equal")
    participants = [int(p) for p in request.form.getlist("participants")]
    shares_input = request.form.get("shares", "")

    if not participants:
        return redirect(url_for("group_detail", group_id=group_id))

    expense = Expense(
        group_id=group_id,
        payer_id=payer_id,
        description=description,
        category=category,
        amount=amount,
        split_type=split_type,
    )
    db.session.add(expense)
    db.session.flush()

    owed = {}
    if split_type == "equal":
        per = (amount / Decimal(len(participants))).quantize(Decimal("0.01"))
        for uid in participants:
            owed[uid] = per
        diff = amount - sum(owed.values())
        owed[participants[0]] += diff
    elif split_type in {"exact", "percent", "shares"}:
        raw = [Decimal(x.strip()) for x in shares_input.split(",") if x.strip()]
        if len(raw) != len(participants):
            return redirect(url_for("group_detail", group_id=group_id))
        if split_type == "exact":
            for uid, val in zip(participants, raw):
                owed[uid] = val.quantize(Decimal("0.01"))
        elif split_type == "percent":
            for uid, pct in zip(participants, raw):
                owed[uid] = (amount * pct / Decimal("100")).quantize(Decimal("0.01"))
        else:
            total_shares = sum(raw)
            for uid, share in zip(participants, raw):
                owed[uid] = (amount * share / total_shares).quantize(Decimal("0.01"))
        diff = amount - sum(owed.values())
        owed[participants[0]] += diff

    for uid, amt in owed.items():
        db.session.add(ExpenseShare(expense_id=expense.id, user_id=uid, owed_amount=amt))

    db.session.commit()
    return redirect(url_for("group_detail", group_id=group_id))


@app.post("/groups/<int:group_id>/settle")
def settle(group_id):
    from_user_id = int(request.form["from_user_id"])
    to_user_id = int(request.form["to_user_id"])
    amount = Decimal(request.form["amount"])
    if amount > 0:
        db.session.add(
            Settlement(
                group_id=group_id,
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                amount=amount,
            )
        )
        db.session.commit()
    return redirect(url_for("group_detail", group_id=group_id))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)
