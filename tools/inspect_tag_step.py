#!/usr/bin/env python3
"""Report named component envelopes from the official nRF54L15 Tag STEP file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_cad_modules() -> dict[str, Any]:
    try:
        from cadquery import Shape
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPCAFControl import STEPCAFControl_Reader
        from OCP.TCollection import TCollection_ExtendedString
        from OCP.TDataStd import TDataStd_Name
        from OCP.TDF import TDF_Label, TDF_LabelSequence
        from OCP.TDocStd import TDocStd_Document
        from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool
    except ImportError as exc:
        raise SystemExit(
            "cadquery is required; install it in an external virtual environment "
            "with: python -m pip install cadquery"
        ) from exc

    return locals()


def inspect_step(path: Path) -> dict[str, Any]:
    modules = _load_cad_modules()
    Shape = modules["Shape"]
    IFSelect_RetDone = modules["IFSelect_RetDone"]
    STEPCAFControl_Reader = modules["STEPCAFControl_Reader"]
    TCollection_ExtendedString = modules["TCollection_ExtendedString"]
    TDataStd_Name = modules["TDataStd_Name"]
    TDF_Label = modules["TDF_Label"]
    TDF_LabelSequence = modules["TDF_LabelSequence"]
    TDocStd_Document = modules["TDocStd_Document"]
    XCAFDoc_DocumentTool = modules["XCAFDoc_DocumentTool"]
    XCAFDoc_ShapeTool = modules["XCAFDoc_ShapeTool"]

    document = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    if reader.ReadFile(str(path)) != IFSelect_RetDone or not reader.Transfer(document):
        raise SystemExit(f"could not load STEP assembly: {path}")

    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    roots = TDF_LabelSequence()
    shape_tool.GetFreeShapes(roots)
    if roots.Length() != 1:
        raise SystemExit(f"expected one assembly root, found {roots.Length()}")

    def name(label: Any) -> str:
        attribute = TDataStd_Name()
        if label.FindAttribute(TDataStd_Name.GetID_s(), attribute):
            return attribute.Get().ToExtString()
        return ""

    def bounds(label: Any) -> dict[str, float]:
        box = Shape.cast(shape_tool.GetShape_s(label)).BoundingBox()
        return {
            "xmin": box.xmin,
            "xmax": box.xmax,
            "ymin": box.ymin,
            "ymax": box.ymax,
            "zmin": box.zmin,
            "zmax": box.zmax,
            "xlen": box.xlen,
            "ylen": box.ylen,
            "zlen": box.zlen,
        }

    root = roots.Value(1)
    component_labels = TDF_LabelSequence()
    shape_tool.GetComponents_s(root, component_labels, False)
    components = []
    for index in range(1, component_labels.Length() + 1):
        instance = component_labels.Value(index)
        referred = TDF_Label()
        shape_tool.GetReferredShape_s(instance, referred)
        components.append(
            {
                "index": index,
                "instance": name(instance),
                "reference": name(referred),
                "bounds_mm": bounds(instance),
            }
        )

    return {
        "source": str(path.resolve()),
        "assembly": name(root),
        "bounds_mm": bounds(root),
        "components": components,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", type=Path, help="official nRF54L15 Tag STEP file")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()
    if not args.step.is_file():
        parser.error(f"STEP file not found: {args.step}")

    result = inspect_step(args.step)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    overall = result["bounds_mm"]
    print(
        f"{result['assembly']}: {overall['xlen']:.3f} x "
        f"{overall['ylen']:.3f} x {overall['zlen']:.3f} mm"
    )
    print("index reference xmin xmax ymin ymax zmin zmax (mm)")
    for component in result["components"]:
        box = component["bounds_mm"]
        print(
            f"{component['index']:>2} {component['reference']:<12} "
            f"{box['xmin']:>7.3f} {box['xmax']:>7.3f} "
            f"{box['ymin']:>7.3f} {box['ymax']:>7.3f} "
            f"{box['zmin']:>7.3f} {box['zmax']:>7.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
