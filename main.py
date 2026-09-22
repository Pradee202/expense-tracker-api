from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from database import engine, Base, SessionLocal
from models import Expense

app = FastAPI()

Base.metadata.create_all(bind=engine)


class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str


@app.get("/")
def home():
    return {"message": "Expense Tracker API is running!"}


@app.get("/expenses")
def get_expenses():
    db = SessionLocal()

    expenses = db.query(Expense).all()

    db.close()

    return expenses


@app.post("/expenses")
def add_expense(expense: ExpenseCreate):
    db = SessionLocal()

    new_expense = Expense(
        title=expense.title,
        amount=expense.amount,
        category=expense.category
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