from domain_models import (
    AuditEntry,
    IAuditRepo,
    IInvoiceRepo,
    IUserRepo,
    NewInvoice,
    NewUser,
)

class AuditService:
    def __init__(self, audit_repo: IAuditRepo):
        self.audit_repo = audit_repo

    def record(self, message: str) -> None:
        self.audit_repo.record(AuditEntry(message=message))

class UserService:
    def __init__(self, user_repo: IUserRepo):
        self.user_repo = user_repo

    def register_user(self, email: str) -> int:
        created_user = self.user_repo.add(NewUser(email=email))
        return created_user.id

class BillingService:
    def __init__(self, user_repo: IUserRepo, invoice_repo: IInvoiceRepo):
        self.user_repo = user_repo
        self.invoice_repo = invoice_repo

    def create_invoice(self, user_id: int, amount_cents: int) -> int:
        if self.user_repo.get(user_id) is None:
            raise ValueError("user not found")
        created_invoice = self.invoice_repo.add(
            NewInvoice(user_id=user_id, amount_cents=amount_cents)
        )
        return created_invoice.id
