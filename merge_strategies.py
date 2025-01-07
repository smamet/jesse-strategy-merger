# This script is used to merge multiple strategies into a single strategy.

# 1) This script will take the strategies names as input.
# 2) Create a new strategy file strategies/MainStrategy[Y-m-d]/__init__.py
# 3) Find the files path will be strategies/[strategy_name]/__init__.py and get as text so that we can edit the code.
# 4) At the beginning of the code create an array containing the strategies names and there priority (integer).

# 5) For each strategy
#     - For every function and property not in this list: "before, after, should_long, should_short, on_open_position, on_close_position, update_position, should_cancel_entry, go_long, go_short, __init__", prefix the function by the strategy name and rename all calls to theses functions accordingly.
#     - For functions should_long, should_short, copy the code add them to the new merged strategy same function name and separate them by a comment, also store the strategies that return true in an array.
#     - If any of this functions return true, store the strategy name in a global variable called active_strategy.
#     - For functions before, after, on_open_position, on_close_position, update_position, should_cancel_entry, go_long, go_short, __init__, copy the code add them to the new merged strategy same function name and add a condition if the active_strategy is the same as the strategy name, then execute the code.
#     - For the hyperparameters, please merge all of them from each strategy into the hyperparameter function. Also prefix each parameter with the strategy name and replace all the calls in the existing code.

# 6) Save the new merged strategy to strategies/MainStrategy[Y-m-d]/__init__.py


import os
from datetime import datetime
import re
import ast
import astor  # To convert modified AST back to source code
import argparse

JESSE_GLOBAL_FUNCTIONS = [
    "get_candles", "log", "notify", "index_to_timestamp", "timestamp_to_index", 
    "anchor_timeframe", "crossed", "crossed_above", "crossed_below", "numpy_candles",
    "get_trading_exchanges", "get_position_exchanges", "get_all_exchanges",
    "terminate_session", "store_indicator_value", "get_indicator_value",
    "liquidate", "add_line_to_candle_chart", "add_line_to_chart", "add_extra_line_chart",
    "hyperparameters", "before", "after", "should_long", "should_short", "on_open_position", 
    "on_close_position", "update_position", "should_cancel_entry", "go_long", "go_short", "__init__"
]

JESSE_GLOBAL_ATTRIBUTES = [
    "active_strategy", "balance", "price", "time", "candles", 
    "position", "hp", "available_margin", "position", "index", 
    "is_long", "is_short", "order", "is_open", "hp", "exchange", 
    "symbol", "sell", "buy", "take_profit", "stop_loss", "stop_loss_price", 
    "timeframe", "index", "fee_rate", "close", "open", "high", "low",
    "current_candle"
]

# Wee will add an if self.active_strategy == [strategy_name] to the following functions:
FUNCTIONS_TO_ADD_IF = ["on_open_position", "on_close_position", "update_position", "should_cancel_entry", "go_long", "go_short"]


