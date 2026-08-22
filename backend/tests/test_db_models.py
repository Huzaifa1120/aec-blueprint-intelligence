from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    Assembly,
    BoqItem,
    Component,
    Drawing,
    DrawingRevision,
    Estimate,
    Material,
    Measurement,
    Price,
    Project,
    Route,
    Sheet,
    Space,
)


def test_core_chain_roundtrip() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        project = Project(name="Jeddah VIP Clinic")
        drawing = Drawing(discipline="Electrical", sheet_number="E-3902")
        rev = DrawingRevision(revision="A", source_path_type="pdf")
        sheet = Sheet(name="AC Wire", scale="1:100")
        component = Component(
            component_type="card_reader", source_layer="access control", x=1.0, y=2.0
        )
        route = Route(route_type="cable_trunk", length_m=42.5)
        space = Space(name="Room 101", area_m2=25.0)
        measurement = Measurement(
            source_sheet="E-3902",
            source_region="{0,0,10,10}",
            measurement_type="count",
            raw_value=1.0,
        )
        estimate = Estimate()
        boq = BoqItem(quantity=1.0, unit_cost=10.0, total_cost=10.0)

        project.drawings.append(drawing)
        drawing.revisions.append(rev)
        drawing.sheets.append(sheet)
        sheet.components.append(component)
        sheet.routes.append(route)
        sheet.spaces.append(space)
        component.measurements.append(measurement)
        estimate.boq_items.append(boq)
        measurement.boq_items.append(boq)
        project.estimates.append(estimate)

        material = Material(name="Cable", unit="m", category="Electrical")
        material.prices.append(Price(unit_price=5.50))
        assembly = Assembly(name="access_control_door", rule_version="1.0")
        assembly.materials.append(material)

        session.add_all([project, material, assembly])
        session.commit()

        assert project.id is not None
        assert drawing.project_id == project.id
        assert boq.measurement_id == measurement.id
        assert boq.estimate_id == estimate.id
        assert material.prices[0].unit_price == 5.50
        assert assembly.materials[0].name == "Cable"


def test_geometry_models_have_source_quality() -> None:
    from app.db.models.geometry import Component, Route, Space

    for model in (Component, Route, Space):
        assert hasattr(model, "source_quality"), f"{model.__name__} missing source_quality"
        assert model.__table__.c.source_quality.default.arg == "layered_vector"
