from domain_models import AuditRepo, UserRepo, InvoiceRepo

class AuditService:
    def __init__(self, audit_repo: AuditRepo):
        self.audit_repo = audit_repo

    def record(self, message: str) -> None:
        self.audit_repo.record(message)

class UserService:
    def __init__(self, user_repo: UserRepo):
        self.user_repo = user_repo

    def register_user(self, email: str) -> int:
        return self.user_repo.add_user(email)

class BillingService:
    def __init__(self, user_repo: UserRepo, invoice_repo: InvoiceRepo):
        self.user_repo = user_repo
        self.invoice_repo = invoice_repo

    def create_invoice(self, user_id: int, amount_cents: int) -> int:
        if self.user_repo.get_email(user_id) is None:
            raise ValueError("user not found")
        return self.invoice_repo.add_invoice(user_id, amount_cents)