from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth, orders, inventory, dashboard, ai, alerts
from app.seed import seed_all

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(inventory.router)
app.include_router(dashboard.router)
app.include_router(ai.router)
app.include_router(alerts.router)


@app.on_event("startup")
def startup():
    seed_all()


@app.get("/")
def root():
    return {"message": f"{settings.app_name} API is running"}
