from fastapi import FastAPI, HTTPException, Query,Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel,Field
from datetime import date

from database import engine, Base, SessionLocal
from models import Expense,Budget,User
from auth import hash_password, verify_password, create_access_token,verify_token

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="login"
)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_username(
    token: str = Depends(oauth2_scheme)
):
    username = verify_token(token)

    if username is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    return username

def get_current_user(
    username: str = Depends(get_current_username),
    db=Depends(get_db)
):
    user = db.query(User).filter(
        User.username == username
    ).first()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user

Base.metadata.create_all(bind=engine)


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1)
    amount: float = Field(gt=0, le=1000000)
    category: str = Field(min_length=1)
    date: date


class BudgetCreate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    amount: float = Field(gt=0, le=100000000)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=5, max_length=100)
    password: str = Field(min_length=6, max_length=100)


class ExpenseResponse(BaseModel):
    id: int
    title: str
    amount: float
    category: str
    date: date
    user_id: int

class BudgetResponse(BaseModel):
    id: int
    year: int
    month: int
    amount: float
    user_id: int


class UserResponse(BaseModel):
    id: int
    username: str
    email: str

class RegisterResponse(BaseModel):
    message: str
    user_id: int
    username: str
    email: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str

@app.post("/register",response_model=RegisterResponse)
def register_user(user: UserCreate, db=Depends(get_db)):
    existing_user = db.query(User).filter(
        User.username == user.username
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    existing_email = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    hashed_password = hash_password(user.password)

    new_user = User(
        username=user.username,
        email=user.email,
        password=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "user_id": new_user.id,
        "username": new_user.username,
        "email": new_user.email
    }

@app.post("/login",response_model=LoginResponse)
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db)
):
    existing_user = db.query(User).filter(
        User.username == form_data.username
    ).first()

    if existing_user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not verify_password(
        form_data.password,
        existing_user.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    access_token = create_access_token({
        "sub": existing_user.username
    })

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@app.get("/protected")
def protected_route(
    username: str = Depends(get_current_username)
):
    return {
        "message": "You are authenticated",
        "username": username
    }

@app.get("/")
def home():
    return {"message": "Expense Tracker API is running!"}

@app.get("/expenses",response_model=list[ExpenseResponse])
def get_expenses(
    sort: str = Query(
        "date_desc",
        pattern="^(amount_desc|amount_asc|date_desc|date_asc)$"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    query = db.query(Expense).filter(
        Expense.user_id == current_user.id
    )

    if sort == "amount_desc":
        query = query.order_by(Expense.amount.desc())
    elif sort == "amount_asc":
        query = query.order_by(Expense.amount.asc())
    elif sort == "date_asc":
        query = query.order_by(Expense.date.asc())
    else:
        query = query.order_by(Expense.date.desc())

    expenses = query.offset(skip).limit(limit).all()

    return expenses

@app.get("/expenses/summary")
def expense_summary(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id
    ).all()

    total_expenses = len(expenses)
    total_amount = sum(
        expense.amount for expense in expenses
    )

    return {
        "total_expenses": total_expenses,
        "total_amount": total_amount
    }

@app.get("/expenses/summary/category")
def category_summary(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id
    ).all()

    summary = {}

    for expense in expenses:
        if expense.category in summary:
            summary[expense.category] += expense.amount
        else:
            summary[expense.category] = expense.amount

    return summary

@app.get("/expenses/summary/month")
def monthly_summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.date >= date(year, month, 1),
        Expense.date < date(
            year + (month == 12),
            1 if month == 12 else month + 1,
            1
        )
    ).all()

    total_expenses = len(expenses)

    total_amount = sum(
        expense.amount for expense in expenses
    )

    return {
        "year": year,
        "month": month,
        "total_expenses": total_expenses,
        "total_amount": total_amount
    }

@app.get("/expenses/filter",response_model=list[ExpenseResponse])
def filter_expenses(
    start_date: date,
    end_date: date,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="Start date cannot be after end date"
        )

    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.date >= start_date,
        Expense.date <= end_date
    ).all()

    return expenses

@app.get("/expenses/search",response_model=list[ExpenseResponse])
def search_expenses(
    keyword: str = Query(..., min_length=1),
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.title.ilike(f"%{keyword}%")
    ).all()

    return expenses

@app.get("/expenses/filter/category",response_model=list[ExpenseResponse])
def filter_by_category(
    category: str = Query(..., min_length=1),
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.category.ilike(category)
    ).all()

    return expenses

@app.get("/expenses/summary/category/{category}")
def category_detail(
    category: str,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.category.ilike(category)
    ).all()

    total_expenses = len(expenses)

    total_amount = sum(
        expense.amount for expense in expenses
    )

    return {
        "category": category,
        "total_expenses": total_expenses,
        "total_amount": total_amount
    }

@app.get("/expenses/summary/top-category")
def top_category(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id
    ).all()

    if not expenses:
        return {
            "message": "No expenses found"
        }

    summary = {}

    for expense in expenses:
        if expense.category in summary:
            summary[expense.category] += expense.amount
        else:
            summary[expense.category] = expense.amount

    top_category = max(
        summary,
        key=summary.get
    )

    return {
        "category": top_category,
        "total_amount": summary[top_category]
    }

@app.get("/expenses/summary/average")
def average_expense(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id
    ).all()

    if not expenses:
        return {
            "message": "No expenses found"
        }

    total_amount = sum(
        expense.amount for expense in expenses
    )

    total_expenses = len(expenses)

    average_amount = total_amount / total_expenses

    return {
        "total_expenses": total_expenses,
        "average_amount": average_amount
    }
@app.get("/expenses/summary/highest")
def highest_expense(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expense = db.query(Expense).filter(
        Expense.user_id == current_user.id
    ).order_by(
        Expense.amount.desc()
    ).first()

    if expense is None:
        return {
            "message": "No expenses found"
        }

    return {
        "id": expense.id,
        "title": expense.title,
        "amount": expense.amount,
        "category": expense.category,
        "date": expense.date
    }

@app.get("/expenses/summary/lowest")
def lowest_expense(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expense = db.query(Expense).filter(
        Expense.user_id == current_user.id
    ).order_by(
        Expense.amount.asc()
    ).first()

    if expense is None:
        return {
            "message": "No expenses found"
        }

    return {
        "id": expense.id,
        "title": expense.title,
        "amount": expense.amount,
        "category": expense.category,
        "date": expense.date
    }

@app.get("/expenses/recent",response_model=list[ExpenseResponse])
def recent_expenses(
    limit: int = Query(5, ge=1, le=50),
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id
    ).order_by(
        Expense.date.desc()
    ).limit(limit).all()

    return expenses

@app.get("/expenses/recent/category",response_model=list[ExpenseResponse])
def recent_by_category(
    category: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=50),
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.category.ilike(category)
    ).order_by(
        Expense.date.desc()
    ).limit(limit).all()

    return expenses

@app.get("/expenses/summary/count-by-category")
def count_by_category(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id
    ).all()

    summary = {}

    for expense in expenses:
        if expense.category in summary:
            summary[expense.category] += 1
        else:
            summary[expense.category] = 1

    return summary

@app.get("/expenses/summary/percentage-by-category")
def percentage_by_category(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id
    ).all()

    if not expenses:
        return {}

    total_amount = sum(
        expense.amount for expense in expenses
    )

    summary = {}

    for expense in expenses:
        if expense.category in summary:
            summary[expense.category] += expense.amount
        else:
            summary[expense.category] = expense.amount

    percentage = {}

    for category, amount in summary.items():
        percentage[category] = round(
            (amount / total_amount) * 100,
            2
        )

    return percentage

@app.post("/budgets",response_model=list[ExpenseResponse])
def create_budget(
    budget: BudgetCreate,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    existing_budget = db.query(Budget).filter(
        Budget.year == budget.year,
        Budget.month == budget.month,
        Budget.user_id == current_user.id
    ).first()

    if existing_budget:
        raise HTTPException(
            status_code=400,
            detail="Budget already exists for this month"
        )

    new_budget = Budget(
        year=budget.year,
        month=budget.month,
        amount=budget.amount,
        user_id=current_user.id
    )

    db.add(new_budget)
    db.commit()
    db.refresh(new_budget)

    return new_budget

@app.get("/budgets/month/status")
def budget_status(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    budget = db.query(Budget).filter(
        Budget.year == year,
        Budget.month == month,
        Budget.user_id == current_user.id
    ).first()

    if budget is None:
        raise HTTPException(
            status_code=404,
            detail="Budget not found for this month"
        )

    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.date >= date(year, month, 1),
        Expense.date < date(
            year + (month == 12),
            1 if month == 12 else month + 1,
            1
        )
    ).all()

    total_spent = sum(
        expense.amount for expense in expenses
    )

    remaining = budget.amount - total_spent

    percentage_used = round(
        (total_spent / budget.amount) * 100,
        2
    )

    if remaining >= 0:
        percentage_remaining = round(
            (remaining / budget.amount) * 100,
            2
        )
        status = "Within Budget"
    else:
        percentage_remaining = 0
        status = "Over Budget"

    return {
        "year": year,
        "month": month,
        "budget": budget.amount,
        "total_spent": total_spent,
        "remaining": remaining,
        "percentage_used": percentage_used,
        "percentage_remaining": percentage_remaining,
        "status": status
    }

@app.put("/budgets/{budget_id}",response_model=list[ExpenseResponse])
def update_budget(
    budget_id: int,
    budget: BudgetCreate,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    existing_budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.user_id == current_user.id
    ).first()

    if existing_budget is None:
        raise HTTPException(
            status_code=404,
            detail="Budget not found"
        )

    duplicate_budget = db.query(Budget).filter(
        Budget.year == budget.year,
        Budget.month == budget.month,
        Budget.user_id == current_user.id,
        Budget.id != budget_id
    ).first()

    if duplicate_budget is not None:
        raise HTTPException(
            status_code=400,
            detail="Budget already exists for this month"
        )

    existing_budget.year = budget.year
    existing_budget.month = budget.month
    existing_budget.amount = budget.amount

    db.commit()
    db.refresh(existing_budget)

    return existing_budget

@app.delete("/budgets/{budget_id}")
def delete_budget(
    budget_id: int,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    existing_budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.user_id == current_user.id
    ).first()

    if existing_budget is None:
        raise HTTPException(
            status_code=404,
            detail="Budget not found"
        )

    db.delete(existing_budget)
    db.commit()

    return {
        "message": "Budget deleted successfully"
    }

@app.get("/expenses/summary/month/report")
def monthly_report(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.date >= date(year, month, 1),
        Expense.date < date(
            year + (month == 12),
            1 if month == 12 else month + 1,
            1
        )
    ).all()

    total_expenses = len(expenses)

    total_spent = sum(
        expense.amount for expense in expenses
    )

    average_expense = round(
        total_spent / total_expenses,
        2
    ) if total_expenses > 0 else 0

    category_summary = {}
    category_count = {}

    for expense in expenses:
        if expense.category in category_summary:
            category_summary[expense.category] += expense.amount
            category_count[expense.category] += 1
        else:
            category_summary[expense.category] = expense.amount
            category_count[expense.category] = 1

    if category_summary:
        highest_category = max(
            category_summary,
            key=category_summary.get
        )
        highest_category_amount = category_summary[highest_category]

        lowest_category = min(
            category_summary,
            key=category_summary.get
        )
        lowest_category_amount = category_summary[lowest_category]
    else:
        highest_category = None
        highest_category_amount = 0
        lowest_category = None
        lowest_category_amount = 0

    budget = db.query(Budget).filter(
        Budget.year == year,
        Budget.month == month,
        Budget.user_id == current_user.id
    ).first()

    if budget is None:
        return {
            "year": year,
            "month": month,
            "total_expenses": total_expenses,
            "total_spent": total_spent,
            "average_expense": average_expense,
            "category_summary": category_summary,
            "category_count": category_count,
            "highest_category": highest_category,
            "highest_category_amount": highest_category_amount,
            "lowest_category": lowest_category,
            "lowest_category_amount": lowest_category_amount,
            "budget": None,
            "remaining": None,
            "percentage_used": None,
            "percentage_remaining": None,
            "status": "No Budget Set"
        }

    remaining = budget.amount - total_spent

    percentage_used = round(
        (total_spent / budget.amount) * 100,
        2
    )

    percentage_remaining = round(
        ((budget.amount - total_spent) / budget.amount) * 100,
        2
    )

    if total_spent > budget.amount:
        status = "Over Budget"
    else:
        status = "Within Budget"

    if percentage_used > 100:
        utilization_level = "Exceeded"
    elif percentage_used > 80:
        utilization_level = "High"
    elif percentage_used >= 50:
        utilization_level = "Moderate"
    else:
        utilization_level = "Low"

    return {
        "year": year,
        "month": month,
        "total_expenses": total_expenses,
        "total_spent": total_spent,
        "average_expense": average_expense,
        "category_summary": category_summary,
        "category_count": category_count,
        "highest_category": highest_category,
        "highest_category_amount": highest_category_amount,
        "lowest_category": lowest_category,
        "lowest_category_amount": lowest_category_amount,
        "budget": budget.amount,
        "remaining": remaining,
        "percentage_used": percentage_used,
        "percentage_remaining": percentage_remaining,
        "status": status,
        "utilization_level": utilization_level
    }

@app.get("/expenses/{expense_id}",response_model=ExpenseResponse)
def get_expense(
    expense_id: int,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()

    if expense is None:
        raise HTTPException(
            status_code=404,
            detail="Expense not found"
        )

    return expense

@app.post("/expenses",response_model=ExpenseResponse)
def create_expense(
    expense: ExpenseCreate,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    new_expense = Expense(
        title=expense.title,
        amount=expense.amount,
        category=expense.category,
        date=expense.date,
        user_id=current_user.id
    )

    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)

    return new_expense

@app.get("/budgets/month",response_model=list[ExpenseResponse])
def get_monthly_budget(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    budget = db.query(Budget).filter(
        Budget.year == year,
        Budget.month == month,
        Budget.user_id == current_user.id
    ).first()

    if budget is None:
        raise HTTPException(
            status_code=404,
            detail="Budget not found for this month"
        )

    return budget

@app.put("/expenses/{expense_id}",response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    expense: ExpenseCreate,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    existing_expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()

    if existing_expense is None:
        raise HTTPException(
            status_code=404,
            detail="Expense not found"
        )

    existing_expense.title = expense.title
    existing_expense.amount = expense.amount
    existing_expense.category = expense.category
    existing_expense.date = expense.date

    db.commit()
    db.refresh(existing_expense)

    return existing_expense

@app.delete("/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    existing_expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()

    if existing_expense is None:
        raise HTTPException(
            status_code=404,
            detail="Expense not found"
        )

    db.delete(existing_expense)
    db.commit()

    return {
        "message": "Expense deleted successfully"
    }