from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel,Field
from datetime import date

from database import engine, Base, SessionLocal
from models import Expense

app = FastAPI()

Base.metadata.create_all(bind=engine)


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1)
    amount: float = Field(gt=0, le=1000000)
    category: str =Field(min_length=1)
    date: date


@app.get("/")
def home():
    return {"message": "Expense Tracker API is running!"}

@app.get("/expenses")
def get_expenses(
    sort: str = "date_desc",
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    db = SessionLocal()

    try:
        if sort == "amount_desc":
            query = db.query(Expense).order_by(
                Expense.amount.desc()
            )
        elif sort == "amount_asc":
            query = db.query(Expense).order_by(
                Expense.amount.asc()
            )
        elif sort == "date_asc":
            query = db.query(Expense).order_by(
                Expense.date.asc()
            )
        else:
            query = db.query(Expense).order_by(
                Expense.date.desc()
            )

        expenses = query.offset(skip).limit(limit).all()

        return expenses

    finally:
        db.close()

@app.get("/expenses/summary")
def expense_summary():
    db = SessionLocal()

    expenses = db.query(Expense).all()

    total_expenses = len(expenses)
    total_amount = sum(expense.amount for expense in expenses)

    db.close()

    return {
        "total_expenses": total_expenses,
        "total_amount": total_amount
    }

@app.get("/expenses/summary/category")
def category_summary():
    db = SessionLocal()

    expenses = db.query(Expense).all()

    summary = {}

    for expense in expenses:
        if expense.category in summary:
            summary[expense.category] += expense.amount
        else:
            summary[expense.category] = expense.amount

    db.close()

    return summary

@app.get("/expenses/summary/month")
def monthly_summary(year: int, month: int):
    db = SessionLocal()

    expenses = db.query(Expense).all()

    monthly_expenses = [
        expense for expense in expenses
        if expense.date.year == year and expense.date.month == month
    ]

    total_expenses = len(monthly_expenses)
    total_amount = sum(
        expense.amount for expense in monthly_expenses
    )

    db.close()

    return {
        "year": year,
        "month": month,
        "total_expenses": total_expenses,
        "total_amount": total_amount
    }

@app.get("/expenses/filter")
def filter_expenses(start_date: date, end_date: date):
    db = SessionLocal()

    expenses = db.query(Expense).filter(
        Expense.date >= start_date,
        Expense.date <= end_date
    ).all()

    db.close()

    return expenses

@app.get("/expenses/search")
def search_expenses(keyword: str):
    db = SessionLocal()

    expenses = db.query(Expense).filter(
        Expense.title.ilike(f"%{keyword}%")
    ).all()

    db.close()

    return expenses

@app.get("/expenses/filter/category")
def filter_by_category(category: str):
    db = SessionLocal()

    expenses = db.query(Expense).filter(
        Expense.category.ilike(category)
    ).all()

    db.close()

    return expenses

@app.get("/expenses/{expense_id}")
def get_expense(expense_id: int):
    db = SessionLocal()

    try:
        expense = db.query(Expense).filter(
            Expense.id == expense_id
        ).first()

        if expense is None:
            raise HTTPException(
                status_code=404,
                detail="Expense not found"
            )

        return expense

    finally:
        db.close()


@app.post("/expenses")
def add_expense(expense: ExpenseCreate):
    db = SessionLocal()

    new_expense = Expense(
        title=expense.title,
        amount=expense.amount,
        category=expense.category,
        date=expense.date
    )

    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)

    db.close()

    return new_expense

@app.put("/expenses/{expense_id}")
def update_expense(expense_id: int, expense: ExpenseCreate):
    db = SessionLocal()

    existing_expense = db.query(Expense).filter(
        Expense.id == expense_id
    ).first()

    if existing_expense is None:
        db.close()
        raise HTTPException(status_code=404, detail="Expense not found")

    existing_expense.title = expense.title
    existing_expense.amount = expense.amount
    existing_expense.category = expense.category
    existing_expense.date =expense.date

    db.commit()
    db.refresh(existing_expense)

    db.close()

    return existing_expense

@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int):
    db = SessionLocal()

    existing_expense = db.query(Expense).filter(
        Expense.id == expense_id
    ).first()

    if existing_expense is None:
        db.close()
        raise HTTPException(status_code=404, detail="Expense not found")

    db.delete(existing_expense)
    db.commit()

    db.close()

    return {"message": "Expense deleted successfully"}