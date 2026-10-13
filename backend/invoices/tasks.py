import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from orders.invoice_pdf import build_invoice_pdf
from .models import InvoiceSendLog, InvoiceSendStatus

logger = logging.getLogger(__name__)

RETRY_BACKOFF_SECONDS = 60


@shared_task(bind=True, max_retries=3)
def send_invoice_email(self, log_id: int):
    """E-mail an invoice PDF to the vendor and record the outcome.

    * Runs in a Celery worker, so billing requests never wait on SMTP.
    * Idempotent: a log that is already ``sent`` is never sent twice (guards
      against broker redelivery).
    * Transient failures are retried with exponential back-off; when retries
      are exhausted the log is marked ``failed`` with the error text.
    """
    try:
        log = InvoiceSendLog.objects.select_related("invoice__order__vendor__user").get(pk=log_id)
    except InvoiceSendLog.DoesNotExist:
        logger.error("send_invoice_email: log %s does not exist", log_id)
        return "missing"

    if log.status == InvoiceSendStatus.SENT:
        return "already-sent"
    if not log.recipient_email:
        log.status = InvoiceSendStatus.FAILED
        log.error_message = log.error_message or "No recipient e-mail address"
        log.save(update_fields=["status", "error_message"])
        return "no-recipient"

    invoice = log.invoice
    order = invoice.order
    try:
        if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
            log.attempts += 1
            log.status = InvoiceSendStatus.FAILED
            log.error_message = (
                "Real email delivery is disabled because EMAIL_BACKEND is set to console.EmailBackend. "
                "Emails are only printed to the server terminal. Please configure SMTP in backend/.env to deliver real emails to inboxes."
            )
            log.save(update_fields=["attempts", "status", "error_message"])
            logger.warning("Invoice %s: email not delivered to inbox because EMAIL_BACKEND is console.EmailBackend", invoice.invoice_number)
            return "failed"

        pdf_bytes = build_invoice_pdf(invoice)
        message = EmailMessage(
            subject=f"Invoice {invoice.invoice_number} for order {order.order_number}",
            body=(
                f"Hello {order.vendor.name},\n\n"
                f"Invoice {invoice.invoice_number} for order {order.order_number} is ready.\n"
                f"Total amount: INR {invoice.total_amount:,.2f}\n\n"
                "The invoice PDF is attached.\n\n"
                "Thank you,\nERP Console"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[log.recipient_email],
        )
        message.attach(f"{invoice.invoice_number}.pdf", pdf_bytes, "application/pdf")
        message.send(fail_silently=False)
    except Exception as exc:
        log.attempts += 1
        log.error_message = f"{exc.__class__.__name__}: {exc}"[:1000]
        retries = getattr(self.request, "retries", 0) if hasattr(self, "request") else 0
        is_config_err = isinstance(exc, (RuntimeError, ValueError)) or "console.EmailBackend" in str(exc)
        if not is_config_err and retries < self.max_retries:
            log.save(update_fields=["attempts", "error_message"])  # stays "pending" while retrying
            logger.warning("Invoice e-mail log %s failed (%s); retrying", log_id, exc)
            raise self.retry(exc=exc, countdown=RETRY_BACKOFF_SECONDS * (2 ** retries))
        log.status = InvoiceSendStatus.FAILED
        log.save(update_fields=["attempts", "error_message", "status"])
        logger.error("Invoice e-mail log %s permanently failed: %s", log_id, exc)
        return "failed"

    log.attempts += 1
    log.status = InvoiceSendStatus.SENT
    log.sent_at = timezone.now()
    log.error_message = ""
    log.save(update_fields=["attempts", "status", "sent_at", "error_message"])
    return "sent"
