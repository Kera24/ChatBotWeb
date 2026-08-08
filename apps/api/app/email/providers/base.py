from abc import ABC, abstractmethod

from app.email.contracts import EmailMessage, EmailSendResult


class TransactionalEmailProvider(ABC):
    provider_key: str

    @abstractmethod
    def send(self, message: EmailMessage) -> EmailSendResult:
        pass
