"""Shared tool-argument normalization for every generation transport."""

NULL_WORDS = {"null", "none", "nil"}


def resolve(schema, root):
    while isinstance(schema, dict) and "$ref" in schema:
        schema = root.get("$defs", {})[schema["$ref"].rsplit("/", 1)[-1]]
    return schema if isinstance(schema, dict) else {}


def nullable(schema, root):
    schema = resolve(schema, root)
    kind = schema.get("type")
    return (kind == "null" or (isinstance(kind, list) and "null" in kind)
            or any(nullable(branch, root) for branch in schema.get("anyOf", []) + schema.get("oneOf", [])))


def absent_values(value, schema, root):
    """Hosted models sometimes write absence as null or as the string "null".

    Nullable fields receive a real null; optional fields are omitted; required
    non-nullable fields are left for schema validation to report.
    """
    schema = resolve(schema, root)
    for branch in schema.get("anyOf", []) + schema.get("oneOf", []):
        branch = resolve(branch, root)
        if (isinstance(value, dict) and branch.get("type") == "object") or (isinstance(value, list) and branch.get("type") == "array"):
            schema = branch
            break
    if isinstance(value, str) and value.strip().lower() in NULL_WORDS | {""} and nullable(schema, root):
        return None
    if isinstance(value, list) and "items" in schema:
        return [absent_values(item, schema["items"], root) for item in value]
    if not isinstance(value, dict):
        return value
    properties, required, result = schema.get("properties", {}), set(schema.get("required", [])), {}
    for key, item in value.items():
        if key in properties:
            absent = item is None or (isinstance(item, str) and item.strip().lower() in NULL_WORDS)
            if absent and key not in required:
                continue
            item = absent_values(item, properties[key], root)
        result[key] = item
    return result


def normalize(arguments, schema):
    """Normalize one tool call's arguments against its JSON Schema."""
    return absent_values(arguments, schema, schema)
