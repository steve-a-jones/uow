from dataclasses import dataclass
from typing import Callable, Optional, Protocol, TypeAlias


@dataclass(frozen=True)
class NewUser:
    email: str


@dataclass(frozen=True)
class User:
    id: int
    email: str


@dataclass(frozen=True)
class NewInvoice:
    user_id: int
    amount_cents: int


@dataclass(frozen=True)
class Invoice:
    id: int
    user_id: int
    amount_cents: int


@dataclass(frozen=True)
class AuditEntry:
    message: str


# INTERFACES FOR REPOS THAT SERVE THE BUSINESS DOMAIN
class IUserRepo(Protocol):
    def get(self, user_id: int) -> Optional[User]: ...

    def add(self, user: NewUser) -> User: ...


class IInvoiceRepo(Protocol):
    def add(self, invoice: NewInvoice) -> Invoice: ...


class IAuditRepo(Protocol):
    def record(self, entry: AuditEntry) -> None: ...


# could potentially have many unit of works that are combos
# of chosen repos that are relevant and applicable to various use case scenarios
# for now we demonstrate the benefits without addressing this potential need
class IUnitOfWork(Protocol):
    user_repo: IUserRepo
    invoice_repo: IInvoiceRepo
    audit_repo: IAuditRepo

    def __enter__(self) -> "IUnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> bool: ...
    def flush(self) -> None: ...


UowFactory: TypeAlias = Callable[[], IUnitOfWork]
