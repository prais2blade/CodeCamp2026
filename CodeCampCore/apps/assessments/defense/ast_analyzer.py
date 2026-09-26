import ast
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class CodeInsights:
    functions: List[str] = field(default_factory=list)
    variables: List[str] = field(default_factory=list)
    has_recursion: bool = False
    loops_count: int = 0
    nested_loops: bool = False
    uses_comprehension: bool = False
    uses_dict_or_set: bool = False
    has_conditionals: bool = False
    key_line_numbers: List[int] = field(default_factory=list)
    sample_snippet: str = ""


class PythonASTAnalyzer:
    """
    Parses submitted Python code using the official AST module to extract
    structural semantics, algorithmic complexity indicators, and variables.
    """

    @classmethod
    def analyze(cls, code: str) -> CodeInsights:
        insights = CodeInsights()
        lines = code.splitlines()

        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Fallback if syntax error in AST parse
            return insights

        current_function = None

        class ASTVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                nonlocal current_function
                insights.functions.append(node.name)
                insights.key_line_numbers.append(node.lineno)
                prev_fn = current_function
                current_function = node.name
                
                # Check for recursion inside function body
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name) and child.func.id == node.name:
                            insights.has_recursion = True

                self.generic_visit(node)
                current_function = prev_fn

            def visit_For(self, node):
                insights.loops_count += 1
                insights.key_line_numbers.append(node.lineno)
                for child in ast.walk(node):
                    if child is not node and isinstance(child, (ast.For, ast.While)):
                        insights.nested_loops = True
                self.generic_visit(node)

            def visit_While(self, node):
                insights.loops_count += 1
                insights.key_line_numbers.append(node.lineno)
                for child in ast.walk(node):
                    if child is not node and isinstance(child, (ast.For, ast.While)):
                        insights.nested_loops = True
                self.generic_visit(node)

            def visit_If(self, node):
                insights.has_conditionals = True
                self.generic_visit(node)

            def visit_ListComp(self, node):
                insights.uses_comprehension = True
                self.generic_visit(node)

            def visit_Dict(self, node):
                insights.uses_dict_or_set = True
                self.generic_visit(node)

            def visit_Set(self, node):
                insights.uses_dict_or_set = True
                self.generic_visit(node)

            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Store) and node.id not in insights.variables:
                    if not node.id.startswith('_') and node.id not in ('self', 'cls'):
                        insights.variables.append(node.id)
                self.generic_visit(node)

        visitor = ASTVisitor()
        visitor.visit(tree)

        # Select a sample snippet from line 1 to 15
        if lines:
            insights.sample_snippet = "\n".join(lines[:min(12, len(lines))])

        return insights


