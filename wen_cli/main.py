import os
import subprocess
import json
from dotenv import load_dotenv
from openai import OpenAI
from ollama import Client as OllamaClient
from colorama import init, Fore, Style

# Initialize colorama for cross-platform color support
init()

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ollama_client = OllamaClient()

# Enhanced conversation history with context
conversation_history = [
    {
        "role": "system",
        "content": (
            "You are wen, an intelligent AI agent that responds in JSON format. You can help with shell commands, complex tasks, and general questions. "
            "ALWAYS respond with valid JSON in this exact format:\n"
            "{\n"
            '  "response": "Your text response to the user",\n'
            '  "actions": [\n'
            '    {\n'
            '      "type": "command",\n'
            '      "command": "shell command to execute",\n'
            '      "description": "what this command does",\n'
            '      "safe": true/false\n'
            '    },\n'
            '    {\n'
            '      "type": "task",\n'
            '      "description": "multi-step task description",\n'
            '      "steps": [\n'
            '        {\n'
            '          "command": "step 1 command",\n'
            '          "description": "step 1 description"\n'
            '        }\n'
            '      ]\n'
            '    },\n'
            '    {\n'
            '      "type": "info",\n'
            '      "message": "informational message"\n'
            '    }\n'
            '  ],\n'
            '  "thinking": "your reasoning process",\n'
            '  "next_action": "what you plan to do next"\n'
            "}\n\n"
            "Rules:\n"
            "- response: Always provide a helpful text response\n"
            "- actions: Array of actions to take (commands, tasks, info)\n"
            "- thinking: Explain your reasoning\n"
            "- next_action: What you plan to do next\n"
            "- For commands, always specify if they're safe to auto-execute\n"
            "- For complex tasks, break them into steps\n"
            "- Be intelligent and proactive in solving problems"
        )
    }
]

