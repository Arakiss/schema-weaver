import os
import subprocess
import requests
import json
import re
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm
from rich.text import Text

console = Console()

def get_diff():
    return subprocess.check_output(['git', 'diff', '--staged']).decode('utf-8')

def get_changed_files():
    return subprocess.check_output(['git', 'diff', '--staged', '--name-only']).decode('utf-8').splitlines()

def generate_prompt(diff, changed_files):
    files_summary = ", ".join(changed_files[:3])
    if len(changed_files) > 3:
        files_summary += f" and {len(changed_files) - 3} more"

    return f"""Generate a structured commit message for the following git diff, following the semantic commit and gitemoji conventions:

Files changed: {files_summary}

```
{diff}
```

Requirements:
1. Title: Maximum 50 characters, starting with an appropriate gitemoji, followed by the semantic commit type and a brief description.
2. Body: Organize changes into categories. Each category should have an appropriate emoji and 2-3 bullet points summarizing key changes.
3. Summary: A brief sentence summarizing the overall impact of the changes.

Respond in the following JSON format:
{{
    "title": "Your commit message title here",
    "body": {{
        "Category1": {{
            "emoji": "🔧",
            "changes": [
                "First change in category 1",
                "Second change in category 1"
            ]
        }},
        "Category2": {{
            "emoji": "✨",
            "changes": [
                "First change in category 2",
                "Second change in category 2"
            ]
        }}
    }},
    "summary": "A brief summary of the overall changes and their impact."
}}

Ensure that each category and change is relevant and specific to the diff provided. Use appropriate and varied emojis for different categories.
"""

def generate_commit_message(prompt):
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    data = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}]
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    response.raise_for_status()
    
    content = response.json()['choices'][0]['message']['content']
    content = re.search(r'\{.*\}', content, re.DOTALL).group()
    return content

def format_commit_message(commit_data):
    title = commit_data['title'][:50]
    body = commit_data['body']
    summary = commit_data['summary']

    formatted_message = f"{title}\n\n"
    for category, content in body.items():
        formatted_message += f"{content['emoji']} {category}:\n"
        for change in content['changes']:
            formatted_message += f"- {change}\n"
        formatted_message += "\n"
    
    formatted_message += f"{summary}\n"

    return formatted_message

def main():
    console.print("\n[bold magenta]🔮 Analyzing your changes...[/bold magenta]")
    
    changed_files = get_changed_files()
    if not changed_files:
        console.print("\n[bold red]🌚 No changes detected in the staging area.[/bold red]")
        return

    console.print("\n[bold blue]📜 Changes detected in the following files:[/bold blue]")
    for file in changed_files:
        console.print(f"  - [cyan]{file}[/cyan]")

    diff = get_diff()
    
    with console.status("[bold green]Generating commit message using GPT-4O...[/bold green]"):
        try:
            commit_message_json = generate_commit_message(generate_prompt(diff, changed_files))
            commit_data = json.loads(commit_message_json)
            formatted_message = format_commit_message(commit_data)
        except json.JSONDecodeError:
            console.print("[bold red]Error: Failed to parse the generated commit message as JSON.[/bold red]")
            return
        except KeyError as e:
            console.print(f"[bold red]Error: Missing key in generated commit message: {e}[/bold red]")
            return
        except Exception as e:
            console.print(f"[bold red]Error: Failed to generate commit message. {str(e)}[/bold red]")
            return

    console.print("\n[bold green]📝 Generated Commit Message:[/bold green]")
    console.print(Panel(Text(formatted_message), expand=False, border_style="green"))

    git_command = f'git commit -m "{commit_data["title"]}" -m "{formatted_message}"'
    
    console.print("\n[bold yellow]🚀 Generated Git Command:[/bold yellow]")
    console.print(Panel(Syntax(git_command, "bash", theme="monokai", line_numbers=True)))

    if Confirm.ask("Do you want to execute this git command?"):
        try:
            subprocess.run(git_command, shell=True, check=True)
            console.print("\n[bold green]✨ Commit executed successfully![/bold green]")
        except subprocess.CalledProcessError:
            console.print("\n[bold red]❌ Failed to execute the commit command. Please check the generated message and try manually.[/bold red]")
    else:
        console.print("\n[bold blue]👍 Commit command not executed. You can use it manually if needed.[/bold blue]")

    console.print("\n[bold magenta]✨ Process completed.[/bold magenta]")

if __name__ == "__main__":
    main()