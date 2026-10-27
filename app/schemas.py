import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized


class AccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    balance: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at")
    @classmethod
    def created_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class TransactionCreate(BaseModel):
    type: Literal["credit", "debit"]
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    description: str = Field(min_length=1, max_length=500)
    reference_id: str = Field(min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @field_validator("description", "reference_id")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class TransactionResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    type: Literal["credit", "debit"]
    amount: Decimal
    description: str
    reference_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at")
    @classmethod
    def created_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class BalanceResponse(BaseModel):
    account_id: uuid.UUID
    balance: Decimal


class PaginationResponse(BaseModel):
    current_page: int
    page_size: int
    total_records: int
    total_pages: int


class TransactionHistoryResponse(BaseModel):
    items: list[TransactionResponse]
    pagination: PaginationResponse


class TransferCreate(BaseModel):
    source_account_id: uuid.UUID
    destination_account_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    description: str = Field(min_length=1, max_length=500)
    reference_id: str = Field(min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @field_validator("description", "reference_id")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @model_validator(mode="after")
    def accounts_must_differ(self) -> "TransferCreate":
        if self.source_account_id == self.destination_account_id:
            raise ValueError("source and destination accounts must be different")
        return self


class TransferResponse(BaseModel):
    transfer_id: uuid.UUID
    debit: TransactionResponse
    credit: TransactionResponse
