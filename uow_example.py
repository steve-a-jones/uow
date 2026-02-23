from domain_impl import create_uow
from services import UserService, AuditService, BillingService

def purchase_workflow_use_case(
    user_service: UserService,
    audit_service: AuditService,
    billing_service: BillingService
) -> int:
    user_id = user_service.register_user('michelle@example.com')
    invoice_id = billing_service.create_invoice(user_id, 10000)
    audit_service.record(f"purchase: user_id={user_id} invoice_id={invoice_id}")
    return invoice_id

def main() -> None:

    # All work within the block are covered by a transaction
    # caveat here is that these service instances must be ephemeral and scoped to the unit of work  -- meaning that they can only live within the uow block.
    # We can evolve our pattern to make this more obvious
    with create_uow() as uow:
        invoice_id = purchase_workflow_use_case(
            user_service=UserService(uow.user_repo),
            audit_service=AuditService(uow.audit_repo),
            billing_service=BillingService(uow.user_repo, uow.invoice_repo),
        )

        print("invoice_id:", invoice_id)

if __name__ == "__main__":
    main()