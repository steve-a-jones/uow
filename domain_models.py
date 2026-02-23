from dataclasses import dataclass
from typing import Callable, Optional, Protocol, TypeAlias

class UserRepo(Protocol):
    def get_email(self, user_id: int) -> Optional[str]: ...
    def add_user(self, email: str) -> int: ...


class InvoiceRepo(Protocol):
    def add_invoice(self, user_id: int, amount_cents: int) -> int: ...

class AuditRepo(Protocol):
    def record(self, message: str) -> None: ...


# could potentially have many unit of works that are combos
# of chosen repos that are relevant and applicable to various use case scenarios
# for now we demonstrate the benefits without addressing this potential need
class UnitOfWork(Protocol):
    users: UserRepo
    invoices: InvoiceRepo
    audit: AuditRepo

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> bool: ...
    def flush(self) -> None: ...

UowFactory: TypeAlias = Callable[[], UnitOfWork]