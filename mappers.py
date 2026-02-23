from db_models import DBAuditRow, DBInvoiceRow, DBUserRow
from domain_models import (
    AuditEntry,
    Invoice,
    NewInvoice,
    NewUser,
    User,
)


class DomainEntityMapper:
    @staticmethod
    def new_user_to_row(user: NewUser) -> DBUserRow:
        return DBUserRow(email=user.email)

    @staticmethod
    def user_row_to_domain(row: DBUserRow) -> User:
        return User(id=row.id, email=row.email)

    @staticmethod
    def new_invoice_to_row(invoice: NewInvoice) -> DBInvoiceRow:
        return DBInvoiceRow(user_id=invoice.user_id, amount_cents=invoice.amount_cents)

    @staticmethod
    def invoice_row_to_domain(row: DBInvoiceRow) -> Invoice:
        return Invoice(id=row.id, user_id=row.user_id, amount_cents=row.amount_cents)

    @staticmethod
    def audit_entry_to_row(entry: AuditEntry) -> DBAuditRow:
        return DBAuditRow(message=entry.message)
