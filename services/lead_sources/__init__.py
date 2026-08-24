"""Lead discovery sources package for multi-source buyer search."""

from services.lead_sources.base_source import BaseLeadSource
from services.lead_sources.serper_source import SerperLeadSource
from services.lead_sources.tradekey_source import TradeKeyLeadSource
from services.lead_sources.europages_source import EuropagesLeadSource
from services.lead_sources.kompass_source import KompassLeadSource
from services.lead_sources.indiamart_source import IndiaMARTLeadSource
from services.lead_sources.tradeindia_source import TradeIndiaLeadSource
from services.lead_sources.alibaba_source import AlibabaLeadSource
from services.lead_sources.globalsources_source import GlobalSourcesLeadSource

ALL_LEAD_SOURCES = {
    "serper": SerperLeadSource,
    "tradekey": TradeKeyLeadSource,
    "europages": EuropagesLeadSource,
    "kompass": KompassLeadSource,
    "indiamart": IndiaMARTLeadSource,
    "tradeindia": TradeIndiaLeadSource,
    "alibaba": AlibabaLeadSource,
    "globalsources": GlobalSourcesLeadSource,
}

__all__ = [
    "BaseLeadSource",
    "SerperLeadSource",
    "TradeKeyLeadSource",
    "EuropagesLeadSource",
    "KompassLeadSource",
    "IndiaMARTLeadSource",
    "TradeIndiaLeadSource",
    "AlibabaLeadSource",
    "GlobalSourcesLeadSource",
    "ALL_LEAD_SOURCES",
]
