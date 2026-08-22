import sys
sys.path.insert(0, '.')
from app.assembly.rules import apply_assembly, load_assembly_rule

# Check what apply_assembly returns for each type
for name in ["cable_tray", "conduit", "access_control_door", "lighting_outlet"]:
    rule = load_assembly_rule(name)
    applied = apply_assembly(name)
    print(f"\n=== {name} ===")
    print(f"BOM: {rule['bom']}")
    print(f"Applied materials: {applied.get('materials', [])}")
    for mat in applied.get("materials", []):
        print(f"  - {mat['material_name']}: quantity={mat['quantity']}")