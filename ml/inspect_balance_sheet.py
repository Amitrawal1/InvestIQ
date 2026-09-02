import xml.etree.ElementTree as ET

FILE = "reliance_financial_result.xml"
XBRLI = "http://www.xbrl.org/2003/instance"

tree = ET.parse(FILE)
root = tree.getroot()

contexts = {}

for context in root.findall(f"{{{XBRLI}}}context"):
    context_id = context.get("id")

    identifier = context.find(f".//{{{XBRLI}}}identifier")
    instant = context.find(f".//{{{XBRLI}}}instant")
    scenario = context.find(f".//{{{XBRLI}}}scenario")

    contexts[context_id] = {
        "symbol": identifier.text if identifier is not None else None,
        "instant": instant.text if instant is not None else None,
        "scenario": scenario is not None
    }


print("\n========== ALL INSTANT FACTS ==========\n")

seen = set()

for element in root.iter():

    tag = element.tag.split("}")[-1]
    context_id = element.get("contextRef")

    if not context_id:
        continue

    context = contexts.get(context_id)

    if not context:
        continue

    # Only instant contexts
    if not context["instant"]:
        continue

    value = element.text

    if value is None:
        continue

    key = (tag, context_id, value)

    if key in seen:
        continue

    seen.add(key)

    print(f"Concept  : {tag}")
    print(f"Context  : {context_id}")
    print(f"Scenario : {context['scenario']}")
    print(f"Value    : {value}")
    print(f"Unit     : {element.get('unitRef')}")
    print(f"Date     : {context['instant']}")
    print("-" * 60)