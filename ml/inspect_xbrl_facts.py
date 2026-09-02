import xml.etree.ElementTree as ET
from collections import defaultdict

FILE = "reliance_financial_result.xml"
XBRLI = "http://www.xbrl.org/2003/instance"

tree = ET.parse(FILE)
root = tree.getroot()

# Important financial concepts we want to inspect
TARGETS = [
    "RevenueFromOperations",
    "OtherIncome",
    "Expenses",
    "ProfitBeforeTax",
    "ProfitLossForPeriod",
    "BasicEarningsLossPerShareFromContinuingOperations",
    "DilutedEarningsLossPerShareFromContinuingOperations",
    "DebtEquityRatio",
    "TotalAssets",
    "Equity",
    "Liabilities",
]

# Build context information
contexts = {}

for context in root.findall(f"{{{XBRLI}}}context"):
    context_id = context.get("id")

    identifier = context.find(
        f".//{{{XBRLI}}}identifier"
    )

    start = context.find(
        f".//{{{XBRLI}}}startDate"
    )

    end = context.find(
        f".//{{{XBRLI}}}endDate"
    )

    instant = context.find(
        f".//{{{XBRLI}}}instant"
    )

    contexts[context_id] = {
        "symbol": identifier.text if identifier is not None else None,
        "start": start.text if start is not None else None,
        "end": end.text if end is not None else None,
        "instant": instant.text if instant is not None else None,
    }


print("\n========== TARGET FINANCIAL FACTS ==========\n")


for element in root.iter():

    # Remove namespace from tag
    tag = element.tag.split("}")[-1]

    if tag not in TARGETS:
        continue

    context_id = element.get("contextRef")

    context = contexts.get(context_id, {})

    print(f"Concept       : {tag}")
    print(f"Context       : {context_id}")
    print(f"Symbol        : {context.get('symbol')}")
    print(f"Start         : {context.get('start')}")
    print(f"End           : {context.get('end')}")
    print(f"Instant       : {context.get('instant')}")
    print(f"Value         : {element.text}")
    print(f"Unit          : {element.get('unitRef')}")
    print("-" * 60)