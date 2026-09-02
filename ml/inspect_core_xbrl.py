import xml.etree.ElementTree as ET

FILE = "reliance_financial_result.xml"
XBRLI = "http://www.xbrl.org/2003/instance"

tree = ET.parse(FILE)
root = tree.getroot()


# --------------------------------------------------
# Build context information
# --------------------------------------------------

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

    scenario = context.find(
        f".//{{{XBRLI}}}scenario"
    )

    contexts[context_id] = {
        "symbol": identifier.text if identifier is not None else None,
        "start": start.text if start is not None else None,
        "end": end.text if end is not None else None,
        "instant": instant.text if instant is not None else None,
        "scenario": scenario is not None
    }


print("\n========== CORE XBRL FACTS ==========\n")


for element in root.iter():

    tag = element.tag.split("}")[-1]

    context_id = element.get("contextRef")

    if not context_id:
        continue

    context = contexts.get(context_id)

    if not context:
        continue

    # Ignore segment/dimensional contexts
    if context["scenario"]:
        continue

    value = element.text

    if value is None:
        continue

    print(f"Concept  : {tag}")
    print(f"Context  : {context_id}")
    print(f"Value    : {value}")
    print(f"Unit     : {element.get('unitRef')}")

    if context["instant"]:
        print(f"Period   : INSTANT {context['instant']}")
    else:
        print(
            f"Period   : "
            f"{context['start']} → {context['end']}"
        )

    print("-" * 60)