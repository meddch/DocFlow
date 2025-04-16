# DocFlow

DocFlow is an AI-powered documentation generator that automatically analyzes your Python codebase and creates comprehensive documentation in Notion.

## Features

- Automatic code structure analysis for Python files
- Intelligent documentation generation using LangChain and GPT models
- Direct publishing to Notion
- Markdown-formatted documentation
- Hierarchical documentation structure
- Configurable options via `.env` file and command-line arguments

## Prerequisites

- Python 3.10 or higher
- A Notion account and API key
- An OpenAI API key

## Installation

1. Clone the repository:
```bash
git clone https://github.com/meddch/DocFlow.git
cd DocFlow
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your API keys:
```env
OPENAI_API_KEY=your_openai_api_key
NOTION_API_KEY=your_notion_api_key
NOTION_PARENT_PAGE_ID=your_notion_parent_page_id
MODEL_NAME=gpt-3.5-turbo  # Optional, defaults to gpt-3.5-turbo
```

## Configuration

DocFlow can be configured via a `.env` file in the project root and/or command-line arguments.

**`.env` file:**

Create a `.env` file with the following variables:

```env
OPENAI_API_KEY=your_openai_api_key          # Required: Your OpenAI API key
NOTION_API_KEY=your_notion_api_key          # Required: Your Notion integration token
NOTION_PARENT_PAGE_ID=your_notion_parent_page_id # Required: The ID of the Notion page to add documentation under
MODEL_NAME=gpt-4o                           # Optional: The OpenAI model to use (defaults to gpt-4o)
# Add other configuration variables as needed
```

**Command-line arguments:**

Command-line arguments can override `.env` settings. Run `python main.py --help` for a full list of options.

## Usage

To generate documentation for a specific project directory:

```bash
python main.py /path/to/your/project [OPTIONS]
```

If no path is provided, DocFlow will analyze the current working directory (`.`):

```bash
python main.py [OPTIONS]
```

Run `python main.py --help` for available options (Note: Command-line options are currently limited).

## Output

DocFlow analyzes the codebase and generates documentation pages in your specified Notion workspace. The default structure includes:

- **Parent Page (specified by `NOTION_PARENT_PAGE_ID`)**
  - **Project Overview:** High-level summary, structure, and key components.
  - **Modules/Packages:** Separate pages detailing functions, classes, and methods within each module.
    - *Sub-modules and nested structures are represented hierarchically.*
  - **API Documentation (Optional):** If applicable, details about public APIs.

The exact structure and content can vary based on the project's complexity and configuration.

## Contributing

Contributions are welcome! Here are some areas for improvement:

- **Testing:** Adding comprehensive unit and integration tests.
- **Language Support:** Implementing parsers for other languages (e.g., JavaScript, TypeScript).
- **Error Handling:** Enhancing robustness and providing more informative error messages.
- **Configuration:** Expanding command-line options for more granular control.
- **Notion Formatting:** Improving the conversion from Markdown to Notion blocks for better visual representation.

Please feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
