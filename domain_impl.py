from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db_models import Base, DBUserRow

# DOMAIN MODELS TO IMPLEMENT
from domain_models import (
    IAuditRepo,
    IInvoiceRepo,
    IUnitOfWork,
    IUserRepo,
    AuditEntry,
    Invoice,
    NewInvoice,
    NewUser,
    User,
    UowFactory,
)
from mappers import DomainEntityMapper


# IMPLEMENTATIONS
class SqlAlchemyUserRepo(IUserRepo):
    def __init__(self, session: Session):
        self._s = session

    def get(self, user_id: int) -> Optional[User]:
        row = self._s.get(DBUserRow, user_id)
        return DomainEntityMapper.user_row_to_domain(row) if row else None

    def add(self, user: NewUser) -> User:
        row = DomainEntityMapper.new_user_to_row(user)
        self._s.add(row)
        self._s.flush()  # ensures row.id assigned
        return DomainEntityMapper.user_row_to_domain(row)

class SqlAlchemyInvoiceRepo(IInvoiceRepo):
    def __init__(self, session: Session):
        self._s = session

    def add(self, invoice: NewInvoice) -> Invoice:
        row = DomainEntityMapper.new_invoice_to_row(invoice)
        self._s.add(row)
        self._s.flush()
        return DomainEntityMapper.invoice_row_to_domain(row)

class SqlAlchemyAuditRepo(IAuditRepo):
    def __init__(self, session: Session):
        self._s = session

    def record(self, entry: AuditEntry) -> None:
        self._s.add(DomainEntityMapper.audit_entry_to_row(entry))
        # no flush needed

@dataclass(frozen=True)
class UowDeps:
    user_repo: IUserRepo
    invoice_repo: IInvoiceRepo
    audit_repo: IAuditRepo

class SqlAlchemyUnitOfWork(IUnitOfWork):
    def __init__(
        self,
        session_factory: Callable[[], Session],
        deps_factory: Callable[[Session], UowDeps],
    ):
        self._sf = session_factory
        self._deps_factory = deps_factory
        self._session: Optional[Session] = None

        self.user_repo: IUserRepo
        self.invoice_repo: IInvoiceRepo
        self.audit_repo: IAuditRepo

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._sf()
        self._session.begin()

        deps = self._deps_factory(self._session)
        self.user_repo = deps.user_repo
        self.invoice_repo = deps.invoice_repo
        self.audit_repo = deps.audit_repo
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

def make_uow_factory(session_factory: sessionmaker) -> UowFactory:
    def deps_factory(s: Session) -> UowDeps:
        return UowDeps(
            user_repo=SqlAlchemyUserRepo(s),
            invoice_repo=SqlAlchemyInvoiceRepo(s),
            audit_repo=SqlAlchemyAuditRepo(s),
        )

    return lambda: SqlAlchemyUnitOfWork(session_factory, deps_factory)