class FunctionMerger(ast.NodeTransformer):
    def __init__(self, file_names):
        self.file_names = file_names
        self.file_functions = {file_name: {} for file_name in file_names}
        self.merged_functions = {}
        self.modified_functions = set()  # Track modified functions
        self.current_file = None
        self.import_statements = set()  # Use a set to collect unique import statements

    def collect_imports(self, tree):
        """Collect import statements from the given AST tree."""
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self.import_statements.add(astor.to_source(node).strip())

    def get_strategy_name(self, file_path):
        # Extract the strategy name from the file path
        return file_path.split('/')[-2]

    def visit(self, node):
        # Set the current file for strategy name extraction
        if hasattr(node, 'lineno'):
            self.current_file = self.file_names[0]  # Assuming single file processing at a time
        return super().visit(node)

    def visit_Attribute(self, node):
        # Modify attributes that start with self. and are not in JESSE_GLOBAL_ATTRIBUTES
        if isinstance(node.value, ast.Name) and node.value.id == 'self' and node.attr not in JESSE_GLOBAL_ATTRIBUTES + JESSE_GLOBAL_FUNCTIONS:
            strategy_name = self.get_strategy_name(self.current_file)
            if not node.attr.startswith(f"{strategy_name}_"):
                node.attr = f"{strategy_name}_{node.attr}"
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Modify function names that are not in JESSE_GLOBAL_FUNCTIONS
        if node.name not in JESSE_GLOBAL_FUNCTIONS + JESSE_GLOBAL_ATTRIBUTES and node.name not in self.modified_functions:
            strategy_name = self.get_strategy_name(self.current_file)
            if not node.name.startswith(f"{strategy_name}_"):
                node.name = f"{strategy_name}_{node.name}"
                self.modified_functions.add(node.name)
        return self.generic_visit(node)

    def visit_Call(self, node):
        # Only modify function calls that are methods of the class (i.e., prefixed by self)
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
            if node.func.attr not in JESSE_GLOBAL_FUNCTIONS + JESSE_GLOBAL_ATTRIBUTES and node.func.attr not in self.modified_functions:
                strategy_name = self.get_strategy_name(self.current_file)
                if not node.func.attr.startswith(f"{strategy_name}_"):
                    node.func.attr = f"{strategy_name}_{node.func.attr}"
                    self.modified_functions.add(node.func.attr)
        return self.generic_visit(node)

    def collect_functions(self, file_name, tree):
        """Collect functions from the given AST tree and associate them with the file name."""
        self.current_file = file_name  # Set the current file for strategy name extraction
        function_map = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_map[node.name] = node
        self.file_functions[file_name] = function_map

    def modify_return_statements(self, body, strategy_name, function_name):
        """Recursively modify return statements in the function body."""
        modified_body = []
        for node in body:
            if isinstance(node, ast.Return):
                # Create assignment statement
                var_name = f"{strategy_name}_{function_name}"
                assignment = ast.Assign(
                    targets=[ast.Name(id=var_name, ctx=ast.Store())],
                    value=node.value
                )
                # Create if statement
                condition = ast.Compare(
                    left=ast.Name(id=var_name, ctx=ast.Load()),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=True)]
                )
                if_body = [
                    ast.Assign(
                        targets=[ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr='active_strategy', ctx=ast.Store())],
                        value=ast.Constant(value=strategy_name)
                    ),
                    ast.Return(value=ast.Constant(value=True))
                ]
                if_statement = ast.If(test=condition, body=if_body, orelse=[])
                modified_body.extend([assignment, if_statement])
            elif isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                # Recursively modify return statements in nested blocks
                node.body = self.modify_return_statements(node.body, strategy_name, function_name)
                if hasattr(node, 'orelse'):
                    node.orelse = self.modify_return_statements(node.orelse, strategy_name, function_name)
                modified_body.append(node)
            else:
                modified_body.append(node)
        return modified_body

    def merge_functions(self):
        """Merge functions from all files, combining functions with the same name."""
        all_function_names = set(
            name for functions in self.file_functions.values() for name in functions
        )
        combined_hyperparameters = []  # Collect hyperparameters arrays
        on_close_position_body = []  # Collect on_close_position bodies
        should_short_body = []  # Collect should_short bodies

        for name in all_function_names:
            combined_body = []
            first_func = None
            super_call_added = False  # Track if super call has been added
            for file_name in self.file_names:
                if name in self.file_functions[file_name]:
                    func = self.file_functions[file_name][name]
                    if not first_func:
                        first_func = func  # Save the first occurrence of the function
                    strategy_name = self.get_strategy_name(file_name)
                    # Modify return statements in should_long and should_short
                    if name == "should_long":
                        modified_body = self.modify_return_statements(func.body, strategy_name, name)
                    elif name == "should_short":
                        # Collect the body for should_short
                        modified_body = self.modify_return_statements(func.body, strategy_name, name)
                        should_short_body.extend(modified_body)
                    elif name == "hyperparameters":
                        # Collect arrays from hyperparameters
                        for node in func.body:
                            if isinstance(node, ast.Return) and isinstance(node.value, ast.List):
                                combined_hyperparameters.extend(node.value.elts)
                    else:
                        modified_body = func.body
                        # Check for super call
                        for node in func.body:
                            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                                if isinstance(node.value.func, ast.Attribute) and node.value.func.attr == name:
                                    if not super_call_added:
                                        combined_body.append(node)
                                        super_call_added = True
                                    continue
                    # Wrap the function body with the conditional if needed
                    if name in FUNCTIONS_TO_ADD_IF:
                        condition = ast.Compare(
                            left=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr='active_strategy', ctx=ast.Load()),
                            ops=[ast.Eq()],
                            comparators=[ast.Constant(value=strategy_name)]
                        )
                        wrapped_body = [ast.If(test=condition, body=modified_body, orelse=[])]
                        combined_body.extend([
                            ast.Expr(ast.Str(f"# Merged from {file_name}")),
                            *wrapped_body,
                        ])
                    else:
                        combined_body.extend([
                            ast.Expr(ast.Str(f"# Merged from {file_name}")),
                            *modified_body,
                        ])
                    if name == "on_close_position":
                        # Collect the body for on_close_position
                        on_close_position_body.extend(combined_body)
            if first_func:
                if name == "__init__":
                    # Ensure self.active_strategy = None is in the __init__ function
                    combined_body.insert(0, ast.Assign(
                        targets=[ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr='active_strategy', ctx=ast.Store())],
                        value=ast.Constant(value=None)
                    ))
                elif name == "hyperparameters":
                    # Create a merged hyperparameters function
                    combined_body = [
                        ast.Expr(ast.Str(f"# Merged from multiple strategies")),
                        ast.Return(value=ast.List(elts=combined_hyperparameters, ctx=ast.Load()))
                    ]
                merged_function = ast.FunctionDef(
                    name=name,
                    args=first_func.args,
                    body=combined_body,
                    decorator_list=first_func.decorator_list,
                    returns=first_func.returns,
                )
                self.merged_functions[name] = merged_function

        # Ensure should_short exists and add global check at the top
        if should_short_body:
            # Add protection comment
            protection_comment = ast.Expr(value=ast.Str(s="# Protection to prevent long & short at the same time (will trigger an error on jesse)"))
            global_check = ast.If(
                test=ast.Call(
                    func=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr='should_long', ctx=ast.Load()),
                    args=[],
                    keywords=[]
                ),
                body=[ast.Return(value=ast.Constant(value=False))],
                orelse=[]
            )
            should_short_body.insert(0, global_check)
            should_short_body.insert(0, protection_comment)
            should_short_func = ast.FunctionDef(
                name="should_short",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(arg='self')],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[]
                ),
                body=should_short_body,
                decorator_list=[]
            )
            self.merged_functions["should_short"] = should_short_func

        # Ensure on_close_position exists and add self.active_strategy = None at the end
        if on_close_position_body:
            on_close_position_body.append(ast.Assign(
                targets=[ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr='active_strategy', ctx=ast.Store())],
                value=ast.Constant(value=None)
            ))
            on_close_position_func = ast.FunctionDef(
                name="on_close_position",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(arg='self'), ast.arg(arg='order')],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[]
                ),
                body=on_close_position_body,
                decorator_list=[]
            )
            self.merged_functions["on_close_position"] = on_close_position_func

        # Ensure __init__ exists if not present
        if "__init__" not in self.merged_functions:
            init_func = ast.FunctionDef(
                name="__init__",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(arg='self')],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[]
                ),
                body=[
                    ast.Assign(
                        targets=[ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr='active_strategy', ctx=ast.Store())],
                        value=ast.Constant(value=None)
                    )
                ],
                decorator_list=[]
            )
            self.merged_functions["__init__"] = init_func

    def generate_merged_tree(self):
        """Generate a new AST tree with merged functions inside a class."""
        date_str = datetime.now().strftime('%Y%m%d')
        class_name = f"MainStrategy{date_str}"
        
        # Separate attributes, properties, JESSE_GLOBAL_FUNCTIONS, and other functions
        attributes = []
        properties = []
        global_functions = []
        other_functions = []
        
        for func_name, func_node in self.merged_functions.items():
            if any(isinstance(decorator, ast.Name) and decorator.id == 'property' for decorator in func_node.decorator_list):
                properties.append(func_node)
            elif func_name in JESSE_GLOBAL_ATTRIBUTES:
                attributes.append(func_node)
            elif func_name in JESSE_GLOBAL_FUNCTIONS:
                global_functions.append(func_node)
            else:
                other_functions.append(func_node)
        
        # Combine all parts in the desired order
        class_body = attributes + properties + global_functions + other_functions
        
        class_def = ast.ClassDef(
            name=class_name,
            bases=[ast.Name(id='Strategy', ctx=ast.Load())],  # Add Strategy as a base class
            keywords=[],
            body=class_body,
            decorator_list=[]
        )
        
        return ast.Module(body=[class_def])


