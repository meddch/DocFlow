import os
import ast
from typing import Dict, List, Any, Union

class CodeParser:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.supported_extensions = {
            '.py': self._parse_python,
            # Add more language parsers as needed
        }
        self.max_file_size = 100 * 1024  # 100KB limit per file
        self.excluded_dirs = {
            'venv',
            'env',
            '.git',
            '__pycache__',
            'node_modules',
            'dist',
            'build'
        }
        self.excluded_files = {
            '.pyc',
            '.pyo',
            '.pyd',
            '.so',
            '.dll',
            '.dylib'
        }
        
    def _should_skip(self, path: str) -> bool:
        """Check if a path should be skipped."""
        path_parts = path.split(os.sep)
        
        # Check if any part of the path is in excluded directories
        if any(part in self.excluded_dirs for part in path_parts):
            return True
            
        # Check if file extension is in excluded files
        _, ext = os.path.splitext(path)
        if ext in self.excluded_files:
            return True
            
        return False
        
    def _add_parent_refs(self, node: ast.AST, parent: ast.AST = None):
        """Add parent references to all nodes in the AST."""
        node.parent = parent
        for child in ast.iter_child_nodes(node):
            self._add_parent_refs(child, node)
            
    def parse_project(self) -> Dict[str, Any]:
        """Parse all supported files in the project directory."""
        project_structure = {}
        total_size = 0
        max_total_size = 500 * 1024  # 500KB total limit
        
        for root, dirs, files in os.walk(self.project_path):
            # Modify dirs in place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Skip excluded files and directories
                if self._should_skip(file_path):
                    continue
                    
                ext = os.path.splitext(file)[1]
                if ext in self.supported_extensions:
                    # Skip files that are too large
                    file_size = os.path.getsize(file_path)
                    if file_size > self.max_file_size:
                        print(f"Skipping large file: {file_path}")
                        continue
                        
                    # Skip if total size would exceed limit
                    if total_size + file_size > max_total_size:
                        print(f"Reached total size limit, skipping remaining files")
                        return project_structure
                        
                    relative_path = os.path.relpath(file_path, self.project_path)
                    try:
                        file_structure = self.supported_extensions[ext](file_path)
                        project_structure[relative_path] = file_structure
                        total_size += file_size
                    except Exception as e:
                        print(f"Error parsing {file_path}: {e}")
        
        return project_structure
    
    def _parse_python(self, file_path: str) -> Dict[str, Any]:
        """Parse Python file and extract its structure."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
            self._add_parent_refs(tree)  # Add parent references
            
            # Extract classes and functions
            classes = []
            functions = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(self._extract_class_info(node))
                elif isinstance(node, ast.FunctionDef):
                    # Only include top-level functions
                    if isinstance(getattr(node, 'parent', None), ast.Module):
                        functions.append(self._extract_function_info(node))
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.append(self._extract_import_info(node))
            
            return {
                'classes': classes,
                'functions': functions,
                'imports': imports,
                'docstring': ast.get_docstring(tree)
            }
        except SyntaxError:
            return {'error': 'Syntax error in file'}
    
    def _extract_class_info(self, node: ast.ClassDef) -> Dict[str, Any]:
        """Extract information about a class."""
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(self._extract_function_info(item))
        
        return {
            'name': node.name,
            'methods': methods,
            'docstring': ast.get_docstring(node)
        }
    
    def _extract_function_info(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Extract information about a function."""
        args = []
        
        for arg in node.args.args:
            arg_info = {'name': arg.arg}
            if arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    arg_info['type'] = arg.annotation.id
                elif isinstance(arg.annotation, ast.Subscript):
                    arg_info['type'] = self._extract_annotation(arg.annotation)
            args.append(arg_info)
        
        return {
            'name': node.name,
            'args': args,
            'docstring': ast.get_docstring(node)
        }
    
    def _extract_import_info(self, node: Union[ast.Import, ast.ImportFrom]) -> Dict[str, Any]:
        """Extract information about an import statement."""
        if isinstance(node, ast.Import):
            return {'type': 'import', 'names': [n.name for n in node.names]}
        else:
            return {
                'type': 'import_from',
                'module': node.module,
                'names': [n.name for n in node.names]
            }
    
    def _extract_annotation(self, node: ast.Subscript) -> str:
        """Extract type annotation from a subscript node."""
        if isinstance(node.value, ast.Name):
            if isinstance(node.slice, ast.Name):
                return f"{node.value.id}[{node.slice.id}]"
        return "complex_type"
