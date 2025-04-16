from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema import SystemMessage
from config.settings import OPENAI_API_KEY
import json

class DocumentationGenerator:
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        self.llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            model_name=model_name,
            temperature=0.2,
        )
        
    def _create_prompt_and_chain(self, system_message: str, human_template: str):
        """Create a prompt chain using the newer LangChain API."""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_message),
            HumanMessagePromptTemplate.from_template(human_template)
        ])
        chain = prompt | self.llm
        return chain
        
    def _chunk_analysis(self, analysis: Dict[str, Any], max_tokens: int = 4000) -> List[Dict[str, Any]]:
        """Split analysis into smaller chunks to avoid token limits."""
        chunks = []
        current_chunk = {}
        current_size = 0
        
        for file_path, file_data in analysis.get('project_structure', {}).items():
            file_str = json.dumps(file_data)
            file_tokens = len(file_str.split()) * 1.5  # Rough token estimate
            
            if file_tokens > max_tokens:
                # If a single file is too large, include only essential info
                summary = {
                    'docstring': file_data.get('docstring', ''),
                    'classes': [{'name': c['name'], 'docstring': c.get('docstring', '')} 
                              for c in file_data.get('classes', [])],
                    'functions': [{'name': f['name'], 'docstring': f.get('docstring', '')} 
                                for f in file_data.get('functions', [])]
                }
                file_str = json.dumps(summary)
                file_tokens = len(file_str.split()) * 1.5
            
            if current_size + file_tokens > max_tokens:
                chunks.append(current_chunk)
                current_chunk = {}
                current_size = 0
            
            current_chunk[file_path] = file_data
            current_size += file_tokens
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _extract_modules(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract modules from project structure for better documentation organization."""
        modules = {}
        project_structure = analysis.get('project_structure', {})
        
        # Group files by directory (module)
        for file_path, file_data in project_structure.items():
            # Skip empty files
            if not file_data:
                continue
                
            # Extract directory/module name from file path
            parts = file_path.split('/')
            if len(parts) > 1 and parts[0] not in ('venv', '__pycache__'):
                module_name = parts[0]  # Use first directory as module name
            else:
                # If file is at root level or in a special directory
                if '.' in parts[-1]:  # It's a file with extension
                    extension = parts[-1].split('.')[-1]
                    if extension in ('py', 'js', 'ts'):
                        module_name = "core"  # Main code files go to core
                    elif extension in ('md', 'txt'):
                        module_name = "documentation"  # Documentation files
                    else:
                        module_name = "other"  # Other files
                else:
                    module_name = "other"
            
            # Skip temporary files, cache, etc.
            if module_name in ('__pycache__', 'venv', '.git', 'build', 'dist'):
                continue
                
            # Initialize module if not exists
            if module_name not in modules:
                modules[module_name] = {}
            
            # Add file data to module with simplified key (just filename)
            filename = parts[-1] if len(parts) > 0 else file_path
            modules[module_name][filename] = file_data
            
        return modules
    
    def generate_project_overview(self, analysis: Dict[str, Any]) -> str:
        """Generate a project overview based on code analysis."""
        # First, get information about modules for a better integrated overview
        modules = self._extract_modules(analysis)
        module_info = {name: self._summarize_module(name, data) for name, data in modules.items()}
        
        chain = self._create_prompt_and_chain(
            system_message="""You are a technical documentation expert specializing in creating clear, comprehensive documentation.
Focus on explaining the project's purpose, architecture, and value proposition.
Use concrete examples and clear explanations.
Break down complex concepts into digestible sections.
Create a cohesive narrative that connects all components of the project.""",
            human_template=(
                "Generate detailed project documentation based on this code analysis:\n\n"
                "{analysis}\n\n"
                "The project has the following modules: {module_summary}\n\n"
                "Include the following sections with detailed explanations and examples:\n\n"
                "# Project Overview\n\n"
                "## Purpose and Goals\n"
                "- What problem does this project solve?\n"
                "- Who is the target audience?\n"
                "- What are the main objectives?\n\n"
                "## Key Features\n"
                "- List and explain main functionalities\n"
                "- Highlight unique selling points\n"
                "- Provide usage examples\n\n"
                "## Technical Architecture\n"
                "- System components and their interactions\n"
                "- Design patterns and principles used\n"
                "- Data flow and processing\n"
                "- How the different modules work together\n\n"
                "## Module Integration\n"
                "- Explain how the different modules connect to each other\n"
                "- Describe the responsibility of each module and its role in the overall system\n"
                "- Show the data flow between modules\n\n"
                "## Technology Stack\n"
                "- Core technologies and frameworks\n"
                "- External dependencies\n"
                "- System requirements\n\n"
                "## Getting Started\n"
                "- Installation steps\n"
                "- Configuration requirements\n"
                "- Quick start guide\n\n"
                "Format in Markdown with clear headings, lists, and code examples where relevant."
            )
        )
        
        chunks = self._chunk_analysis(analysis)
        if len(chunks) == 1:
            return chain.invoke({
                "analysis": str(analysis), 
                "module_summary": str(module_info)
            }).content
            
        overview_parts = []
        for chunk in chunks:
            result = chain.invoke({
                "analysis": str(chunk), 
                "module_summary": str(module_info)
            }).content
            overview_parts.append(result)
        
        return "\n\n".join(overview_parts)
        
    def _summarize_module(self, module_name: str, module_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of a module for better integrated documentation."""
        summary = {
            "name": module_name,
            "files": list(module_data.keys()),
            "classes": [],
            "functions": []
        }
        
        for file_name, file_data in module_data.items():
            # Extract classes
            for cls in file_data.get('classes', []):
                class_info = {
                    "name": cls.get('name', ''),
                    "methods": [m.get('name', '') for m in cls.get('methods', [])],
                    "purpose": cls.get('docstring', '')[:100] + '...' if cls.get('docstring') else 'No description'
                }
                summary["classes"].append(class_info)
            
            # Extract functions  
            for func in file_data.get('functions', []):
                func_info = {
                    "name": func.get('name', ''),
                    "purpose": func.get('docstring', '')[:100] + '...' if func.get('docstring') else 'No description'
                }
                summary["functions"].append(func_info)
                
        return summary
    
    def generate_module_docs(self, module_name: str, module_data: Dict[str, Any]) -> str:
        """Generate documentation for a specific module."""
        chain = self._create_prompt_and_chain(
            system_message="""You are a technical writer specializing in API and module documentation.
Focus on practical usage, clear examples, and proper technical details.
Explain complex functionality in simple terms while maintaining technical accuracy.
Structure your documentation with clear headings and sections.
Use a professional tone and format for technical documentation.""",
            human_template=(
                "Generate comprehensive module documentation for:\n\n"
                "Module: {module_name}\n"
                "Data: {module_data}\n\n"
                "Include these sections with clear Markdown heading structure:\n\n"
                "# {module_name} Module\n\n"
                "## Overview\n"
                "- Module purpose and responsibility\n"
                "- Key functionalities\n"
                "- Usage scenarios\n\n"
                "## Classes\n"
                "For each class, use level 3 headings (###) and include:\n"
                "- Purpose and usage\n"
                "- Constructor parameters (use bullet points with bold parameter names like `**parameter_name**`)\n"
                "- Important methods (use bullet points with bold method names like `**method_name**`)\n"
                "- Usage examples (in code blocks with proper language syntax)\n\n"
                "## Functions\n"
                "For each standalone function, use level 3 headings (###) and include:\n"
                "- Purpose\n"
                "- Parameters and return values (use bullet points with bold parameter names)\n"
                "- Usage examples\n"
                "- Error handling\n\n"
                "## Integration\n"
                "- How to integrate with other modules\n"
                "- Common usage patterns\n"
                "- Best practices\n\n"
                "## Dependencies\n"
                "- Required modules and packages\n"
                "- Version requirements\n"
                "- External dependencies\n\n"
                "Format all headings with proper Markdown heading levels (# for main title, ## for sections, ### for subsections).\n"
                "Format parameter and method names as bold using **name**.\n"
                "Use code blocks with language specification for all code examples.\n"
                "Keep the documentation concise but comprehensive."
            )
        )
        
        return chain.invoke({
            "module_name": module_name,
            "module_data": str(module_data)
        }).content
    
    def generate_api_docs(self, analysis: Dict[str, Any]) -> str:
        """Generate API documentation if applicable."""
        has_api = False
        for file_path, structure in analysis.get('project_structure', {}).items():
            if any(keyword in file_path.lower() for keyword in 
                   ['api', 'route', 'endpoint', 'controller']):
                has_api = True
                break
        
        if not has_api:
            return "No API endpoints detected in the project."
        
        chain = self._create_prompt_and_chain(
            system_message="""You are an API documentation specialist.
Focus on clear endpoint descriptions, request/response formats, and practical examples.
Include authentication, error handling, and rate limiting details.""",
            human_template=(
                "Generate detailed API documentation for:\n\n"
                "{analysis}\n\n"
                "# API Documentation\n\n"
                "## Overview\n"
                "- API purpose and scope\n"
                "- Base URL and versioning\n"
                "- Authentication methods\n\n"
                "## Authentication\n"
                "- Authentication methods\n"
                "- Token formats\n"
                "- Security considerations\n\n"
                "## Endpoints\n"
                "For each endpoint:\n"
                "- HTTP method and path\n"
                "- Request parameters\n"
                "- Request body format\n"
                "- Response format\n"
                "- Status codes\n"
                "- Error responses\n"
                "- Example requests and responses\n\n"
                "## Error Handling\n"
                "- Common error codes\n"
                "- Error response format\n"
                "- Troubleshooting guide\n\n"
                "## Rate Limiting\n"
                "- Limits and quotas\n"
                "- Rate limit headers\n"
                "- Handling rate limits\n\n"
                "Include curl examples and language-specific code samples.\n"
                "Format in Markdown with proper heading hierarchy."
            )
        )
        
        return chain.invoke({"analysis": str(analysis)}).content
    
    def generate_complete_documentation(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """Generate complete documentation for the project."""
        # Extract modules from project structure
        modules = self._extract_modules(analysis)
        
        # Generate project overview
        overview = self.generate_project_overview(analysis)
        
        # Generate module documentation
        module_docs = {}
        for module_name, module_data in modules.items():
            module_docs[module_name] = self.generate_module_docs(module_name, module_data)
            
        # Generate API documentation
        api_docs = self.generate_api_docs(analysis)
        
        return {
            'overview': overview,
            'modules': module_docs,
            'api': api_docs
        }
