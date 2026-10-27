import uuid
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import LedgerError
from app.models import MAX_BALANCE_CENTS, Account, LedgerTransaction
from app.schemas import TransactionCreate, TransferCreate


def _amount_to_cents(amount: Decimal) -> int:
    return int(amount * 100)


def _get_account(db: Session, account_id: uuid.UUID) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise LedgerError(404, "account_not_found", "Account was not found.")
    return account


def _ensure_reference_is_new(
    db: Session,
    account_ids: tuple[uuid.UUID, ...],
    reference_id: str,
) -> None:
    existing = db.scalar(
        select(LedgerTransaction.id)
        .where(
            LedgerTransaction.account_id.in_(account_ids),
            LedgerTransaction.reference_id == reference_id,
        )
        .limit(1)
    )
    if existing is not None:
        raise LedgerError(
            409,
            "duplicate_transaction",
            "A transaction with this reference_id already exists for the account.",
        )


def _change_balance(
    db: Session,
    account_id: uuid.UUID,
    amount_cents: int,
    transaction_type: str,
) -> None:
    conditions = [Account.id == account_id]
    if transaction_type == "debit":
        conditions.append(Account.balance_cents >= amount_cents)
        new_balance = Account.balance_cents - amount_cents
    else:
        conditions.append(Account.balance_cents <= MAX_BALANCE_CENTS - amount_cents)
        new_balance = Account.balance_cents + amount_cents

    result = db.execute(update(Account).where(*conditions).values(balance_cents=new_balance))
    if result.rowcount == 1:
        return

    if db.get(Account, account_id) is None:
        raise LedgerError(404, "account_not_found", "Account was not found.")
    if transaction_type == "debit":
        raise LedgerError(
            409,
            "insufficient_balance",
            "The account does not have sufficient balance for this debit.",
        )
    raise LedgerError(409, "balance_limit_exceeded", "The resulting balance exceeds the limit.")


def _raise_duplicate_if_present(
    db: Session,
    account_ids: tuple[uuid.UUID, ...],
    reference_id: str,
) -> None:
    db.rollback()
    existing = db.scalar(
        select(LedgerTransaction.id)
        .where(
            LedgerTransaction.account_id.in_(account_ids),
            LedgerTransaction.reference_id == reference_id,
        )
        .limit(1)
    )
    if existing is not None:
        raise LedgerError(
            409,
            "duplicate_transaction",
            "A transaction with this reference_id already exists for the account.",
        )


def post_transaction(
    db: Session,
    account_id: uuid.UUID,
    payload: TransactionCreate,
) -> LedgerTransaction:
    amount_cents = _amount_to_cents(payload.amount)
    try:
        with db.begin():
            _get_account(db, account_id)
            _ensure_reference_is_new(db, (account_id,), payload.reference_id)
            transaction = LedgerTransaction(
                account_id=account_id,
                type=payload.type,
                amount_cents=amount_cents,
                description=payload.description,
                reference_id=payload.reference_id,
            )
            db.add(transaction)
            db.flush()
            _change_balance(db, account_id, amount_cents, payload.type)
            db.flush()
    except IntegrityError:
        _raise_duplicate_if_present(db, (account_id,), payload.reference_id)
        raise
    db.refresh(transaction)
    return transaction


def post_transfer(db: Session, payload: TransferCreate) -> tuple[uuid.UUID, LedgerTransaction, LedgerTransaction]:
    source_id = payload.source_account_id
    destination_id = payload.destination_account_id
    account_ids = (source_id, destination_id)
    amount_cents = _amount_to_cents(payload.amount)
    transfer_id = uuid.uuid4()

    try:
        with db.begin():
            _get_account(db, source_id)
            _get_account(db, destination_id)
            _ensure_reference_is_new(db, account_ids, payload.reference_id)

            debit = LedgerTransaction(
                account_id=source_id,
                type="debit",
                amount_cents=amount_cents,
                description=payload.description,
                reference_id=payload.reference_id,
                transfer_id=transfer_id,
            )
            credit = LedgerTransaction(
                account_id=destination_id,
                type="credit",
                amount_cents=amount_cents,
                description=payload.description,
                reference_id=payload.reference_id,
                transfer_id=transfer_id,
            )
            db.add_all((debit, credit))
            db.flush()
            _change_balance(db, source_id, amount_cents, "debit")
            _change_balance(db, destination_id, amount_cents, "credit")
            db.flush()
    except IntegrityError:
        _raise_duplicate_if_present(db, account_ids, payload.reference_id)
        raise

    db.refresh(debit)
    db.refresh(credit)
    return transfer_id, debit, credit


def get_account_balance(db: Session, account_id: uuid.UUID) -> Decimal:
    account = _get_account(db, account_id)
    return account.balance


def get_transaction_history(
    db: Session,
    account_id: uuid.UUID,
    transaction_type: str | None,
    page: int,
    limit: int,
) -> tuple[list[LedgerTransaction], int]:
    _get_account(db, account_id)
    filters = [LedgerTransaction.account_id == account_id]
    if transaction_type is not None:
        filters.append(LedgerTransaction.type == transaction_type)

    total = db.scalar(select(func.count()).select_from(LedgerTransaction).where(*filters)) or 0
    transactions = list(
        db.scalars(
            select(LedgerTransaction)
            .where(*filters)
            .order_by(LedgerTransaction.created_at.desc(), LedgerTransaction.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    )
    return transactions, total
