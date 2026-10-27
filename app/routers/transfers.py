from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import TransferCreate, TransferResponse
from app.services.ledger import post_transfer

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post("", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(
    payload: TransferCreate,
    db: Session = Depends(get_db),
) -> TransferResponse:
    transfer_id, debit, credit = post_transfer(db, payload)
    return TransferResponse(transfer_id=transfer_id, debit=debit, credit=credit)
