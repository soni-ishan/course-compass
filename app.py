import os
import dotenv
import sys
import ssl
from flask import Flask, request, jsonify
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from groq import Groq
from flask_cors import CORS

dotenv.load_dotenv()

# --- Environment Variables ---
# Replace these placeholder values with your actual credentials.
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing for frontend communication

# --- Neo4j Driver Initialization ---
driver = None
try:
    if "YOUR_NEO4J" in NEO4J_URI or "YOUR_NEO4J" in NEO4J_PASSWORD:
         raise ValueError("Please replace the placeholder Neo4j credentials in app.py.")

    # Create an SSL context that disables certificate verification, similar to your friend's script
    # WARNING: This is insecure for production.
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
        ssl_context=ssl_context
    )
    driver.verify_connectivity()
    print("Successfully connected to Neo4j.")
except ServiceUnavailable as e:
    print(f"Error connecting to Neo4j: {e}")
    print("\nThis is often due to an incorrect URI. Please check the following:")
    print("1. Your `NEO4J_URI` in app.py is correct.")
    print("2. The database is running and accessible from your network.")
    driver = None # Ensure driver is None on failure
except Exception as e:
    print(f"An unexpected error occurred when connecting to Neo4j: {e}")
    driver = None # Ensure driver is None on failure


# --- Groq Client Initialization ---
groq_client = None
try:
    if "YOUR_GROQ" in GROQ_API_KEY:
        raise ValueError("Please replace the placeholder GROQ_API_KEY in app.py.")
    groq_client = Groq(api_key=GROQ_API_KEY)
    print("Groq client initialized successfully.")
except Exception as e:
    print(f"Error initializing Groq client: {e}")


# --- System Prompt for the LLM ---
# This prompt guides the LLM on how to behave and what information it has.
SYSTEM_PROMPT = """
You are a university course advisor chatbot. Your purpose is to help students understand course prerequisites and recommend courses based on their interests. You will be given context from a Neo4j graph database that contains course information.

**Your instructions are:**
1.  **Analyze the User's Query:** Understand if the user is asking for prerequisites of a specific course or for course recommendations for a field of interest.
2.  **Use Provided Context:** Base your answers *only* on the context provided from the database query results. Do not invent courses, prerequisites, or relationships.
3.  **Handle Prerequisite Questions:** If the user asks for the prerequisites of a course (e.g., "What are the prerequisites for CS201?"), use the provided data to list them clearly. Distinguish between required and recommended prerequisites.
4.  **Handle Recommendation Questions:** If the user asks for course recommendations (e.g., "What courses should I take for AI?"), use your general knowledge to suggest relevant course codes from the provided list of all available courses.
5.  **Be Conversational and Helpful:** Respond in a clear, friendly, and easy-to-understand manner.
6.  **Handle Insufficient Information:** If the database context does not contain the information needed to answer the question, politely state that you don't have that information. For example, if a course doesn't exist or has no prerequisites.
"""

# --- Graph Schema for the LLM ---
# This helps the LLM understand the structure of the database.
GRAPH_SCHEMA = """
# Graph Schema - Course Prerequisite System

This document defines the graph data model used in the Neo4j-based course prerequisite planning system.

## Node Types

### Course
Represents a university course.
- `code`: Unique course code (e.g., "CS101")
- `title`: Full course title
- `credits`: Number of credit hours
- `level`: Course level (e.g., 100, 200)

### PrerequisiteGroup
Represents a group of prerequisite courses.
- `type`: Logical connector: "AND", "OR"
- `recommended`: `true` if recommended, `false` if required.

## Relationship Types
- `(:Course)-[:REQUIRES]->(:PrerequisiteGroup)`: A course requires a group of prerequisites.
- `(:PrerequisiteGroup)-[:HAS]->(:Course)`: A prerequisite group contains specific courses.
"""

