"""JSON/CSV conversion and formatting for the json-csv-converter and
json-formatter tools."""

import time
from io import StringIO

from app.core.logging import get_tool_logger


class JsonService:
    """Convert JSON<->CSV and pretty-print or minify JSON."""

    def json_to_csv(self, json_text: str) -> str:
        tool_logger = get_tool_logger("json-csv-converter")
        started = time.monotonic()
        import csv
        import json

        try:
            data = json.loads(json_text)
        except Exception as err:
            raise ValueError(f"Invalid JSON string: {err}")

        output = StringIO()
        if isinstance(data, list):
            if not data:
                return ""
            if isinstance(data[0], dict):
                # Union of keys in first-seen order: objects with keys
                # the first row lacked used to fail with a 400.
                headers: list[str] = []
                seen: set[str] = set()
                for row in data:
                    if isinstance(row, dict):
                        for key in row:
                            if key not in seen:
                                seen.add(key)
                                headers.append(key)
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                for row in data:
                    if isinstance(row, dict):
                        writer.writerow(
                            {
                                key: (
                                    json.dumps(value, ensure_ascii=False)
                                    if isinstance(value, (dict, list))
                                    else value
                                )
                                for key, value in row.items()
                            }
                        )
            else:
                writer = csv.writer(output)
                writer.writerow(["value"])
                for val in data:
                    writer.writerow([val])
        elif isinstance(data, dict):
            writer = csv.writer(output)
            writer.writerow(["Key", "Value"])
            for k, v in data.items():
                writer.writerow(
                    [
                        k,
                        json.dumps(v, ensure_ascii=False)
                        if isinstance(v, (dict, list))
                        else v,
                    ]
                )
        else:
            raise ValueError("JSON must be an array of objects or an object.")

        tool_logger.info(
            "converted json -> csv (%d bytes) in %.2fs",
            len(output.getvalue()),
            time.monotonic() - started,
        )
        return output.getvalue()

    def csv_to_json(self, csv_text: str) -> str:
        tool_logger = get_tool_logger("json-csv-converter")
        started = time.monotonic()
        import csv
        import json

        try:
            reader = csv.DictReader(
                StringIO(csv_text.strip()),
                restkey="_extra",
            )
            rows = [dict(row) for row in reader]
            tool_logger.info(
                "converted csv -> json (%d rows) in %.2fs",
                len(rows),
                time.monotonic() - started,
            )
            return json.dumps(rows, indent=2, ensure_ascii=False)
        except Exception as err:
            raise ValueError(f"Invalid CSV string: {err}")

    def json_format(self, json_text: str, minify: bool = False) -> str:
        tool_logger = get_tool_logger("json-formatter")
        started = time.monotonic()
        import json

        try:
            obj = json.loads(json_text)
            if minify:
                # ensure_ascii=False: "café" must not become "caf\\u00e9".
                result = json.dumps(
                    obj, separators=(",", ":"), ensure_ascii=False
                )
            else:
                result = json.dumps(obj, indent=2, ensure_ascii=False)
            tool_logger.info(
                "formatted json (%s, %d bytes) in %.2fs",
                "minified" if minify else "pretty",
                len(result.encode("utf-8")),
                time.monotonic() - started,
            )
            return result
        except Exception as err:
            raise ValueError(f"Invalid JSON string: {err}")


json_service = JsonService()
