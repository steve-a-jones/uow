from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol, TypeAlias

from sqlalchemy import ForeignKey, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

# ============================================================
# CORE (ports + app logic)
# ============================================================

class UserRepo(Protocol):
    def get_email(self, user_id: int) -> Optional[str]: ...
    def add_user(self, email: str) -> int: ...

# class ClaimInterface(Protocol):
#     def addClaim(self,ClaimInfo: ClaimInfo) -> int: ...
#
# class DoubleClaimImpl(ClaimInterface):
#     def addClaim(self,ClaimInfo: ClaimInfo) -> int:
#         legacyAddClaim(ClaimInfo)
#         snapshotAddClaim(ClaimInfo)

#legacyAddClaim
#snapshotAddClaim

class InvoiceRepo(Protocol):
    def add_invoice(self, user_id: int, amount_cents: int) -> int: ...


class AuditRepo(Protocol):
    def record(self, message: str) -> None: ...


class UnitOfWork(Protocol):
    users: UserRepo
    invoices: InvoiceRepo
    audit: AuditRepo

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> bool: ...
    def flush(self) -> None: ...


UowFactory: TypeAlias = Callable[[], UnitOfWork]


@dataclass(frozen=True)
class BillingService:
    def create_invoice(self, uow: UnitOfWork, user_id: int, amount_cents: int) -> int:
        if uow.users.get_email(user_id) is None:
            raise ValueError("user not found")
        return uow.invoices.add_invoice(user_id, amount_cents)


@dataclass(frozen=True)
class UserService:
    def register_user(self, uow: UnitOfWork, email: str) -> int:
        return uow.users.add_user(email)


def create_claim(claimArgs):
    db.session.add(Claim(claimArgs))

@dataclass(frozen=True)
class AuditService:
    def record(self, uow: UnitOfWork, message: str) -> None:
        uow.audit.record(message)


def purchase_workflow(
    uow: UnitOfWork,
    user_svc: UserService,
    billing_svc: BillingService,
    audit_svc: AuditService,
    *,
    email: str,
    amount_cents: int,
) -> int:
    # Step 1: create user (needs DB-generated id)
    user_id = user_svc.register_user(uow, email)

    # create_claim(claim_args)

    # Step 2: create invoice referencing that id
    invoice_id = billing_svc.create_invoice(uow, user_id, amount_cents)

    # Step 3: record audit log (same transaction)
    audit_svc.record(uow, f"purchase: user_id={user_id} invoice_id={invoice_id} amount={amount_cents}")

    return invoice_id


# ============================================================
# INFRA (SQLAlchemy implementation)
# ============================================================

class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str]


class InvoiceRow(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount_cents: Mapped[int]


class AuditRow(Base):
    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message: Mapped[str]


class SqlAlchemyUserRepo(UserRepo):
    def __init__(self, session: Session):
        self._s = session

    def get_email(self, user_id: int) -> Optional[str]:
        row = self._s.get(UserRow, user_id)
        return row.email if row else None

    def add_user(self, email: str) -> int:
        row = UserRow(email=email)
        self._s.add(row)
        self._s.flush()  # ensures row.id assigned
        return row.id


class SqlAlchemyInvoiceRepo(InvoiceRepo):
    def __init__(self, session: Session):
        self._s = session

    def add_invoice(self, user_id: int, amount_cents: int) -> int:
        row = InvoiceRow(user_id=user_id, amount_cents=amount_cents)
        self._s.add(row)
        self._s.flush()
        return row.id


class SqlAlchemyAuditRepo(AuditRepo):
    def __init__(self, session: Session):
        self._s = session

    def record(self, message: str) -> None:
        self._s.add(AuditRow(message=message))
        # no flush needed


@dataclass(frozen=True)
class UowDeps:
    users: UserRepo
    invoices: InvoiceRepo
    audit: AuditRepo


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(
        self,
        session_factory: Callable[[], Session],
        deps_factory: Callable[[Session], UowDeps],
    ):
        self._sf = session_factory
        self._deps_factory = deps_factory
        self._session: Optional[Session] = None

        self.users: UserRepo
        self.invoices: InvoiceRepo
        self.audit: AuditRepo

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._sf()
        self._session.begin()

        deps = self._deps_factory(self._session)
        self.users = deps.users
        self.invoices = deps.invoices
        self.audit = deps.audit
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        assert self._session is not None
        try:
            if exc_type is None:
                self._session.commit()
            else:
                self._session.rollback()
        finally:
            self._session.close()
        return False

    def flush(self) -> None:
        assert self._session is not None
        self._session.flush()


def make_uow_factory(SessionFactory: sessionmaker) -> UowFactory:
    def deps_factory(s: Session) -> UowDeps:
        return UowDeps(
            users=SqlAlchemyUserRepo(s),
            invoices=SqlAlchemyInvoiceRepo(s),
            audit=SqlAlchemyAuditRepo(s),
        )

    return lambda: SqlAlchemyUnitOfWork(SessionFactory, deps_factory)


# ============================================================
# MULTI-STEP WORKFLOW USING "with" (no run_in_uow)
# ============================================================

def main() -> None:
    engine = create_engine("sqlite+pysqlite:///workflow_with_uow.sqlite", future=True)
    Base.metadata.create_all(engine)

    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    uow_factory = make_uow_factory(SessionFactory)

    user_svc = UserService()
    billing_svc = BillingService()
    audit_svc = AuditService()

    with uow_factory() as uow:
        invoice_id = purchase_workflow(
            uow,
            user_svc,
            billing_svc,
            audit_svc,
            email="a@example.com",
            amount_cents=12345,
        )
        print("invoice_id:", invoice_id)


if __name__ == "__main__":
    main()