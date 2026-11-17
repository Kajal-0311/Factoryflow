from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrator'
        SALESMAN = 'SALESMAN', 'Sales Representative'
        PRODUCTION_SUPERVISOR = 'PRODUCTION_SUPERVISOR', 'Production Supervisor'
        OWNER_AUDITOR = 'OWNER_AUDITOR', 'Owner / Accountant / Auditor'

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.ADMIN,
        help_text='System role governing access permissions across modules'
    )
    phone = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['username']

    def __str__(self):
        full = self.get_full_name()
        return f"{full} ({self.get_role_display()})" if full else f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin_role(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_salesman_role(self):
        return self.role == self.Role.SALESMAN

    @property
    def is_production_supervisor_role(self):
        return self.role == self.Role.PRODUCTION_SUPERVISOR

    @property
    def is_production_role(self):
        return self.is_production_supervisor_role

    @property
    def is_auditor_owner_role(self):
        return self.role == self.Role.OWNER_AUDITOR

    @property
    def is_auditor_role(self):
        return self.is_auditor_owner_role
