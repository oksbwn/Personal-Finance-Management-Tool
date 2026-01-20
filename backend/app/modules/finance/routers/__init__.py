from fastapi import APIRouter
from .accounts import router as accounts_router
from .transactions import router as transactions_router
from .categories import router as categories_router
from .budgets import router as budgets_router
from .recurring import router as recurring_router
from .analytics import router as analytics_router
from .mutual_funds import router as mutual_funds_router

router = APIRouter()

router.include_router(accounts_router, tags=["Accounts"])
router.include_router(transactions_router, tags=["Transactions"])
router.include_router(categories_router, tags=["Categories"])
router.include_router(budgets_router, tags=["Budgets"])
router.include_router(recurring_router, tags=["Recurring"])
router.include_router(analytics_router, tags=["Analytics"])
router.include_router(mutual_funds_router, tags=["Mutual Funds"])