def run_command(command):
    """Execute a shell command and return results"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
            "returncode": result.returncode
        }
    except Exception as e:
        return {"success": False, "output": "", "error": str(e), "returncode": -1}

def execute_multi_step_task(user_input):
    """Let AI plan and execute multi-step tasks dynamically"""
    # Ask AI to plan the steps for complex tasks
    plan_response = get_ai_task_plan(user_input)
    
    # Check if AI suggests this needs multiple steps
    if "MULTI_STEP:" in plan_response:
        return execute_ai_planned_steps(user_input, plan_response)
    else:
        # Single command task
        return plan_response

def get_ai_task_plan(user_input):
    """Get AI to plan the steps for a task"""
    plan_messages = [
        {
            "role": "system",
            "content": (
                "You are a task planner. Analyze the user request and determine if it needs multiple steps. "
                "If it's a simple command, respond with just the command. "
                "If it needs multiple steps (like finding files, searching directories, then opening), respond with 'MULTI_STEP:' followed by a JSON array of commands. "
                "Use {result} placeholder to use output from previous step. "
                "Example: 'find morpheus project' → 'MULTI_STEP: [\"find ~/Desktop -name \\\"*morpheus*\\\" -type d\", \"open -a \\\"Visual Studio Code\\\" \\\"{result}\\\"\"]' "
                "Example: 'setup python project' → 'MULTI_STEP: [\"python3 -m venv venv\", \"source venv/bin/activate\", \"pip install -r requirements.txt\"]' "
                "Example: 'ls files' → 'ls'"
            )
        },
        {
            "role": "user",
            "content": f"Plan steps for: {user_input}"
        }
    ]
    
    # Check which provider to use
    provider = os.getenv("WEN_PROVIDER", "openai")
    
    if provider == "ollama":
        try:
            response = ollama_client.chat(
                model="mistral",
                messages=plan_messages,
                options={"num_predict": 200, "temperature": 0.1}
            )
            return response['message']['content'].strip()
        except Exception as e:
            print(f"{Fore.RED}Ollama error: {e}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Falling back to OpenAI...{Style.RESET_ALL}")
            provider = "openai"
    
    if provider == "openai":
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=plan_messages,
            max_tokens=200,
            temperature=0.1,
            timeout=10
        )
        return response.choices[0].message.content.strip()

def execute_ai_planned_steps(user_input, plan_response):
    """Execute the steps planned by AI"""
    try:
        # Extract commands from the plan
        commands_json = plan_response.replace("MULTI_STEP:", "").strip()
        import json
        commands = json.loads(commands_json)
        
        print(f"{Fore.CYAN}Executing {len(commands)} steps...{Style.RESET_ALL}")
        
        # Execute each command and collect results
        results = []
        for i, command in enumerate(commands):
            print(f"{Fore.BLUE}Step {i+1}: {command}{Style.RESET_ALL}")
            
            # Replace placeholders with actual results
            if "{result}" in command and results:
                last_result = results[-1]["output"] if results[-1]["success"] else ""
                command = command.replace("{result}", last_result)
                print(f"{Fore.YELLOW}Replaced with: {last_result}{Style.RESET_ALL}")
            
            result = run_command(command)
            results.append(result)
            
            if result["success"]:
                if result["output"]:
                    print(f"{Fore.GREEN}✓ {result['output']}{Style.RESET_ALL}")
            else:
                if result["error"]:
                    print(f"{Fore.RED}✗ {result['error']}{Style.RESET_ALL}")
        
        # Return the final result or success message
        if results and results[-1]["success"]:
            return f"Task completed successfully. Final output: {results[-1]['output']}"
        else:
            return "Task completed with some errors."
            
    except Exception as e:
        print(f"{Fore.RED}Error executing planned steps: {e}{Style.RESET_ALL}")
        return get_ai_response(user_input, conversation_history)



def get_ai_response(user_input, history):
    """Get response from AI with conversation history"""
    messages = history + [{"role": "user", "content": user_input}]
    
    # Check which provider to use
    provider = os.getenv("WEN_PROVIDER", "openai")
    
    if provider == "ollama":
        try:
            response = ollama_client.chat(
                model="mistral",
                messages=messages,
                options={"num_predict": 1000, "temperature": 0.7}
            )
            return response['message']['content'].strip()
        except Exception as e:
            print(f"{Fore.RED}Ollama error: {e}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Falling back to OpenAI...{Style.RESET_ALL}")
            # Fallback to OpenAI
            provider = "openai"
    
    if provider == "openai":
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=1000,  # Allow longer responses for JSON
            temperature=0.7,  # More creative and conversational
            timeout=15
        )
        return response.choices[0].message.content.strip()

def parse_ai_response(response_text):
    """Parse AI response and extract JSON structure"""
    try:
        # Try to extract JSON from the response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start != -1 and json_end != 0:
            json_str = response_text[json_start:json_end]
            return json.loads(json_str)
        else:
            # Fallback: create a simple response structure
            return {
                "response": response_text,
                "actions": [],
                "thinking": "Could not parse structured response",
                "next_action": "Continue conversation"
            }
    except json.JSONDecodeError as e:
        print(f"{Fore.RED}JSON parsing error: {e}{Style.RESET_ALL}")
        # Fallback: create a simple response structure
        return {
            "response": response_text,
            "actions": [],
            "thinking": f"JSON parsing failed: {e}",
            "next_action": "Continue conversation"
        }

def execute_actions(actions, conversation_history):
    """Execute the actions specified in the AI response"""
    results = []
    
    for action in actions:
        action_type = action.get("type", "")
        
        if action_type == "command":
            command = action.get("command", "")
            description = action.get("description", "")
            safe = action.get("safe", False)
            
            print(f"{Fore.CYAN}action: {description}{Style.RESET_ALL}")
            
            if safe:
                print(f"{Fore.GREEN}running: {command}{Style.RESET_ALL}")
                result = run_command(command)
                
                if result["success"]:
                    if result["output"]:
                        print(f"{Fore.GREEN}{result['output']}{Style.RESET_ALL}")
                else:
                    if result["error"]:
                        print(f"{Fore.RED}error: {result['error']}{Style.RESET_ALL}")
                
                results.append({
                    "type": "command",
                    "command": command,
                    "success": result["success"],
                    "output": result["output"],
                    "error": result["error"]
                })
            else:
                confirm = input(f"{Fore.RED}Run this command? (y/n): {Style.RESET_ALL}").lower()
                if confirm == 'y':
                    print(f"{Fore.GREEN}running: {command}{Style.RESET_ALL}")
                    result = run_command(command)
                    
                    if result["success"]:
                        if result["output"]:
                            print(f"{Fore.GREEN}{result['output']}{Style.RESET_ALL}")
                    else:
                        if result["error"]:
                            print(f"{Fore.RED}error: {result['error']}{Style.RESET_ALL}")
                    
                    results.append({
                        "type": "command",
                        "command": command,
                        "success": result["success"],
                        "output": result["output"],
                        "error": result["error"]
                    })
                else:
                    print(f"{Fore.YELLOW}command skipped.{Style.RESET_ALL}")
                    results.append({
                        "type": "command",
                        "command": command,
                        "success": False,
                        "output": "",
                        "error": "User declined execution"
                    })
        
        elif action_type == "task":
            description = action.get("description", "")
            steps = action.get("steps", [])
            
            print(f"{Fore.MAGENTA}task: {description}{Style.RESET_ALL}")
            
            task_results = []
            for i, step in enumerate(steps):
                step_command = step.get("command", "")
                step_description = step.get("description", "")
                
                print(f"{Fore.BLUE}step {i+1}: {step_description}{Style.RESET_ALL}")
                
                if step_command:
                    result = run_command(step_command)
                    
                    if result["success"]:
                        if result["output"]:
                            print(f"{Fore.GREEN}{result['output']}{Style.RESET_ALL}")
                    else:
                        if result["error"]:
                            print(f"{Fore.RED}error: {result['error']}{Style.RESET_ALL}")
                    
                    task_results.append({
                        "step": i+1,
                        "command": step_command,
                        "success": result["success"],
                        "output": result["output"],
                        "error": result["error"]
                    })
            
            results.append({
                "type": "task",
                "description": description,
                "steps": task_results
            })
        
        elif action_type == "info":
            message = action.get("message", "")
            print(f"{Style.DIM}{Fore.YELLOW}info: {message}{Style.RESET_ALL}")
            results.append({
                "type": "info",
                "message": message
            })
    
    return results



def main():
    provider = os.getenv("WEN_PROVIDER", "openai")
    print(f"{Fore.CYAN}hi i am wen - working dir: {os.getcwd()} - using {provider}{Style.RESET_ALL}")
    # print(f"{Fore.YELLOW}Type 'exit' to quit{Style.RESET_ALL}")
    
    while True:
        user_input = input(f"\n{Fore.GREEN}> {Style.RESET_ALL}").strip()
        
        if user_input.lower() in ["exit", "quit", "bye"]:
            print(f"{Fore.MAGENTA}Goodbye! 👋{Style.RESET_ALL}")
            break
            
        if not user_input:
            continue
        
        try:
            # Get AI response in JSON format
            response_text = get_ai_response(user_input, conversation_history)
            
            # Parse the JSON response
            ai_response = parse_ai_response(response_text)
            
            
            
            # Show thinking process (optional, can be toggled)
            # Opacity is not natively supported for terminal text color using colorama or ANSI codes.
            # As a workaround, you can use a dimmer style to visually "soften" the text, which is the closest effect.
            if ai_response.get('thinking'):
                print(f"{Style.DIM}{Fore.BLUE}thinking: {ai_response['thinking']}{Style.RESET_ALL}")
            # Note: True opacity/transparency is not possible in terminal text.
            
            # Execute actions
            actions = ai_response.get('actions', [])
            if actions:
                print(f"{Style.DIM}{Fore.CYAN}running {len(actions)} action(s)...{Style.RESET_ALL}")
                action_results = execute_actions(actions, conversation_history)
                
                # Add results to conversation history
                conversation_history.append({
                    "role": "assistant",
                    "content": f"Executed actions: {json.dumps(action_results, indent=2)}"
                })
            else:
                # No actions to execute, just conversation
                conversation_history.append({
                    "role": "assistant",
                    "content": ai_response.get('response', '')
                })
            
            # Show next action plan
            # if ai_response.get('next_action'):
            #     print(f"{Style.DIM}{Fore.MAGENTA}next: {ai_response['next_action']}{Style.RESET_ALL}")
            
            # Add user input to history
            conversation_history.append({"role": "user", "content": user_input})

            # Display the AI's response
            print(f"{Fore.GREEN}wen: {ai_response.get('response', 'No response')}{Style.RESET_ALL}")
        
        except Exception as e:
            print(f"{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
            # Let AI help with the error
            error_context = f"An error occurred: {str(e)}. Please help resolve this."
            try:
                error_response = get_ai_response(error_context, conversation_history)
                error_parsed = parse_ai_response(error_response)
                print(f"{Fore.CYAN}🔧 AI suggestion: {error_parsed.get('response', error_response)}{Style.RESET_ALL}")
            except:
                print(f"{Fore.CYAN}🔧 AI suggestion: Please try again or rephrase your request.{Style.RESET_ALL}")
        
        # Keep history manageable (last 20 exchanges)
        if len(conversation_history) > 40:
            conversation_history.pop(1)  # Remove oldest user message
            conversation_history.pop(1)  # Remove oldest assistant message

if __name__ == "__main__":
    main() 