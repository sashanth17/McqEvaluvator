import os
import json
import sys
from dotenv import load_dotenv

# Ensure .env is loaded so OPENROUTER_API_KEY is available
# Calculate the absolute path to the .env file in the backend directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(backend_dir, ".env")
load_dotenv(dotenv_path=env_path)

from app.agents.questionAgent import QuestioningAgent

import json
import os
import sys
# Define the path for your evaluation log
LOG_FILE = "interview_evaluation_log.json"

def append_to_evaluation_log(turn_number, topic, agent_question, student_answer):
    """
    Appends a single Q&A interaction to the JSON log file.
    """
    # 1. Load existing data if the file exists
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            try:
                log_data = json.load(f)
            except json.JSONDecodeError:
                log_data = [] # Handle empty or corrupted files
    else:
        log_data = []

    # 2. Construct the new interaction record
    interaction = {
        "turn": turn_number,
        "topic": topic,
        "question_metadata": {
            "question": agent_question.get("question"),
            "question_type": agent_question.get("question_type"),
            "difficulty": agent_question.get("difficulty"),
            "learning_objective": agent_question.get("learning_objective")
        },
        "student_answer": student_answer,
        # Leave a placeholder for your future EvaluatorAgent to fill in
        "evaluation": {
            "score": None,
            "feedback": None,
            "is_concept_mastered": None
        }
    }

    # 3. Append and save
    log_data.append(interaction)
    
    with open(LOG_FILE, "w") as f:
        json.dump(log_data, f, indent=4)
        
    print(f"--- Interaction saved to {LOG_FILE} ---")


def main():
    # Verify API Key
    if not os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        print("Error: API Key is not set.", file=sys.stderr)
        sys.exit(1)

    agent = QuestioningAgent(model="anthropic/claude-sonnet-5")
    
    # Load your test states
    try:
        with open("test_states.json", "r") as f:
            test_states = json.load(f)
    except FileNotFoundError:
        print("Error: test_states.json not found.")
        sys.exit(1)

    # Clear the log file at the start of a new test run (optional)
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    for i, state in enumerate(test_states):
        turn_number = i + 1
        topic = state.get("topic", state.get("current_topic", {}).get("topic", "Unknown Topic"))
        print(f"\nProcessing Turn {turn_number}: {topic}")
        
        try:
            # 1. Generate the question
            result = agent.run(state)
            print(f"Agent asked: {result['question']}")
            
            # 2. Simulate getting a student answer (In production, this comes from the frontend)
            # For testing, you can use input() or a hardcoded string
            print("\nSimulating Student Answer...")
            simulated_answer = input("Type a mock answer (or press Enter for default): ")
            if not simulated_answer.strip():
                simulated_answer = "This is a simulated answer for testing purposes."
            
            # 3. Save the combined Q&A to your JSON log
            append_to_evaluation_log(
                turn_number=turn_number,
                topic=topic,
                agent_question=result,
                student_answer=simulated_answer
            )
            
        except Exception as e:
            print(f"Error during execution of Turn {turn_number}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()