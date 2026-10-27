from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers.accounts import router as accounts_router
from app.routers.transfers import router as transfers_router
from app.errors import LedgerError

app = FastAPI(title="Transaction Ledger API", version="0.1.0")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(transfers_router, prefix="/api/v1")


@app.exception_handler(LedgerError)
async def ledger_error_handler(_: Request, exc: LedgerError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "details": details,
            }
        },
    )


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
