# Implementation Plan  
## Task 6: Assembly Rules  
### 6.1 YAML Rule Set Structure  
Code block:  
  # data/assemblies/access_control_door.yaml  
  name: access_control_door  
  rule_version: '1.0.0'  
  components:  
    card_reader: count: 1  
    magnetic_lock: count: 1  
    push_button: count: 1  
    door_controller: count: 0.5  
  labor:  
    installation_hours: 2.5  
  waste_factor: 0.10  
`  
The Assembly model in backend/app/db/models/catalog.py has rule_version and formula_or_bom (JSON) fields.  
Approach: YAML files in data/assemblies/ loaded at startup, parsed into Assembly DB model.  
## Task 7: Cost Engine  
- Material cost = quantity * unit_price  
- Labor hours = measured_quantity / productivity_rate  
- Labor cost = labor_hours * hourly_rate  
- Total = material_cost + labor_cost + equipment_cost + waste + contingency  
- Prices and productivity rates from catalog DB or YAML, never hardcoded  
