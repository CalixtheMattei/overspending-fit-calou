from __future__ import annotations

from .counterparty import Counterparty, CounterpartyKind

# Backward-compatible aliases while payee endpoints continue to exist.
Payee = Counterparty
PayeeKind = CounterpartyKind
