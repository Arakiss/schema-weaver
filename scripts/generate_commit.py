import os
import subprocess
import requests
import json
import re
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm

console = Console()

def get_diff():
    return subprocess.check_output(['git', 'diff', '--staged']).decode('utf-8')

def get_changed_files():
    return subprocess.check_output(['git', 'diff', '--staged', '--name-only']).decode('utf-8').splitlines()

def generate_prompt(diff, changed_files):
    files_summary = ", ".join(changed_files[:3])
    if len(changed_files) > 3:
        files_summary += f" and {len(changed_files) - 3} more"

    return f"""Generate a concise and informative commit message for the following git diff, following the semantic commit and gitemoji conventions:

Files changed: {files_summary}

```
{diff}
```

Requirements:
1. Title: Maximum 50 characters, starting with an appropriate gitemoji, followed by the semantic commit type and a brief description.
2. Body: 2-3 short bullet points summarizing the key changes. Each point should be max 72 characters.

Focus on the most significant changes and their impact. Be specific but concise.

Respond in the following JSON format:
{{
    "title": "Your commit message title here",
    "body": [
        "First key point",
        "Second key point",
        "Third key point (if necessary)"
    ]
}}
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

def format_commit_message(title, body):
    formatted_title = title[:50]  # Ensure title is not longer than 50 chars
    formatted_body = [line[:72] for line in body]  # Ensure each line is not longer than 72 chars
    return formatted_title, formatted_body

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
            commit_message = json.loads(commit_message_json)
            title, body = format_commit_message(commit_message['title'], commit_message['body'])
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
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", title="Title"))
    console.print(Panel("\n".join([f"• {line}" for line in body]), title="Body"))

    git_command = f'git commit -m "{title}" -m "{chr(10).join(body)}"'
    
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