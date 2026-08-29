import ast
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
RESULTS_PATH = ROOT_DIR / "tests/reports/results_log.json"
OUTPUT_PATH = ROOT_DIR / "tests/test-cases/api-test-matrix.md"

HTTP_METHODS = ("post", "get", "put", "delete", "patch")


def extract_docstrings(test_file):
    source = (ROOT_DIR / test_file).read_text()
    tree = ast.parse(source)
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name.startswith("test_"):
            result[node.name] = ast.get_docstring(node) or ""
    return result


def collect_local_vars(node):
    """Collect dict literals assigned to names, plus a source-text fallback for dicts
    containing non-literal expressions (e.g. future_time(48))."""
    local_vars = {}
    for stmt in ast.walk(node):
        if isinstance(stmt, ast.Assign):
            try:
                value = ast.literal_eval(stmt.value)
                if isinstance(value, dict):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            local_vars[target.id] = value
            except Exception:
                try:
                    source_text = ast.unparse(stmt.value)
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            local_vars.setdefault(target.id + "__source", source_text)
                except Exception:
                    pass
    return local_vars


def collect_http_calls(node):
    """Every client.<verb>(...) call in the function, in source order."""
    calls = []
    for stmt in ast.walk(node):
        if not (isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Attribute)):
            continue
        if stmt.func.attr not in HTTP_METHODS:
            continue
        url = None
        if stmt.args:
            try:
                url = ast.literal_eval(stmt.args[0])
            except Exception:
                try:
                    url = ast.unparse(stmt.args[0])
                except Exception:
                    url = None
        calls.append({
            "node": stmt,
            "lineno": stmt.lineno,
            "method": stmt.func.attr.upper(),
            "url": url,
        })
    calls.sort(key=lambda c: c["lineno"])
    return calls


def find_asserted_names(node):
    """Names that appear inside assert statements, e.g. 'response', 'body'."""
    names = set()
    for stmt in ast.walk(node):
        if isinstance(stmt, ast.Assert):
            for sub in ast.walk(stmt.test):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
    return names


def map_assignments_to_calls(node):
    """Which variable name each HTTP call result was assigned to."""
    mapping = {}
    for stmt in ast.walk(node):
        if not isinstance(stmt, ast.Assign):
            continue
        value = stmt.value
        if isinstance(value, ast.Await):
            value = value.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
            if value.func.attr in HTTP_METHODS:
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        mapping[value.lineno] = target.id
    return mapping


def pick_call_under_test(calls, node):
    """Choose the call the assertions are actually about, rather than just the last
    call ast.walk happens to visit. Prefers the last call whose result variable is
    referenced inside an assert; falls back to the last call overall."""
    if not calls:
        return None

    asserted = find_asserted_names(node)
    assigned = map_assignments_to_calls(node)

    scored = []
    for call in calls:
        name = assigned.get(call["lineno"])
        if name and name in asserted:
            scored.append(call)
        elif name is None:
            # unassigned call result (e.g. `response = await client.patch(...)` used
            # directly without an intermediate variable check) -- still a candidate
            scored.append(call)

    if scored:
        return scored[-1]
    return calls[-1]


def render_json_input(kw_value, local_vars):
    """Render the json= kwarg value as a readable input string."""
    if isinstance(kw_value, ast.Name):
        if kw_value.id in local_vars:
            return json.dumps(local_vars[kw_value.id])
        if (kw_value.id + "__source") in local_vars:
            return local_vars[kw_value.id + "__source"]
    try:
        return json.dumps(ast.literal_eval(kw_value))
    except Exception:
        try:
            return ast.unparse(kw_value)
        except Exception:
            return "see test code"


def extract_test_details(test_file, func_name):
    source = (ROOT_DIR / test_file).read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not (isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == func_name):
            continue

        local_vars = collect_local_vars(node)

        expected_parts = []
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Assert):
                try:
                    expected_parts.append(ast.unparse(stmt.test))
                except Exception:
                    pass
            if isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    call = item.context_expr
                    if isinstance(call, ast.Call) and getattr(call.func, "attr", "") == "raises":
                        exc_name = ast.unparse(call.args[0]) if call.args else "Exception"
                        expected_parts.append(f"raises {exc_name}")

        expected = " AND ".join(expected_parts) if expected_parts else "see test code"

        calls = collect_http_calls(node)
        chosen = pick_call_under_test(calls, node)

        if chosen is not None:
            api = f"{chosen['method']} {chosen['url']}" if chosen["url"] else chosen["method"]
            inputs = None
            for kw in chosen["node"].keywords:
                if kw.arg == "json":
                    inputs = render_json_input(kw.value, local_vars)
                    break
            if inputs is None:
                inputs = "N/A"
            return api, inputs, expected

        # no HTTP call found, look for a plain function call instead (unit tests)
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Name):
                func_called = stmt.func.id
                if func_called.startswith("test_"):
                    continue
                try:
                    args_repr = ", ".join(ast.unparse(a) for a in stmt.args)
                    return f"{func_called}()", (args_repr or "no arguments"), expected
                except Exception:
                    return f"{func_called}()", "see test code", expected

        return "N/A", "N/A", expected

    return "N/A", "N/A", "see test code"