def merge_files(strategy_names, output_path):
    # Parse the files
    trees = []
    all_imports = set()  # Use a set to collect unique import statements
    
    for strategy_name in strategy_names:
        file_path = f'strategies/{strategy_name}/__init__.py'
        with open(file_path, "r") as f:
            tree = ast.parse(f.read())
            # Apply transformations
            merger = FunctionMerger([file_path])
            merger.collect_imports(tree)  # Collect imports
            merger.visit(tree)
            trees.append((file_path, tree))
            all_imports.update(merger.import_statements)  # Add collected imports

    # Merge functions
    merger = FunctionMerger([file_path for file_path, _ in trees])
    for file_path, tree in trees:
        merger.collect_functions(file_path, tree)
    merger.merge_functions()

    # Generate the new file
    merged_tree = merger.generate_merged_tree()
    merged_code = astor.to_source(merged_tree)

    # Add unique imports to the top of the merged code
    import_code = "\n".join(sorted(all_imports))
    final_code = f"{import_code}\n\n{merged_code}"

    # Write the merged code to the output file
    with open(output_path, "w") as output_file:
        output_file.write(final_code)

    print(f"Merged file written to: {output_path}")


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Merge strategies into a single strategy.')
    parser.add_argument('strategies', metavar='S', type=str, nargs='+',
                        help='a list of strategy names to merge')

    # Parse arguments
    args = parser.parse_args()

    # Use the provided strategies
    strategies_to_merge = args.strategies

    # Create directory for the new merged strategy
    date_str = datetime.now().strftime('%Y%m%d')
    main_strategy_path = f'strategies/MainStrategy{date_str}/'
    os.makedirs(main_strategy_path, exist_ok=True)

    output_file = os.path.join(main_strategy_path, '__init__.py')
    merge_files(strategies_to_merge, output_file)

if __name__ == "__main__":
    main()
