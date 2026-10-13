"""Management command to test SMTP email delivery to a real recipient."""
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test SMTP email delivery to a real recipient inbox."

    def add_arguments(self, parser):
        parser.add_argument("recipient", type=str, help="Recipient email address to test delivery to")

    def handle(self, *args, **options):
        recipient = options["recipient"].strip()
        self.stdout.write(self.style.NOTICE(f"\n--- ERP Console Email Configuration Diagnostics ---"))
        self.stdout.write(f"EMAIL_BACKEND:       {settings.EMAIL_BACKEND}")
        self.stdout.write(f"EMAIL_HOST:          {settings.EMAIL_HOST}")
        self.stdout.write(f"EMAIL_PORT:          {settings.EMAIL_PORT}")
        self.stdout.write(f"EMAIL_USE_TLS:       {getattr(settings, 'EMAIL_USE_TLS', False)}")
        self.stdout.write(f"EMAIL_USE_SSL:       {getattr(settings, 'EMAIL_USE_SSL', False)}")
        self.stdout.write(f"EMAIL_HOST_USER:     {settings.EMAIL_HOST_USER}")
        self.stdout.write(f"EMAIL_HOST_PASSWORD: {'*' * len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else '(not set)'}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL:  {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"Target Recipient:    {recipient}\n")

        if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
            self.stdout.write(self.style.WARNING(
                "WARNING: EMAIL_BACKEND is set to console.EmailBackend.\n"
                "Emails are printed to the terminal console only, NOT delivered to real inboxes.\n"
                "To deliver real emails, set in backend/.env:\n"
                "  EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend\n"
                "  EMAIL_HOST=smtp.gmail.com (or your SMTP host)\n"
                "  EMAIL_PORT=587\n"
                "  EMAIL_USE_TLS=True\n"
                "  EMAIL_HOST_USER=your-email@gmail.com\n"
                "  EMAIL_HOST_PASSWORD=your-app-password\n"
                "  DEFAULT_FROM_EMAIL=your-email@gmail.com\n"
            ))

        self.stdout.write(f"Attempting to connect and send test message to {recipient}...")

        try:
            connection = get_connection()
            connection.open()
            self.stdout.write(self.style.SUCCESS("[OK] Connection to email host opened successfully."))

            message = EmailMessage(
                subject="ERP Console - SMTP Delivery Verification",
                body=(
                    f"Hello,\n\n"
                    f"This is a test email from the ERP Console.\n"
                    f"If you received this message in your inbox, SMTP email delivery is configured and working perfectly!\n\n"
                    f"Configuration used:\n"
                    f"  Host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}\n"
                    f"  From: {settings.DEFAULT_FROM_EMAIL}\n"
                    f"  Backend: {settings.EMAIL_BACKEND}\n\n"
                    f"Regards,\nERP Console"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
                connection=connection,
            )
            count = message.send(fail_silently=False)
            connection.close()

            if count > 0:
                if settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
                    self.stdout.write(self.style.SUCCESS(
                        f"\n[OK] SUCCESS: Test email was accepted by the SMTP server ({settings.EMAIL_HOST})!\n"
                        f"Please check the inbox of '{recipient}' (and your Spam folder if not found in primary).\n"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"\n[OK] Message processed by {settings.EMAIL_BACKEND}.\n"
                        f"Note: Since console backend is active, this was written to terminal and not sent to internet inboxes.\n"
                    ))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"\n[FAILED] DELIVERY FAILED: {exc.__class__.__name__}: {exc}\n"))
            if "Authentication" in str(exc) or "535" in str(exc):
                self.stdout.write(self.style.NOTICE(
                    "Hint: Authentication failed. For Gmail, make sure you generated a 16-character App Password "
                    "at https://myaccount.google.com/apppasswords and that 2-Step Verification is enabled."
                ))
            elif "ConnectionRefused" in str(exc) or "timed out" in str(exc).lower():
                self.stdout.write(self.style.NOTICE(
                    f"Hint: Could not connect to {settings.EMAIL_HOST}:{settings.EMAIL_PORT}. "
                    "Check port (587 for TLS, 465 for SSL) and your internet connection."
                ))