def get_prerequisites(tx, course_code):
    """
    Cypher query to get prerequisites for a specific course.
    """
    query = """
    MATCH (c:Course {code: $course_code})
    OPTIONAL MATCH (c)-[:REQUIRES]->(pg:PrerequisiteGroup)-[:HAS]->(prereq:Course)
    RETURN c.code AS course, c.title AS course_title,
           pg.type AS group_type, pg.recommended AS is_recommended,
           collect(prereq.code) AS prerequisites
    """
    result = tx.run(query, course_code=course_code)
    return [record.data() for record in result]

def get_all_courses(tx):
    """
    Cypher query to get all courses, used for general recommendations.
    """
    query = "MATCH (c:Course) RETURN c.code AS code, c.title AS title"
    result = tx.run(query)
    return [record.data() for record in result]


@app.route('/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint to handle user messages.
    """
    if not driver or not groq_client:
        return jsonify({"error": "Backend services not initialized properly. Check server logs for details."}), 500

    user_message = request.json.get('message', '').strip()
    if not user_message:
        return jsonify({"error": "Empty message received."}), 400

    try:
        # Step 1: Use LLM to classify intent and extract course code
        intent_detection_prompt = f"""
        Analyze the user's message to determine their intent and extract the course code if present.
        The user's message is: "{user_message}"

        Possible intents are: 'get_prerequisites' or 'course_recommendation'.
        If the intent is 'get_prerequisites', return the course code mentioned.
        If the intent is 'course_recommendation', the course code is not needed.

        Return a JSON object with "intent" and "course_code" (or null if not applicable).
        Example for "What are the prereqs for CS101?": {{"intent": "get_prerequisites", "course_code": "CS101"}}
        Example for "What courses are good for data science?": {{"intent": "course_recommendation", "course_code": null}}
        """

        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an expert at classifying user intent."},
                {"role": "user", "content": intent_detection_prompt},
            ],
            model="llama-3.1-8b-instant",
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        response_json = chat_completion.choices[0].message.content
        import json
        intent_data = json.loads(response_json)
        intent = intent_data.get("intent")
        course_code = intent_data.get("course_code")

        context = ""
        with driver.session() as session:
            if intent == 'get_prerequisites' and course_code:
                # Fetch prerequisite data from Neo4j
                prereq_data = session.execute_read(get_prerequisites, course_code.upper())
                if not prereq_data or not any(p['prerequisites'] for p in prereq_data):
                     context = f"The course '{course_code.upper()}' was not found or has no prerequisites listed."
                else:
                    context = "Prerequisite data from the database:\n" + json.dumps(prereq_data, indent=2)

            elif intent == 'course_recommendation':
                # Fetch all courses for general recommendation questions
                all_courses = session.execute_read(get_all_courses)
                context = "List of all available courses:\n" + json.dumps(all_courses, indent=2)
            else:
                 # Fallback for unclear intent
                all_courses = session.execute_read(get_all_courses)
                context = "The user's query was unclear. Here is a list of all courses for context:\n" + json.dumps(all_courses, indent=2)


        # Step 3: Use LLM to generate a natural language response based on context
        final_prompt = f"""
        {SYSTEM_PROMPT}

        Here is the schema of the graph database for your reference:
        {GRAPH_SCHEMA}

        Here is the context retrieved from the database based on the user's query:
        ---
        {context}
        ---

        User's original query: "{user_message}"

        Please provide a helpful and conversational response to the user based *only* on the context provided.
        """

        final_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": final_prompt},
            ],
            model="llama-3.1-8b-instant",
            temperature=0.7
        )

        bot_response = final_completion.choices[0].message.content
        return jsonify({"reply": bot_response})

    except Exception as e:
        print(f"An error occurred during chat processing: {e}")
        return jsonify({"error": "An internal error occurred."}), 500

if __name__ == '__main__':
    if not driver or not groq_client:
        print("\nFATAL: A backend service (Neo4j or Groq) could not be initialized.")
        print("The application will not start. Please check the error messages above.")
        sys.exit(1) # Exit the script if services aren't ready
        
    # It's recommended to use a proper WSGI server like Gunicorn in production
    app.run(debug=True, port=5001)