def simplify_expected(expected_parts):
    simplified = []
    has_access_token = False
    has_refresh_token = False
    for part in expected_parts:
        if "status_code ==" in part:
            try:
                code = part.split("==")[1].strip()
                simplified.append(f"Status: `{code}`")
            except Exception:
                simplified.append(part)
        elif "status_code in" in part:
            try:
                opts = part.split("in")[1].strip()
                simplified.append(f"Status: `{opts}`")
            except Exception:
                simplified.append(part)
        elif "message' ==" in part or 'message" ==' in part or "message] ==" in part:
            try:
                msg = part.split("==")[1].strip()
                simplified.append(f"Message: {msg}")
            except Exception:
                simplified.append(part)
        elif "access_token" in part:
            has_access_token = True
        elif "refresh_token" in part:
            has_refresh_token = True
        elif part.startswith("raises "):
            simplified.append(part)
        else:
            if "==" in part:
                try:
                    left, right = part.split("==", 1)
                    left = left.strip()
                    right = right.strip()
                    if "body[" in left:
                        key = left.split("body[")[1].split("]")[0].strip("'\"")
                        simplified.append(f"{key.capitalize()}: {right}")
                    else:
                        simplified.append(f"`{part}`")
                except Exception:
                    simplified.append(f"`{part}`")
            else:
                simplified.append(f"`{part}`")

    if has_access_token or has_refresh_token:
        tokens = []
        if has_access_token:
            tokens.append("access_token")
        if has_refresh_token:
            tokens.append("refresh_token")
        simplified.append(f"Tokens: {', '.join(tokens)}")

    return "<br>".join(simplified)


def extract_actual_error(raw_error: str) -> str:
    lines_err = [l for l in raw_error.split("\n") if l.strip()]
    return lines_err[0].strip() if lines_err else "Failed"


def load_results(results_path):
    with open(results_path) as f:
        return json.load(f)


def build_table(results):
    lines = ["# API Test Case Matrix", ""]

    def get_category_name(test_file):
        path = Path(test_file)
        is_unit = "unit" in path.parts
        module_name = path.stem.replace("test_", "").replace("_", " ").title()
        test_type = "Unit Tests" if is_unit else "Integration Tests"
        return f"{module_name} {test_type}"

    grouped_results = {}
    for r in results:
        node_id = r["test"]
        test_file = node_id.split("::")[0]
        cat = get_category_name(test_file)
        grouped_results.setdefault(cat, []).append(r)

    docstring_cache = {}
    test_count = 1

    integration_cats = sorted([c for c in grouped_results if "Integration Tests" in c])
    unit_cats = sorted([c for c in grouped_results if "Unit Tests" in c])
    other_cats = sorted([c for c in grouped_results if c not in integration_cats and c not in unit_cats])

    all_cats = integration_cats + unit_cats + other_cats

    for cat in all_cats:
        lines.append(f"## {cat}")
        lines.append("")
        lines.append("| Test ID | Description | API / Function | Inputs | Expected Output | Actual Output | Result |")
        lines.append("|---|---|---|---|---|---|---|")

        for r in grouped_results[cat]:
            node_id = r["test"]
            parts = node_id.split("::")
            test_file = parts[0]
            func_name = parts[-1]
            outcome = r["outcome"]

            if test_file not in docstring_cache:
                docstring_cache[test_file] = extract_docstrings(test_file)
            raw_doc = docstring_cache[test_file].get(func_name, func_name.replace("_", " "))
            doc = raw_doc.replace("|", "-").strip()

            api, inputs, expected_raw = extract_test_details(test_file, func_name)

            expected_parts = [p.strip() for p in expected_raw.split(" AND ") if p.strip()]
            expected = simplify_expected(expected_parts)

            if outcome == "passed":
                actual = expected
                result = "Success"
            else:
                raw_error = r["error"] or "Failed"
                assert_err = extract_actual_error(raw_error)
                actual = f"<code>{assert_err}</code>"
                result = "Fail"

            prefix = "UT" if "unit" in test_file else "IT"
            case_id = f"**{prefix}-{test_count:03d}**"
            test_count += 1

            inputs_fmt = f"`{inputs}`" if inputs not in ("N/A", "see test code") else inputs
            api_fmt = f"`{api}`" if api != "N/A" else api

            lines.append(f"| {case_id} | {doc} | {api_fmt} | {inputs_fmt} | {expected} | {actual} | {result} |")

        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    results = load_results(RESULTS_PATH)
    table = build_table(results)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(table)