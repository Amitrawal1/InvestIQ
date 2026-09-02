import xml.etree.ElementTree as ET

FILE = "reliance_financial_result.xml"

tree = ET.parse(FILE)
root = tree.getroot()

# Namespace
XBRLI = "http://www.xbrl.org/2003/instance"

# --------------------------------------------------
# 1. Read all contexts
# --------------------------------------------------

contexts = {}

for context in root.findall(f"{{{XBRLI}}}context"):
    context_id = context.get("id")

    identifier = context.find(f".//{{{XBRLI}}}identifier")
    start_date = context.find(f".//{{{XBRLI}}}startDate")
    end_date = context.find(f".//{{{XBRLI}}}endDate")

    contexts[context_id] = {
        "identifier": identifier.text if identifier is not None else None,
        "start_date": start_date.text if start_date is not None else None,
        "end_date": end_date.text if end_date is not None else None,
        "has_scenario": context.find(f".//{{{XBRLI}}}scenario") is not None
    }


# --------------------------------------------------
# 2. Financial concepts we care about
# --------------------------------------------------

TARGETS = {
    "RevenueFromOperations",
    "ProfitBeforeTax",
    "ProfitLossForPeriod",
    "Expenses",
    "OtherIncome",
    "FinanceCosts",
    "DepreciationDepletionAndAmortisationExpense",
    "EmployeeBenefitExpense",
    "CostOfMaterialsConsumed",
    "BasicEarningsLossPerShareFromContinuingOperations",
    "DilutedEarningsLossPerShareFromContinuingOperations",
    "DebtEquityRatio",
    "DebtServiceCoverageRatio"
}


# --------------------------------------------------
# 3. Extract values
# --------------------------------------------------

print("========== FINANCIAL VALUES ==========\n")

for element in root.iter():

    tag = element.tag.split("}")[-1]

    if tag not in TARGETS:
        continue

    value = element.text
    context_id = element.get("contextRef")
    unit = element.get("unitRef")

    context = contexts.get(context_id, {})

    print(f"Concept      : {tag}")
    print(f"Value        : {value}")
    print(f"Unit         : {unit}")
    print(f"Context      : {context_id}")
    print(f"Identifier   : {context.get('identifier')}")
    print(f"Start Date   : {context.get('start_date')}")
    print(f"End Date     : {context.get('end_date')}")
    print(f"Has Scenario : {context.get('has_scenario')}")
    print("-" * 60)