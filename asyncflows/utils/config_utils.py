import ast
import builtins


# def construct_optional_config(model: type[BaseModel]) -> type[BaseModel]:
#     return pydantic.create_model(
#         "Optional" + model.__name__,
#         __base__=model,
#         __module__=__name__,
#         model_config=ConfigDict(
#             arbitrary_types_allowed=True,
#         ),
#         **transform_and_templatify(
#             model,
#             vars_=None,
#             add_union=type(None),
#         ),
#     )


def get_names_from_ast(node: ast.AST, ignore_vars: None | frozenset = None) -> set:
    if ignore_vars is None:
        ignore_vars = frozenset()
    names = set()
    if isinstance(node, ast.Name):
        if node.id not in ignore_vars and node.id not in builtins.__dict__:
            names.add(node.id)
    elif isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
        new_ignore_vars = ignore_vars
        for gen in node.generators:
            # The 'target' introduces loop variables, add them to ignore list
            loop_vars = {n.id for n in ast.walk(gen.target) if isinstance(n, ast.Name)}
            new_ignore_vars |= loop_vars

            # Process 'iter' part which can include external dependencies
            names |= get_names_from_ast(gen.iter, new_ignore_vars)

            # Comprehensions can be nested, so handle 'ifs'
            for if_clause in gen.ifs:
                names |= get_names_from_ast(if_clause, new_ignore_vars)
    else:
        for child in ast.iter_child_nodes(node):
            names |= get_names_from_ast(child, ignore_vars)
    return names


def extract_attribute_path(node: ast.AST) -> str:
    """Helper function to correctly build the attribute path."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def get_full_paths_from_ast(node: ast.AST, ignore_vars: None | frozenset = None) -> set:
    if ignore_vars is None:
        ignore_vars = frozenset()
    paths = set()

    if isinstance(node, ast.Name):
        if node.id not in ignore_vars:
            paths.add(node.id)
    elif isinstance(node, ast.Attribute):
        full_path = extract_attribute_path(node)
        # Include the full path if the base variable is not ignored
        base_var = full_path.split(".")[0]
        if base_var not in ignore_vars:
            paths.add(full_path)
    elif isinstance(node, (ast.ListComp, ast.DictComp)):
        for gen in node.generators:
            loop_vars = {n.id for n in ast.walk(gen.target) if isinstance(n, ast.Name)}
            new_ignore_vars = ignore_vars | loop_vars

            paths |= get_full_paths_from_ast(gen.iter, new_ignore_vars)

            for if_clause in gen.ifs:
                paths |= get_full_paths_from_ast(if_clause, new_ignore_vars)
    else:
        for child in ast.iter_child_nodes(node):
            paths |= get_full_paths_from_ast(child, ignore_vars)

    return paths


_allowed_ast_types = (
    ast.Module,
    ast.Expr,
    ast.Constant,
    ast.Name,
    ast.Attribute,
    ast.Load,
    ast.Store,
    ast.ListComp,
    ast.comprehension,
    ast.List,
    ast.Dict,
    ast.Subscript,
    ast.Tuple,
    ast.BinOp,
    ast.Add,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Call,
    ast.JoinedStr,
    ast.FormattedValue,
)


def verify_ast(node: ast.AST):
    if not isinstance(node, _allowed_ast_types):
        raise ValueError(f"Unexpected AST type: {type(node)}")
    for child in ast.iter_child_nodes(node):
        verify_ast(child)


def collect_ast_types(node: ast.AST) -> set[type]:
    types = set()
    if isinstance(node, _allowed_ast_types):
        types.add(type(node))
        for child in ast.iter_child_nodes(node):
            types |= collect_ast_types(child)
    return types
