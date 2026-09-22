from fastapi import FastAPI, HTTPException
from pydantic import BaseModel,Field
from datetime import date

from database import engine, Base, SessionLocal
from models import Expense

app = FastAPI()

Base.metadata.create_all(bind=engine)


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1)
    amount: float = Field(gt=0)
    category: str =Field(min_length=1)
    date: date


@app.get("/")
def home():
    return {"message": "Expense Tracker API is running!"}


@app.get("/expenses")
def get_expenses():
    db = SessionLocal()

    expenses = db.query(Expense).all()

    db.close()

    return expenses

@app.get("/expenses/{expense_id}")
def get_expense(expense_id: int):
    db = SessionLocal()

    expense = db.query(Expense).filter(
        Expense.id == expense_id
    ).first()

    if expense is None:
        db.close()
        raise HTTPException(status_code=404, detail="Expense not found")

    db.close()

    return expense

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