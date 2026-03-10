# jsonschema

Validate JSON and generate schemas from data.

One file. Zero deps. Types JSON.

## Usage

```bash
# Generate schema from sample data
echo '{"name":"Alice","age":30}' | python3 jsonschema.py generate
python3 jsonschema.py generate data.json

# Validate data against schema
python3 jsonschema.py validate data.json schema.json

# Compare JSON structures
python3 jsonschema.py diff a.json b.json
```

Auto-detects formats: date, date-time, email, URI, IPv4.

## Requirements

Python 3.8+. No dependencies.

## License

MIT
