import os
import subprocess
import requests
import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_diff():
    return subprocess.check_output(['git', 'diff', '--staged']).decode('utf-8')

def get_changed_files():
    return subprocess.check_output(['git', 'diff', '--staged', '--name-only']).decode('utf-8').splitlines()

def generate_prompt(diff):
    return f"""Generate a concise and informative commit message for the following git diff, following the semantic commit and gitemoji conventions:

```
{diff}
```

Requirements:
1. Title: Maximum 50 characters, starting with an appropriate gitemoji, followed by the semantic commit type and a brief description.
2. Body: 2-3 short bullet points summarizing the key changes.

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

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        response_json = response.json()
        
        if 'choices' not in response_json or len(response_json['choices']) == 0:
            logger.error(f"Unexpected API response structure: {response_json}")
            raise ValueError("API response does not contain expected 'choices' field")
        
        content = response_json['choices'][0]['message']['content']
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from API response content: {content}")
            raise ValueError(f"API returned non-JSON content: {content}") from e
        
    except requests.RequestException as e:
        logger.error(f"Error making request to OpenAI API: {e}")
        raise
    except KeyError as e:
        logger.error(f"Error accessing key in response: {e}")
        raise

def execute_git_commit(title, body):
    git_command = f'git commit -m "{title}" -m "{chr(10).join(body)}"'
    try:
        subprocess.run(git_command, shell=True, check=True)
        logger.info("✨ Commit executed successfully!")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error executing commit command: {e}")
        raise

def main():
    logger.info("🔮 Analyzing your changes...")
    
    changed_files = get_changed_files()
    if not changed_files:
        logger.info("🌚 No changes detected in the staging area.")
        return

    logger.info("📜 Changes detected in the following files:")
    for file in changed_files:
        logger.info(f"  - {file}")

    diff = get_diff()
    
    logger.info("🤖 Generating commit message using GPT-4...")
    try:
        commit_message = generate_commit_message(generate_prompt(diff))
        title = commit_message['title']
        body = commit_message['body']
    except Exception as e:
        logger.error(f"Error: Could not generate commit message. {str(e)}")
        return

    logger.info("\n📝 Generated Commit Message:")
    logger.info(f"Title: {title}")
    logger.info("Body:")
    for line in body:
        logger.info(f"  - {line}")

    user_input = input("\n🚀 Do you want to execute the git commit command with this message? (y/n): ").lower()
    if user_input == 'y':
        try:
            execute_git_commit(title, body)
        except Exception as e:
            logger.error(f"Could not execute commit command: {e}")
    else:
        logger.info("👍 Commit command not executed. You can use it manually if needed.")

    logger.info("✨ Process completed.")

if __name__ == "__main__":
    main()