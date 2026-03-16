from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .routers import accounts, analytics, categories, health, imports, internal_accounts, moments, payees, profile, rules, transactions

app = FastAPI(title="Personal Expense Tracker", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.demo_mode:
    from .middleware.demo_guard import DemoGuardMiddleware

    app.add_middleware(DemoGuardMiddleware)

app.include_router(health.router)
app.include_router(imports.router)
app.include_router(transactions.router)
app.include_router(payees.router)
app.include_router(internal_accounts.router)
app.include_router(categories.router)
app.include_router(analytics.router)
app.include_router(moments.router)
app.include_router(accounts.router)
app.include_router(rules.router)
app.include_router(profile.router)

_avatars_dir = Path(settings.avatars_storage_dir)
_avatars_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/avatars", StaticFiles(directory=str(_avatars_dir)), name="avatars")
