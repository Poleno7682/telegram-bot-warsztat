"""Presentation helpers shared between handlers and services.

Anything here must stay free of dependencies on app.services / app.repositories
so it can be safely imported from the service layer (see NotificationService)
without inverting the handlers -> services -> repositories dependency direction.
"""