class DefenseQuestionGenerator:
    """
    Deterministically generates 3 targeted defense challenges directly derived from
    the student's parsed code structure, variables, and logic.
    """

    @classmethod
    def generate_defense_questions(cls, code: str, language: str = 'python') -> List[Dict[str, Any]]:
        questions = []
        insights = PythonASTAnalyzer.analyze(code) if language == 'python' else CodeInsights()

        primary_fn = insights.functions[0] if insights.functions else "your solution"
        primary_var = insights.variables[0] if insights.variables else "data"
        secondary_var = insights.variables[1] if len(insights.variables) > 1 else "result"

        # -------------------------------------------------------------
        # 1. EXPLAIN (Category: Time Complexity & Algorithmic Strategy)
        # -------------------------------------------------------------
        if insights.nested_loops:
            complexity_correct = "O(N^2) quadratic time complexity due to nested iteration"
            complexity_wrong1 = "O(N) linear time complexity"
            complexity_wrong2 = "O(log N) logarithmic time complexity"
            snippet = f"Nested loop block in function '{primary_fn}'"
        elif insights.has_recursion:
            complexity_correct = "O(2^N) or O(N) depending on recursion tree and memoization"
            complexity_wrong1 = "O(1) constant time complexity"
            complexity_wrong2 = "O(N^3) cubic time complexity"
            snippet = f"Recursive invocation of '{primary_fn}'"
        elif insights.loops_count > 0:
            complexity_correct = "O(N) linear time complexity traversing input elements"
            complexity_wrong1 = "O(N^2) quadratic time complexity"
            complexity_wrong2 = "O(1) constant time complexity"
            snippet = f"Iteration loop manipulating variable '{primary_var}'"
        else:
            complexity_correct = "O(1) constant time operations without loops"
            complexity_wrong1 = "O(N) linear time iteration"
            complexity_wrong2 = "O(N log N) sorting overhead"
            snippet = f"Direct algorithmic execution in '{primary_fn}'"

        q1 = {
            "order": 1,
            "category": "explain",
            "time_limit_sec": 90,
            "prompt": f"Analyze your implementation in function '{primary_fn}'. What is the asymptotic time complexity of this code and how does it scale as input size N grows?",
            "target_code_snippet": snippet,
            "options": [
                {"key": "A", "text": complexity_correct},
                {"key": "B", "text": complexity_wrong1},
                {"key": "C", "text": complexity_wrong2},
                {"key": "D", "text": "Unbounded time complexity leading to inevitable memory starvation"},
            ],
            "correct_answer": "A",
            "rubric_notes": "Student should identify time complexity based on loop depth and recursive branches."
        }
        questions.append(q1)

        # -------------------------------------------------------------
        # 2. PREDICT (Category: Edge Case Execution & Mutant Tracing)
        # -------------------------------------------------------------
        if insights.uses_comprehension:
            pred_prompt = f"In function '{primary_fn}', what will the comprehension evaluate to if the input iterable is completely empty (e.g. `[]` or `None`)?"
            correct_pred = "Returns an empty collection [] without raising an IndexError"
            wrong_pred1 = "Raises an immediate IndexError exception"
            wrong_pred2 = "Returns None"
        elif insights.loops_count > 0:
            pred_prompt = f"During execution of '{primary_fn}', what is the state of variable '{primary_var}' if the input sequence has only a single element?"
            correct_pred = "The loop executes exactly once, processing the single item without off-by-one errors"
            wrong_pred1 = "The loop condition fails to trigger, returning initial undefined state"
            wrong_pred2 = "An infinite loop occurs waiting for second element termination"
        else:
            pred_prompt = f"If the input parameters to '{primary_fn}' contain unexpected negative numbers or zeroes, how does your logic react?"
            correct_pred = "Computes the standard arithmetic result according to defined mathematical signs"
            wrong_pred1 = "Throws an uncaught OverflowError"
            wrong_pred2 = "Terminates the host process immediately"

        q2 = {
            "order": 2,
            "category": "predict",
            "time_limit_sec": 90,
            "prompt": pred_prompt,
            "target_code_snippet": f"Tracking variable '{primary_var}' and conditional logic",
            "options": [
                {"key": "A", "text": correct_pred},
                {"key": "B", "text": wrong_pred1},
                {"key": "C", "text": wrong_pred2},
                {"key": "D", "text": "Raises a silent NullPointer / TypeError across all interpreters"},
            ],
            "correct_answer": "A",
            "rubric_notes": "Checks student grasp of edge cases (empty inputs, singletons, zeroes)."
        }
        questions.append(q2)

        # -------------------------------------------------------------
        # 3. MODIFY (Category: Architectural Refactoring & Optimization)
        # -------------------------------------------------------------
        if insights.has_recursion:
            mod_prompt = f"If stack depth limits become a bottleneck in large scale production runs for '{primary_fn}', what is the optimal modification?"
            mod_correct = "Convert the recursive logic to an iterative loop using an explicit stack or dynamic programming table"
            mod_wrong1 = "Increase sys.setrecursionlimit to 1,000,000 without algorithmic refactoring"
            mod_wrong2 = "Wrap the recursive call in a generic try/except block to catch RecursionError"
        elif insights.nested_loops:
            mod_prompt = f"How would you refactor '{primary_fn}' to reduce its time complexity from O(N^2) to O(N) linear time?"
            mod_correct = f"Utilize a hash map (dict) or set for variable '{secondary_var}' to enable O(1) average-time lookups"
            mod_wrong1 = "Replace the inner for-loop with a while-loop using the same iteration indices"
            mod_wrong2 = "Sort the array before nested iterations using Bubble Sort"
        else:
            mod_prompt = f"If this problem requires handling continuous real-time streaming data where memory must remain O(1), how should your solution be adapted?"
            mod_correct = "Convert the return logic to a Python generator using `yield` instead of buffering complete results in memory"
            mod_wrong1 = "Store all stream frames in a global dictionary buffer"
            mod_wrong2 = "Dump intermediate frames to a temporary disk file on every invocation"

        q3 = {
            "order": 3,
            "category": "modify",
            "time_limit_sec": 120,
            "prompt": mod_prompt,
            "target_code_snippet": f"Refactoring '{primary_fn}' for memory & scalability",
            "options": [
                {"key": "A", "text": mod_correct},
                {"key": "B", "text": mod_wrong1},
                {"key": "C", "text": mod_wrong2},
                {"key": "D", "text": "Spawn 100 detached child threads to parallelize CPU-bound iterations"},
            ],
            "correct_answer": "A",
            "rubric_notes": "Evaluates software engineering judgment and memory/space trade-offs."
        }
        questions.append(q3)

        return questions
