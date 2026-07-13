import ast


def generate_code_outline(source_py_file: str, output_txt_file: str):
    with open(source_py_file, "r", encoding="utf-8") as f:
        source_code = f.read()

    tree = ast.parse(source_code)
    outline = []

    # ------------------------
    # Module docstring
    # ------------------------
    module_doc = ast.get_docstring(tree)
    if module_doc:
        outline.append('"""')
        outline.append(module_doc)
        outline.append('"""')
        outline.append("")

    # ------------------------
    # Dependencies
    # ------------------------
    dependencies = []

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("src"):
                imported = ", ".join(alias.name for alias in node.names)
                dependencies.append(
                    f"from {node.module} import {imported}"
                )

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src"):
                    dependencies.append(f"import {alias.name}")

    if dependencies:
        outline.append("dependencies:")
        outline.extend(dependencies)
        outline.append("")

    # ------------------------
    # Classes & functions
    # ------------------------
    for node in tree.body:

        if isinstance(node, ast.ClassDef):
            outline.append(f"class {node.name}:")

            for subnode in node.body:
                if isinstance(subnode, ast.FunctionDef):
                    outline.append(f"    def {subnode.name}()")
                elif isinstance(subnode, ast.AsyncFunctionDef):
                    outline.append(f"    async def {subnode.name}()")

            outline.append("")

        elif isinstance(node, ast.FunctionDef):
            outline.append(f"def {node.name}()")

        elif isinstance(node, ast.AsyncFunctionDef):
            outline.append(f"async def {node.name}()")

    with open(output_txt_file, "a", encoding="utf-8") as f:
        f.write("\n".join(outline))

    print(f"Saved outline to {output_txt_file}")


if __name__ == "__main__":
    generate_code_outline(
        "src\\api\\recommendation_router.py",
        "routes.txt"
    )