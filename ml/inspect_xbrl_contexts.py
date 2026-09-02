import xml.etree.ElementTree as ET
from datetime import date

FILE = "reliance_financial_result.xml"

XBRLI = "http://www.xbrl.org/2003/instance"

tree = ET.parse(FILE)
root = tree.getroot()


def get_text(element, path):
    child = element.find(path)

    if child is not None:
        return child.text

    return None


def days_between(start_date, end_date):
    if not start_date or not end_date:
        return None

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    return (end - start).days + 1


print("========== XBRL CONTEXT ANALYSIS ==========\n")


# --------------------------------------------------
# Read contexts
# --------------------------------------------------

contexts = {}

for context in root.findall(f"{{{XBRLI}}}context"):

    context_id = context.get("id")

    identifier = get_text(
        context,
        f".//{{{XBRLI}}}identifier"
    )

    start_date = get_text(
        context,
        f".//{{{XBRLI}}}startDate"
    )

    end_date = get_text(
        context,
        f".//{{{XBRLI}}}endDate"
    )

    instant = get_text(
        context,
        f".//{{{XBRLI}}}instant"
    )

    scenario = context.find(
        f".//{{{XBRLI}}}scenario"
    )

    has_scenario = scenario is not None

    duration = days_between(start_date, end_date)

    contexts[context_id] = {
        "identifier": identifier,
        "start_date": start_date,
        "end_date": end_date,
        "instant": instant,
        "duration_days": duration,
        "has_scenario": has_scenario
    }


# --------------------------------------------------
# Print contexts
# --------------------------------------------------

for context_id, context in contexts.items():

    print(f"Context ID     : {context_id}")
    print(f"Symbol         : {context['identifier']}")
    print(f"Start Date     : {context['start_date']}")
    print(f"End Date       : {context['end_date']}")
    print(f"Instant        : {context['instant']}")
    print(f"Duration Days  : {context['duration_days']}")
    print(f"Has Scenario   : {context['has_scenario']}")

    print("-" * 60)


print("\n========== CONTEXT SUMMARY ==========")

duration_counts = {}

for context in contexts.values():
    duration = context["duration_days"]

    if duration is None:
        key = "Instant"
    else:
        key = duration

    duration_counts[key] = duration_counts.get(key, 0) + 1

print("\n========== CONTEXT SUMMARY ==========")

for duration, count in sorted(
    duration_counts.items(),
    key=lambda x: (x[0] == "Instant", x[0])
):
    print(f"Duration: {duration} → Contexts: {count}")