import math
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account
from app.schemas import (
    AccountCreate,
    AccountResponse,
    BalanceResponse,
    PaginationResponse,
    TransactionCreate,
    TransactionHistoryResponse,
    TransactionResponse,
)
from app.services.ledger import (
    get_account_balance,
    get_transaction_history,
    post_transaction,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> Account:
    account = Account(name=payload.name)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/{account_id}/balance", response_model=BalanceResponse)
def read_account_balance(account_id: uuid.UUID, db: Session = Depends(get_db)) -> BalanceResponse:
    balance = get_account_balance(db, account_id)
    return BalanceResponse(account_id=account_id, balance=balance)


@router.post(
    "/{account_id}/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    account_id: uuid.UUID,
    payload: TransactionCreate,
    db: Session = Depends(get_db),
) -> TransactionResponse:
    return post_transaction(db, account_id, payload)


@router.get("/{account_id}/transactions", response_model=TransactionHistoryResponse)
def read_transaction_history(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    transaction_type: Annotated[Literal["credit", "debit"] | None, Query(alias="type")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TransactionHistoryResponse:
    transactions, total = get_transaction_history(
        db, account_id, transaction_type, page, limit
    )
    return TransactionHistoryResponse(
        items=transactions,
        pagination=PaginationResponse(
            current_page=page,
            page_size=limit,
            total_records=total,
            total_pages=math.ceil(total / limit),
        ),
    )
