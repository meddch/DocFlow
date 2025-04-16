import os
from typing import Dict, Any
from config.settings import (
    OPENAI_API_KEY,
    NOTION_API_KEY,
    NOTION_PARENT_PAGE_ID,
    MODEL_NAME
)
from core.code_parser import CodeParser
from core.doc_generator import DocumentationGenerator
from notion.client import NotionPublisher

class DocuAgent:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.code_parser = CodeParser(project_path)
        self.doc_generator = DocumentationGenerator(MODEL_NAME)
        self.notion_publisher = NotionPublisher(NOTION_API_KEY, NOTION_PARENT_PAGE_ID)
    
    def generate_documentation(self) -> Dict[str, str]:
        """Generate documentation for the project."""
        print("Parsing project structure...")
        # Parse and analyze the code
        project_structure = self.code_parser.parse_project()
        print(f"Found {len(project_structure)} files to document")
        
        print("Generating documentation from analysis...")
        # Generate documentation
        documentation = self.doc_generator.generate_complete_documentation(
            {"project_structure": project_structure}
        )
        
        # Log documentation sections
        print(f"Generated documentation sections:")
        for section, content in documentation.items():
            if section == 'modules':
                print(f"- {section}: {len(content)} modules")
                for module_name in content.keys():
                    print(f"  - {module_name}")
            else:
                content_preview = content[:50] + "..." if content and len(content) > 50 else content
                print(f"- {section}: {content_preview}")
        
        return documentation
    
    def publish_to_notion(self, documentation: Dict[str, str]) -> Dict[str, str]:
        """Publish documentation to Notion."""
        return self.notion_publisher.create_documentation_structure(documentation)

def main():
    # Check for required environment variables
    required_vars = ['OPENAI_API_KEY', 'NOTION_API_KEY', 'NOTION_PARENT_PAGE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"- {var}")
        return
    
    # Get project path from command line or use current directory
    import sys
    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    print(f"Analyzing project at: {project_path}")
    
    try:
        # Initialize DocuAgent
        print("Initializing DocuAgent...")
        agent = DocuAgent(project_path)
        
        # Generate documentation
        print("Generating documentation...")
        documentation = agent.generate_documentation()
        
        # Publish to Notion
        print("Publishing to Notion...")
        page_ids = agent.publish_to_notion(documentation)
        
        print("\nDocumentation published successfully!")
        print(f"Main documentation page: https://notion.so/{page_ids['main'].replace('-', '')}")
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main()
