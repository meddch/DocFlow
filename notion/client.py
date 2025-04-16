from typing import Dict, Any, List
from notion_client import Client, APIResponseError
import re

class NotionPublisher:
    def __init__(self, token: str, parent_page_id: str):
        self.token = token
        self.parent_page_id = self._extract_page_id(parent_page_id)
        self.client = Client(auth=token)
        # Test connection on initialization
        self._test_connection()
    
    def _extract_page_id(self, page_id: str) -> str:
        """Extract and format the page ID from either a URL or direct ID."""
        # Remove any spaces and hyphens
        clean_id = page_id.replace('-', '').replace(' ', '')
        
        # If it's a URL, extract the ID portion
        if 'notion.so' in page_id:
            # Extract the last portion of the URL that contains the ID
            matches = re.search(r'([a-f0-9]{32})', page_id)
            if matches:
                clean_id = matches.group(1)
        
        # Format ID with hyphens
        if len(clean_id) == 32:
            return f"{clean_id[:8]}-{clean_id[8:12]}-{clean_id[12:16]}-{clean_id[16:20]}-{clean_id[20:32]}"
        return clean_id
    
    def _test_connection(self) -> None:
        """Test the connection to Notion and access to the parent page."""
        try:
            # First test the token by getting user bot info
            self.client.users.me()
        except APIResponseError as e:
            setup_instructions = """
Please set up your Notion integration:
1. Go to https://www.notion.so/my-integrations
2. Click "New integration"
3. Name it "DocFlow"
4. Select your workspace
5. Copy the new integration token
6. Update your .env file with the new token
"""
            raise ValueError(f"Invalid Notion API token. {setup_instructions}")
        
        try:
            # Test access to the parent page
            self.client.pages.retrieve(self.parent_page_id)
        except APIResponseError as e:
            page_instructions = f"""
Could not access the Notion page. Please:
1. Go to your Notion page
2. Click 'Share' in the top right
3. Click 'Add people, emails, groups, or integrations'
4. Search for your integration name (DocFlow)
5. Click 'Invite'

Your page ID is: {self.parent_page_id}
If this ID looks incorrect, please get the correct ID from your Notion page URL.
"""
            raise ValueError(page_instructions)
    
    def _validate_page_access(self, page_id: str) -> bool:
        """Validate that the integration has access to the page."""
        try:
            self.client.pages.retrieve(page_id)
            return True
        except Exception as e:
            print(f"Error accessing page {page_id}. Please make sure:")
            print("1. The page ID is correct")
            print("2. The integration has been added to the page")
            print("3. The page exists and is accessible")
            print(f"Error details: {str(e)}")
            return False
    
    def _clear_page_content(self, page_id: str) -> None:
        """Clear all existing content from a Notion page without deleting the page."""
        try:
            # Don't update the page title, just clear the blocks
            # Retrieve the page first to preserve its title and other properties
            # We skip the title update entirely since we want to keep the existing title
            
            # Archive existing blocks instead of deleting them
            blocks = self.client.blocks.children.list(page_id)
            
            # Clear blocks by updating them to empty content
            for block in blocks["results"]:
                try:
                    if block.get("type") == "child_page":
                        continue  # Skip child pages to preserve structure
                    self.client.blocks.update(
                        block_id=block["id"],
                        archived=True  # Archive instead of delete
                    )
                except APIResponseError as e:
                    if "rate_limited" in str(e):
                        import time
                        time.sleep(0.5)  # Add rate limit handling
                    else:
                        print(f"Warning: Could not clear block {block['id']}: {str(e)}")
        except APIResponseError as e:
            print(f"Warning: Could not clear page content: {str(e)}")
    
    def _delete_child_pages(self, parent_page_id: str) -> None:
        """Delete all child pages of the given parent page."""
        try:
            # Get all blocks in the parent page
            blocks = self.client.blocks.children.list(parent_page_id)
            
            # Find and delete child pages
            for block in blocks["results"]:
                if block.get("type") == "child_page":
                    try:
                        print(f"  - Deleting child page: {block.get('child_page', {}).get('title', 'Untitled')}")
                        # Archive/delete the child page
                        self.client.blocks.delete(block_id=block["id"])
                    except APIResponseError as e:
                        if "rate_limited" in str(e):
                            import time
                            time.sleep(0.5)  # Add rate limit handling
                            # Try once more
                            self.client.blocks.delete(block_id=block["id"])
                        else:
                            print(f"Warning: Could not delete child page {block['id']}: {str(e)}")
            
            print("Cleaned up old child pages.")
        except APIResponseError as e:
            print(f"Warning: Could not list or delete child pages: {str(e)}")
    
    def create_page(self, title: str, content: str = "", icon_emoji: str = "📚") -> str:
        """Create a new page in Notion."""
        # Validate access to parent page first
        if not self._validate_page_access(self.parent_page_id):
            raise ValueError(
                "Cannot access the parent page. Please make sure you have:\n"
                "1. Added your integration to the page in Notion\n"
                "2. Used the correct page ID from the Notion URL\n"
                "3. The page is accessible to your integration"
            )
            
        # Create the page
        page = self.client.pages.create(
            parent={"page_id": self.parent_page_id},
            icon={
                "type": "emoji",
                "emoji": icon_emoji
            },
            properties={
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            }
        )
        
        # Ensure the page title is properly set by explicitly updating it
        self.client.pages.update(
            page_id=page["id"],
            properties={
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            }
        )
        
        # Clear any existing content from the page before adding new content
        self._clear_page_content(page["id"])
        
        if content:
            # Process the content to remove any duplicate links to itself or other modules
            processed_content = self._remove_duplicate_links(content)
            self.append_content_to_page(page["id"], processed_content)
        
        return page["id"]
        
    def _remove_duplicate_links(self, content: str) -> str:
        """Remove duplicate links to pages that might appear in the content."""
        # Remove duplicate module links
        lines = content.split('\n')
        seen_links = set()
        filtered_lines = []
        
        for line in lines:
            # Check if line is a Notion link
            if 'https://www.notion.so/' in line and line.strip().startswith('[Module:'):
                link_url = re.search(r'https://www.notion.so/[a-zA-Z0-9]+', line)
                if link_url:
                    link_id = link_url.group(0)
                    if link_id in seen_links:
                        continue  # Skip duplicate link
                    seen_links.add(link_id)
            
            # Also remove links to "Project Overview" if they're in an overview page
            if '1. Project Overview' in line and '[1. Project Overview]' in line:
                continue
                
            filtered_lines.append(line)
            
        return '\n'.join(filtered_lines)
    
    def append_content_to_page(self, page_id: str, content: str) -> None:
        """Append markdown content to a page."""
        # Convert markdown to Notion blocks
        blocks = self._markdown_to_blocks(content)
        
        # Split blocks into chunks if needed (Notion API has size limits)
        for chunk in self._chunk_blocks(blocks, 100):
            self.client.blocks.children.append(
                block_id=page_id,
                children=chunk
            )
    
    def _markdown_to_blocks(self, content: str) -> List[Dict[str, Any]]:
        """Convert markdown content to Notion blocks."""
        blocks = []
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # Headers - fix for handling standalone # characters
            if line == '#':
                # Skip lone hashtags, they cause issues in Notion
                i += 1
                continue
            elif line.startswith('# '):
                blocks.append({
                    "heading_1": {"rich_text": [{"text": {"content": line[2:]}}]}
                })
            elif line.startswith('## '):
                blocks.append({
                    "heading_2": {"rich_text": [{"text": {"content": line[3:]}}]}
                })
            elif line.startswith('### '):
                blocks.append({
                    "heading_3": {"rich_text": [{"text": {"content": line[4:]}}]}
                })
            
            # Lists with rich text handling for bold
            elif line.startswith('- '):
                content = line[2:]
                rich_text_blocks = self._parse_rich_text(content)
                blocks.append({
                    "bulleted_list_item": {"rich_text": rich_text_blocks}
                })
            elif line.startswith('1. '):
                content = line[3:]
                rich_text_blocks = self._parse_rich_text(content)
                blocks.append({
                    "numbered_list_item": {"rich_text": rich_text_blocks}
                })
            
            # Code blocks
            elif line.startswith('```'):
                code_lines = []
                language = "plain text"  # Default language
                
                # Check if language is specified after backticks
                if len(line) > 3:
                    lang = line[3:].strip().lower()
                    # Map common language names to Notion's supported languages
                    lang_map = {
                        "js": "javascript",
                        "py": "python",
                        "ts": "typescript",
                        "shell": "bash",
                        "sh": "bash",
                        "yml": "yaml",
                        "text": "plain text"
                    }
                    language = lang_map.get(lang, lang)
                    # Validate if language is supported by Notion
                    supported_languages = {
                        "abap", "agda", "arduino", "assembly", "bash", "basic", "bnf", "c", "c#", "c++",
                        "clojure", "coffeescript", "coq", "css", "dart", "dhall", "diff", "docker",
                        "ebnf", "elixir", "elm", "erlang", "f#", "flow", "fortran", "gherkin", "glsl",
                        "go", "graphql", "groovy", "haskell", "hcl", "html", "idris", "java", "javascript",
                        "json", "julia", "kotlin", "latex", "less", "lisp", "livescript", "llvm ir", "lua",
                        "makefile", "markdown", "markup", "matlab", "mathematica", "mermaid", "nix",
                        "notion formula", "objective-c", "ocaml", "pascal", "perl", "php", "plain text",
                        "powershell", "prolog", "protobuf", "purescript", "python", "r", "racket",
                        "reason", "ruby", "rust", "sass", "scala", "scheme", "scss", "shell", "smalltalk",
                        "solidity", "sql", "swift", "toml", "typescript", "vb.net", "verilog", "vhdl",
                        "visual basic", "webassembly", "xml", "yaml"
                    }
                    if language not in supported_languages:
                        language = "plain text"
                
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                if code_lines:
                    blocks.append({
                        "code": {
                            "rich_text": [{"text": {"content": '\n'.join(code_lines)}}],
                            "language": language
                        }
                    })
            
            # Regular paragraph with rich text handling for bold
            else:
                rich_text_blocks = self._parse_rich_text(line)
                blocks.append({
                    "paragraph": {"rich_text": rich_text_blocks}
                })
            
            i += 1
        
        return blocks
    
    def _parse_rich_text(self, text: str) -> List[Dict[str, Any]]:
        """Parse text for rich text formatting including bold, italic, and code."""
        result = []
        
        # Process text in order of: code, bold, italic
        # Process bold text directly - simpler and more reliable approach
        bold_pattern = r'\*\*(.*?)\*\*'
        
        # Split by bold markers
        parts = []
        current_idx = 0
        
        import re
        for match in re.finditer(bold_pattern, text):
            if current_idx < match.start():
                # Add plain text before the match
                parts.append((text[current_idx:match.start()], False))
            
            # Add the bold text (without the ** markers)
            parts.append((match.group(1), True))
            current_idx = match.end()
            
        # Add remaining text after last match
        if current_idx < len(text):
            parts.append((text[current_idx:], False))
        
        # If no bold patterns were found, return original text
        if not parts:
            return [{"text": {"content": text}}]
            
        # Create rich text blocks
        for part_text, is_bold in parts:
            block = {"text": {"content": part_text}}
            if is_bold:
                block["annotations"] = {"bold": True}
            result.append(block)
            
        return result
    
    def _chunk_blocks(self, blocks: List[Dict[str, Any]], chunk_size: int) -> List[List[Dict[str, Any]]]:
        """Split blocks into smaller chunks to respect Notion API limits."""
        return [blocks[i:i + chunk_size] for i in range(0, len(blocks), chunk_size)]
    
    def create_documentation_structure(self, documentation: Dict[str, str]) -> Dict[str, str]:
        """Create a complete documentation structure in Notion with proper cross-linking."""
        # Track all created page IDs to avoid duplication
        page_ids = {}
        created_modules = set()
        
        # Step 1: Clean the parent page and prepare it as our main documentation page
        try:
            # First delete all existing child pages to avoid duplicates
            print("Cleaning up existing child pages...")
            self._delete_child_pages(self.parent_page_id)
            
            # Then clear the content of the main page itself
            self._clear_page_content(self.parent_page_id)
            main_page_id = self.parent_page_id
            
            # Update the main page title
            self.client.pages.update(
                page_id=main_page_id,
                properties={
                    "title": {
                        "title": [
                            {
                                "text": {
                                    "content": "DocFlow Documentation"
                                }
                            }
                        ]
                    }
                },
                icon={
                    "type": "emoji",
                    "emoji": "📚"
                }
            )
            page_ids["main"] = main_page_id
        except APIResponseError as e:
            print(f"Warning: Could not prepare main page: {str(e)}")
            return {}
            
        # Step 2: Create all the individual pages first so we can cross-link them
        print("Creating documentation pages...")
        
        # 2.1 Create Project Overview page
        overview_page_id = None
        if 'overview' in documentation and documentation['overview']:
            try:
                overview_page_id = self.create_page(
                    title="1. Project Overview",
                    content=documentation['overview'],
                    icon_emoji="🔍"
                )
                page_ids["overview"] = overview_page_id
                print(f"  - Created Project Overview page")
            except APIResponseError as e:
                print(f"Warning: Could not create Project Overview: {str(e)}")
                
        # 2.2 Create Module pages with IDs for cross-referencing
        module_pages = {}
        if 'modules' in documentation and documentation['modules']:
            print(f"Creating module documentation pages...")
            for module_name, module_content in documentation['modules'].items():
                # Skip empty content or already created modules
                if not module_content or module_name in created_modules:
                    continue
                    
                try:
                    module_page_id = self.create_page(
                        title=f"Module: {module_name}",
                        content=module_content,
                        icon_emoji="📦"
                    )
                    page_ids[f"module_{module_name}"] = module_page_id
                    module_pages[module_name] = {
                        "id": module_page_id,
                        "title": f"Module: {module_name}"
                    }
                    created_modules.add(module_name)
                    print(f"  - Created {module_name} module page")
                except APIResponseError as e:
                    print(f"Warning: Could not create module page for {module_name}: {str(e)}")
        
        # 2.3 Create API Documentation page if applicable
        api_page_id = None
        if 'api' in documentation and documentation['api'] and documentation['api'] != "No API endpoints detected in the project.":
            try:
                api_page_id = self.create_page(
                    title="2. API Documentation",
                    content=documentation['api'],
                    icon_emoji="🔌"
                )
                page_ids["api"] = api_page_id
                print(f"  - Created API Documentation page")
            except APIResponseError as e:
                print(f"Warning: Could not create API Documentation: {str(e)}")
        
        # Step 3: Now create an integrated main page with cross-references
        print("Creating integrated main documentation page...")
        
        # Function to create proper Notion URLs
        def create_notion_url(page_id):
            # Format: https://www.notion.so/[workspace_name]/[page_title]-[page_id_without_hyphens]
            # Since we don't know the workspace name, we'll use a more reliable direct link format
            clean_id = page_id.replace('-', '')
            return f"https://www.notion.so/{clean_id}"
        
        # 3.1 Create blocks for the main page header
        main_blocks = [
            {
                "heading_1": {
                    "rich_text": [{
                        "text": {"content": "DocFlow Project Documentation"}
                    }]
                }
            },
            {
                "paragraph": {
                    "rich_text": [{
                        "text": {"content": "Complete documentation for the DocFlow project - an automated documentation generator and publisher."}
                    }]
                }
            }
        ]
        
        # 3.2 Create a table of contents
        main_blocks.append({
            "heading_2": {
                "rich_text": [{
                    "text": {"content": "Table of Contents"}
                }]
            }
        })
        
        # Add overview to TOC
        if overview_page_id:
            main_blocks.append({
                "bulleted_list_item": {
                    "rich_text": [
                        {
                            "text": {
                                "content": "Project Overview",
                                "link": {"url": create_notion_url(overview_page_id)}
                            }
                        }
                    ]
                }
            })
        
        # Add API docs to TOC if exists
        if api_page_id:
            main_blocks.append({
                "bulleted_list_item": {
                    "rich_text": [
                        {
                            "text": {
                                "content": "API Documentation",
                                "link": {"url": create_notion_url(api_page_id)}
                            }
                        }
                    ]
                }
            })
        
        # Add modules section to TOC
        if module_pages:
            main_blocks.append({
                "heading_3": {
                    "rich_text": [{
                        "text": {"content": "Module Documentation"}
                    }]
                }
            })
            
            # Add each module as a bulleted list item (only once per module)
            for module_name, module_info in module_pages.items():
                main_blocks.append({
                    "bulleted_list_item": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": module_name,
                                    "link": {"url": create_notion_url(module_info['id'])}
                                }
                            }
                        ]
                    }
                })
        
        # 3.3 Add project architecture overview
        main_blocks.append({
            "heading_2": {
                "rich_text": [{
                    "text": {"content": "Project Architecture"}
                }]
            }
        })
        
        # Add architecture diagram explanation
        main_blocks.append({
            "paragraph": {
                "rich_text": [{
                    "text": {"content": "DocFlow is organized into the following key components:"}
                }]
            }
        })
        
        # Create a simplified component description
        components = [
            {
                "name": "Core",
                "description": "Contains the core functionality including code parsing and documentation generation."
            },
            {
                "name": "Notion",
                "description": "Handles publishing documentation to Notion pages and formatting content appropriately."
            },
            {
                "name": "Config",
                "description": "Manages configuration settings and environment variables."
            }
        ]
        
        # Add component descriptions
        for component in components:
            module_id = page_ids.get(f"module_{component['name'].lower()}")
            name_text = component["name"]
            
            # If we have a page ID for this module, make it a link
            rich_text = []
            if module_id:
                rich_text.append({
                    "text": {
                        "content": name_text,
                        "link": {"url": create_notion_url(module_id)}
                    },
                    "annotations": {"bold": True}
                })
            else:
                rich_text.append({
                    "text": {"content": name_text},
                    "annotations": {"bold": True}
                })
                
            # Add the description
            rich_text.append({
                "text": {"content": f": {component['description']}"}
            })
            
            # Create the list item
            main_blocks.append({
                "bulleted_list_item": {
                    "rich_text": rich_text
                }
            })
        
        # 3.4 Add data flow description
        main_blocks.append({
            "heading_2": {
                "rich_text": [{
                    "text": {"content": "Data Flow"}
                }]
            }
        })
        
        main_blocks.append({
            "paragraph": {
                "rich_text": [{
                    "text": {"content": "The DocFlow process follows these steps:"}
                }]
            }
        })
        
        # Describe the data flow as numbered steps
        workflow_steps = [
            "Code Analysis: Project files are parsed to extract structure, classes, functions, and docstrings.",
            "Documentation Generation: The extracted code structure is analyzed to generate comprehensive documentation.",
            "Notion Publishing: Generated documentation is formatted and published to interconnected Notion pages."
        ]
        
        for i, step in enumerate(workflow_steps):
            main_blocks.append({
                "numbered_list_item": {
                    "rich_text": [{
                        "text": {"content": step}
                    }]
                }
            })
        
        # 3.5 Add quick start guide
        main_blocks.append({
            "heading_2": {
                "rich_text": [{
                    "text": {"content": "Quick Start Guide"}
                }]
            }
        })
        
        # Add installation instructions
        main_blocks.append({
            "paragraph": {
                "rich_text": [{
                    "text": {"content": "To get started with DocFlow:"}
                }]
            }
        })
        
        quick_start = [
            "Clone the repository",
            "Install dependencies with `pip install -r requirements.txt`",
            "Set up environment variables (OPENAI_API_KEY, NOTION_API_KEY, NOTION_PARENT_PAGE_ID)",
            "Run with `python main.py <project_path>`"
        ]
        
        for step in quick_start:
            main_blocks.append({
                "bulleted_list_item": {
                    "rich_text": self._parse_rich_text(step)
                }
            })
        
        # Add all blocks to the main page
        for i in range(0, len(main_blocks), 100):  # Notion has a limit on blocks per request
            chunk = main_blocks[i:i+100]
            self.client.blocks.children.append(block_id=main_page_id, children=chunk)
        
        print(f"Documentation structure created successfully!")
        return page_ids
