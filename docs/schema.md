# Database Schema Reference

Auto-generated from YAML schemas in backend/data/schemas/.

## assemblies

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| name | varchar(200) | no | - | - |
| rule_version | varchar(50) | no | - | - |
| formula_or_bom | json | yes | - | - |

## assembly_materials

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| assembly_id | uuid | no | - | assemblies.id |
| material_id | uuid | no | - | materials.id |
| quantity | float | no | 1.0 | - |

## boq_items

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| measurement_id | uuid | no | - | measurements.id |
| estimate_id | uuid | no | - | estimates.id |
| quantity | float | no | - | - |
| unit_cost | float | no | - | - |
| total_cost | float | no | - | - |
| derivation_json | varchar(2000) | yes | None | - |
| size_source | varchar(20) | yes | None | - |
| source_bbox_json | text | yes | None | - |
| confidence_status | varchar(20) | yes | None | - |
| confidence_score | float | yes | None | - |

## components

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| sheet_id | uuid | no | - | sheets.id |
| component_type | varchar(100) | no | - | - |
| source_layer | varchar(100) | yes | - | - |
| x | float | no | - | - |
| y | float | no | - | - |
| confidence_status | varchar(20) | no | MEASURED | - |
| confidence_score | float | no | 1.0 | - |
| layer_id | uuid | yes | - | layers.id |
| source_quality | varchar(20) | no | layered_vector | - |

## drawing_quality_assessments

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| drawing_id | uuid | yes | - | drawings.id |
| file_name | varchar(500) | no | - | - |
| verdict | varchar(20) | no | - | - |
| metrics_json | varchar(2000) | yes | - | - |
| created_at | datetime | no | func.now | - |

## drawing_revisions

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| drawing_id | uuid | no | - | drawings.id |
| revision | varchar(20) | no | - | - |
| issued_date | date | yes | - | - |
| source_path_type | varchar(50) | yes | - | - |

## drawings

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| project_id | uuid | no | - | projects.id |
| discipline | varchar(100) | yes | - | - |
| sheet_number | varchar(50) | yes | - | - |

## estimates

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| project_id | uuid | no | - | projects.id |
| total_material_cost | float | no | 0.0 | - |
| total_labor_cost | float | no | 0.0 | - |
| total_cost | float | no | 0.0 | - |
| data_quality_json | text | yes | None | - |
| scale_status | varchar(20) | yes | - | - |
| source_quality | varchar(20) | no | layered_vector | - |
| source_pdf_path | varchar(500) | yes | - | - |

## labor_rates

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| name | varchar(200) | no | - | - |
| productivity_rate | float | yes | None | - |
| hourly_rate | float | yes | None | - |
| category | varchar(100) | yes | None | - |
| effective_from | date | yes | None | - |
| effective_to | date | yes | None | - |

## layers

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| sheet_id | uuid | no | - | sheets.id |
| ocg_name | varchar(100) | no | - | - |
| classified_discipline | varchar(50) | no | - | - |
| human_override_discipline | varchar(50) | yes | - | - |

## materials

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| name | varchar(200) | no | - | - |
| unit | varchar(20) | no | - | - |
| category | varchar(100) | yes | - | - |

## measurements

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| component_id | uuid | yes | - | components.id |
| route_id | uuid | yes | - | routes.id |
| space_id | uuid | yes | - | spaces.id |
| source_sheet | varchar(200) | no | - | - |
| source_region | varchar(500) | no | - | - |
| measurement_type | varchar(50) | no | - | - |
| raw_value | float | no | - | - |
| final_value | float | yes | - | - |
| confidence_status | varchar(20) | no | MEASURED | - |
| calculation_method | varchar(100) | yes | - | - |
| rule_version | varchar(50) | yes | - | - |

## prices

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| material_id | uuid | no | - | materials.id |
| unit_price | numeric(12,2) | no | - | - |
| currency | varchar(3) | no | USD | - |
| effective_from | date | yes | - | - |
| effective_to | date | yes | - | - |

## projects

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| name | varchar(200) | no | - | - |
| owner | varchar(200) | yes | - | - |
| consultant | varchar(200) | yes | - | - |
| currency | varchar(3) | no | USD | - |

## reexport_requests

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| drawing_id | uuid | yes | - | drawings.id |
| message | varchar(1000) | no | - | - |
| requested_at | datetime | no | func.now | - |

## review_actions

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| session_id | uuid | no | - | review_sessions.id |
| item_id | varchar(100) | no | - | - |
| action | varchar(20) | no | - | - |
| confidence_tier | varchar(20) | no | - | - |
| boq_item_id | uuid | yes | - | boq_items.id |
| reason | text | yes | - | - |
| corrected_value | float | yes | - | - |
| created_at | datetime | no | func.now | - |

## review_sessions

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| project_id | uuid | yes | - | projects.id |
| sheet_label | varchar(200) | no | - | - |
| started_at | datetime | no | utcnow | - |
| ended_at | datetime | yes | - | - |

## routes

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| sheet_id | uuid | no | - | sheets.id |
| route_type | varchar(100) | no | - | - |
| length_m | float | yes | - | - |
| confidence_status | varchar(20) | no | MEASURED | - |
| confidence_score | float | no | 1.0 | - |
| layer_id | uuid | yes | - | layers.id |
| source_quality | varchar(20) | no | layered_vector | - |
| size_json | text | yes | None | - |

## schedule_blocks

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| sheet_id | uuid | no | - | sheets.id |
| block_type | varchar(30) | no | - | - |
| page_region_json | varchar(500) | no | - | - |
| entries_json | text | no | - | - |
| source_quality | varchar(20) | no | layered_vector | - |

## sheets

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| drawing_id | uuid | no | - | drawings.id |
| name | varchar(200) | yes | - | - |
| page_number | integer | yes | - | - |
| scale | varchar(20) | yes | - | - |
| source_quality | varchar(20) | no | layered_vector | - |

## spaces

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| sheet_id | uuid | no | - | sheets.id |
| name | varchar(200) | yes | - | - |
| area_m2 | float | yes | - | - |
| confidence_status | varchar(20) | no | MEASURED | - |
| confidence_score | float | no | 1.0 | - |
| layer_id | uuid | yes | - | layers.id |
| source_quality | varchar(20) | no | layered_vector | - |

## text_annotations

| Column | Type | Nullable | Default | FK |
|--------|------|----------|---------|-----|
| id | uuid | no | uuid4 | - |
| sheet_id | uuid | no | - | sheets.id |
| text | text | no | - | - |
| bbox_json | varchar(200) | no | - | - |
| ocg_layer | varchar(100) | yes | - | - |
| component_id | uuid | yes | - | components.id |
| route_id | uuid | yes | - | routes.id |
| space_id | uuid | yes | - | spaces.id |

