import xml.etree.ElementTree as ET

FILE = "reliance_financial_result.xml"

tree = ET.parse(FILE)
root = tree.getroot()

print("========== XBRL TAGS ==========")

tags = set()

for element in root.iter():
    tag = element.tag.split("}")[-1]

    if tag not in [
        "xbrl",
        "context",
        "entity",
        "identifier",
        "period",
        "startDate",
        "endDate",
        "scenario",
        "explicitMember",
        "schemaRef"
    ]:
        tags.add(tag)

for tag in sorted(tags):
    print(tag)

print("\nTotal unique tags:", len(tags))