def create_uow():
    engine = create_engine("sqlite+pysqlite:///workflow_with_uow.sqlite", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    uow_factory = make_uow_factory(session_factory)
    return uow_factory()


# ---------- READ THIS ------------------
# Unit Of Work = "Workers" (dependencies -- we use "repos" here, but that's not the point, could be services, etc..) that all SHARE and ADHERE
# to a common concept of a "transaction".. represented here as a "Session".
# REMEMBER that only the concrete implementations are aware of the "session" concept..
# the interfaces for the repos aren't burdened with knowledge of this as they ONLY SERVER
# THE BUSINESS DOMAIN (review the interfaces for the repos above to see that they have NO NEED for a concept of a session)
# ---
# WHAT THIS MEANS:
# 1) A domain "boundary" is constituted and enforced (NO EXCEPTIONS). A line is drawn and crossing the line is made possible and safe via interfaces..
#   The interface absolves us of tightly coupling ourselves to implementation specifics. This permits us to change implementation specifics as we see fit
#   without needing to involve our business domain (unless our business domain must be extended -- which is alright).
#   If our implementation satisfies the contract (interface) then consumers of the contract proceed business-as-usual.

# 2) We can now relax and just write code against our established business domain :)
#     If we feel an urge/need to talk about the DB specifics then
#     we HAVE TO FIND A WAY TO EXTEND OUR BUSINESS DOMAIN -- THIS WILL HAPPEN AND IT'S OK.

# 3) Consumers that use these repos only see the interfaces (which serve the business domain)
# and are relieved of the burden of speaking in specifics about things like sessions and concrete db entities (like DBUserRow).
# REMEMBER: Since the interfaces only service the business domain, their method signatures MUST (NO EXCEPTION) only allow inputs
# that belong to the business domain (otherwise, the boundary is broken).
# e.g.;
#
# ****GOOD****
# Here our inputs/outputs are of the business domain -- it's the only language we speak. If translation takes places behind the scenes
# we wouldn't know and don't want to know.
# class ClaimRepo(Protocol):
#     def get_claim_by_id(self, claim_id: int) -> IClaim: ...
#     def update_claim(self, claim: IClaim, claim_update_info: IClaimUpdateRequest) -> IClaim: ...

# ****BAD****
# Here the interface leaks the DB Entity Models. Seems innocent, but the once they are across the line they infiltrate all parts of the domain
# super-glueing themselves to our precious business logic, weighing us down and making it hard for the application to evolve/change
# without major refactors.
# class ClaimRepo(Protocol):
#     def get_claim_by_id(self, claim_id: int) -> DBClaim: ...
#     def update_claim(self, claim: IClaim, claim_update_info: IClaimUpdateRequest) -> DBClaim: ...


# 4) NOTHING IS FREE. The trade-off here (we're honestly lucky that the cost is so low for the value we get in return)
# is that we must now find way to "cross the line" from our abstract business domain to the concrete world where concrete specifics (like DB entities)
# matter. DOMAIN ENTITY MAPPERS are needed, but they are easier to manage (AND TEST, #DO_IT_WITH_AI) and are pure functions that simply map types --
# e.g.;
# IClaimToDBClaim(claim: IClaim) -> DBClaim
# DBClaimToIClaim(dbClaim: DBClaim) -> IClaim
# **NOTE** Mappers reside where domain reconstruction is needed (so they reside near the implementation specifics) **

# In practice this would look something like...

# File: app/infrastructure/db/sqlalchemy/claim_mappers.py
# Here we translate: business domain -> db entity
# def order_domain_to_new_row(order: Order) -> OrderRow:
#     """
#     Convert a domain Order to a NEW persistence row object.
#     Useful for inserts.
#     """
#     return OrderRow(
#         id=str(order.id),
#         customer_id=order.customer_id,
#         total_cents=order.total.cents,
#         currency_code=str(order.total.currency).upper(),
#         status=order.status.value,
#     )
#
# # Here we translate: DB Entity -> Business Domain
# def order_row_to_domain(row: OrderRow) -> Order:
#     """
#     Reconstruct a domain Order from a persistence row.
#
#     This is a PURE function:
#       - no DB calls
#       - no session access
#       - deterministic for the given row input
#     """
#     return Order(
#         id=OrderId(row.id),
#         customer_id=row.customer_id,
#         total=Money(
#             cents=row.total_cents,
#             currency=_currency_from_db(row.currency_code),
#         ),
#         status=_status_from_db(row.status),
#     )
# ------------
# -----------
# What is looks like in your concrete repo (that implements the generic interface):
# File: app/infrastructure/db/sqlalchemy/order_repository.py
# class SqlAlchemyOrderRepository(OrderRepo):
#     def __init__(self, session: Session) -> None:
#         self._session = session
#
#     # Input = Business domain, Output = Business Domain
#     # Any translation happens internally
#     def get(self, order_id: OrderId) -> Optional[Order]:
#         row = self._session.get(OrderRow, str(order_id))
#         return maybe_order_row_to_domain(row) # translate from db entity back to business domain (as our interface contract requires)
#
#    # Input = Business domain, Output = None (bc this is a Void function.. side effect only)
#     def save(self, order: Order) -> None:
#           self._session.add(
#                order_domain_to_new_row(order) # translate business domain to db entity for saving
#           )


# READ ABOVE UNTIL IT CLICKS. DO NOT PASS GO UNTIL YOU "SEE IT". IT WILL FEEL DIFFERENT, AND THATS OK.
