#!/usr/bin/env python3
"""jsonschema - Validate JSON and generate schemas.

One file. Zero deps. Types JSON.

Usage:
  jsonschema.py generate data.json           → infer schema from data
  jsonschema.py validate data.json schema.json → validate against schema
  jsonschema.py diff a.json b.json            → compare JSON structures
  echo '{"a":1}' | jsonschema.py generate    → pipe input
"""

import argparse
import json
import sys


def infer_type(value) -> dict:
    """Infer JSON Schema type from a value."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        schema = {"type": "string"}
        if len(value) > 0:
            schema["minLength"] = 1
        # Detect formats
        import re
        if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
            schema["format"] = "date"
        elif re.match(r'^\d{4}-\d{2}-\d{2}T', value):
            schema["format"] = "date-time"
        elif re.match(r'^[^@]+@[^@]+\.[^@]+$', value):
            schema["format"] = "email"
        elif re.match(r'^https?://', value):
            schema["format"] = "uri"
        elif re.match(r'^\d{1,3}(\.\d{1,3}){3}$', value):
            schema["format"] = "ipv4"
        return schema
    if isinstance(value, list):
        schema = {"type": "array"}
        if value:
            # Infer items schema from all elements
            item_schemas = [infer_type(item) for item in value]
            if all(s == item_schemas[0] for s in item_schemas):
                schema["items"] = item_schemas[0]
            else:
                # Union type
                types = list({json.dumps(s, sort_keys=True) for s in item_schemas})
                if len(types) == 1:
                    schema["items"] = json.loads(types[0])
                else:
                    schema["items"] = {"oneOf": [json.loads(t) for t in types]}
            schema["minItems"] = 0
        return schema
    if isinstance(value, dict):
        schema = {
            "type": "object",
            "properties": {},
            "required": list(value.keys()),
        }
        for k, v in value.items():
            schema["properties"][k] = infer_type(v)
        return schema
    return {}


def generate_schema(data) -> dict:
    """Generate a JSON Schema from sample data."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
    }
    schema.update(infer_type(data))
    return schema


def validate(data, schema, path="$") -> list[str]:
    """Validate data against a JSON Schema. Returns list of errors."""
    errors = []
    schema_type = schema.get("type")

    # Type check
    type_map = {
        "string": str, "integer": int, "number": (int, float),
        "boolean": bool, "array": list, "object": dict, "null": type(None),
    }

    if schema_type and schema_type in type_map:
        expected = type_map[schema_type]
        if not isinstance(data, expected):
            # Special: integer is also number
            if schema_type == "number" and isinstance(data, (int, float)):
                pass
            elif schema_type == "integer" and isinstance(data, bool):
                errors.append(f"{path}: expected integer, got boolean")
            else:
                errors.append(f"{path}: expected {schema_type}, got {type(data).__name__}")
                return errors

    # String constraints
    if schema_type == "string" and isinstance(data, str):
        if "minLength" in schema and len(data) < schema["minLength"]:
            errors.append(f"{path}: string too short (min {schema['minLength']})")
        if "maxLength" in schema and len(data) > schema["maxLength"]:
            errors.append(f"{path}: string too long (max {schema['maxLength']})")
        if "pattern" in schema:
            import re
            if not re.search(schema["pattern"], data):
                errors.append(f"{path}: doesn't match pattern '{schema['pattern']}'")
        if "enum" in schema and data not in schema["enum"]:
            errors.append(f"{path}: must be one of {schema['enum']}")

    # Number constraints
    if schema_type in ("integer", "number") and isinstance(data, (int, float)):
        if "minimum" in schema and data < schema["minimum"]:
            errors.append(f"{path}: {data} < minimum {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            errors.append(f"{path}: {data} > maximum {schema['maximum']}")

    # Array
    if schema_type == "array" and isinstance(data, list):
        if "minItems" in schema and len(data) < schema["minItems"]:
            errors.append(f"{path}: too few items (min {schema['minItems']})")
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            errors.append(f"{path}: too many items (max {schema['maxItems']})")
        if "items" in schema:
            for i, item in enumerate(data):
                errors.extend(validate(item, schema["items"], f"{path}[{i}]"))

    # Object
    if schema_type == "object" and isinstance(data, dict):
        props = schema.get("properties", {})
        required = schema.get("required", [])
        for req in required:
            if req not in data:
                errors.append(f"{path}: missing required property '{req}'")
        for key, val in data.items():
            if key in props:
                errors.extend(validate(val, props[key], f"{path}.{key}"))

    return errors


def json_diff(a, b, path="$") -> list[str]:
    """Compare two JSON structures."""
    diffs = []
    if type(a) != type(b):
        diffs.append(f"{path}: type {type(a).__name__} vs {type(b).__name__}")
        return diffs
    if isinstance(a, dict):
        for k in set(list(a.keys()) + list(b.keys())):
            if k not in a:
                diffs.append(f"{path}.{k}: only in second")
            elif k not in b:
                diffs.append(f"{path}.{k}: only in first")
            else:
                diffs.extend(json_diff(a[k], b[k], f"{path}.{k}"))
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append(f"{path}: length {len(a)} vs {len(b)}")
        for i in range(min(len(a), len(b))):
            diffs.extend(json_diff(a[i], b[i], f"{path}[{i}]"))
    elif a != b:
        diffs.append(f"{path}: {json.dumps(a)} vs {json.dumps(b)}")
    return diffs


def main():
    parser = argparse.ArgumentParser(description="JSON Schema tools")
    sub = parser.add_subparsers(dest="command")

    g = sub.add_parser("generate", help="Generate schema from data")
    g.add_argument("file", nargs="?")

    v = sub.add_parser("validate", help="Validate data against schema")
    v.add_argument("data")
    v.add_argument("schema")

    d = sub.add_parser("diff", help="Compare JSON structures")
    d.add_argument("file1")
    d.add_argument("file2")

    args = parser.parse_args()

    if args.command == "generate":
        if args.file:
            with open(args.file) as f:
                data = json.load(f)
        elif not sys.stdin.isatty():
            data = json.load(sys.stdin)
        else:
            print("Error: no input", file=sys.stderr)
            return 1
        schema = generate_schema(data)
        print(json.dumps(schema, indent=2))

    elif args.command == "validate":
        with open(args.data) as f:
            data = json.load(f)
        with open(args.schema) as f:
            schema = json.load(f)
        errors = validate(data, schema)
        if errors:
            for e in errors:
                print(f"  ✗ {e}")
            return 1
        print("  ✓ Valid")

    elif args.command == "diff":
        with open(args.file1) as f:
            a = json.load(f)
        with open(args.file2) as f:
            b = json.load(f)
        diffs = json_diff(a, b)
        if diffs:
            for d in diffs:
                print(f"  ~ {d}")
        else:
            print("  ✓ Identical")

    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
