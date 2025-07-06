# Final, Clean Code for Render (bot.py) - Updated for Plan Creation
import os
import logging
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler

# Load environment variables for local testing (Render will use its own)
load_dotenv()

# --- Robust Logging Setup ---
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('chat_history.log')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logging.getLogger("httpx").setLevel(logging.WARNING)

# --- Get Keys & Config from Environment Variables ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
USER_DATA_DIR = "/var/data/user_data" # Absolute path for Render

if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)
    logger.info(f"'{USER_DATA_DIR}' directory created.")

# --- Helper Functions (No changes here) ---
def load_user_data(user_id: int) -> dict:
    filepath = os.path.join(USER_DATA_DIR, f"{user_id}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {"first_name": None, "history": []}

def save_user_data(user_id: int, data: dict) -> None:
    filepath = os.path.join(USER_DATA_DIR, f"{user_id}.json")
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

# --- Conversation States ---
CONVERSATION_MEMORY_LENGTH = 12
# Onboarding State
ASKING_NAME = 1
# --- NEW: Plan Creation States ---
ASKING_PLAN_TYPE = 2
ASKING_GENDER = 3
ASKING_AGE = 4
ASKING_HEIGHT = 5
ASKING_WEIGHT = 6
ASKING_ACTIVITY_LEVEL = 7
ASKING_DIET_PREF = 8
ASKING_ALLERGIES = 9
ASKING_WORKOUT_GOAL = 10
ASKING_WORKOUT_EXP = 11

# --- The Definitive, Consolidated SYSTEM_PROMPT ---
SYSTEM_PROMPT = """
# CORE IDENTITY
Your name is Atom. You are an expert AI assistant and a world-class human performance coach.

# PERSONALITY
Your persona is that of a super-smart, friendly, and slightly witty fitness and nutrition nerd. You are the best training partner someone could ask for: knowledgeable, encouraging, casual, and down-to-earth. You break down complex topics with ease and a touch of reliable humor.

# EXPERTISE & SPECIALIZATIONS
Your knowledge is strictly evidence-based. You have three specializations:
1.  **Strength & Conditioning Specialist:** You design workout programs based on user goals (e.g., fat loss, muscle gain, strength, power) and experience level.
2.  **Sports Nutritionist:** You create personalized diet plans by calculating BMR/TDEE and catering to dietary preferences and allergies. You can provide food substitutions.
3.  **Wellness & Habit Coach:** You use principles from the Cognitive Behavioral Therapy (CBT) framework to help users build sustainable habits and overcome mental blocks.

# CRITICAL INTERACTION PROTOCOLS (Non-Negotiable)

1.  **Name Protocol:** If asked your name ("what is your name?", "who are you?"), your ONLY response is: "I am Atom!"
2.  **Creator Protocol (Progressive Disclosure):** Do not volunteer who made you. If asked ("who made you?", "who trained you?"), your ONLY response is: "I am an AI assistant trained by Viraj to help you with your fitness, nutrition, and wellness goals."
3.  **Plan Protocol:** If a user asks for a diet or workout plan, you MUST state that you need to ask some questions first to create a personalized plan. DO NOT provide a generic plan. Instead, suggest they use the /create_plan command.
4.  **Username Protocol:** You are communicating with {user_name}. Use their name VERY SPARINGLY, only for significant moments of encouragement. Never start a reply with their name. Overusing it is a major failure.
5.  **Evidence Protocol:** Your advice is science-based, but you must be "chill" about it. DO NOT cite studies or share reference links unless the user explicitly asks for them.
6.  **Formatting Protocol:** Use markdown for clarity (*bold* headings, bullet points •). DO NOT use horizontal lines (--- or ___).
7.  **Safety Protocol:** ALWAYS preface specific exercise or diet plans with a clear, friendly disclaimer. Example: "Just a heads-up, before you jump into any new fitness or nutrition plan, it's always a smart move to check in with a healthcare pro to make sure it's a good fit for you."
8.  **Privacy Protocol:** If asked how you remember things, your ONLY response is: "I save our conversation history to provide context for our chats, just like a human coach would remember past sessions. This helps me give you better, more relevant advice. Your privacy is taken very seriously, and your data is never shared."
"""

# --- Bot Functions ---

# Onboarding and general message handling functions (no changes)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (function is unchanged)
    user = update.effective_user
    user_data = load_user_data(user.id)
    if user_data.get("first_name"):
        await update.message.reply_text(f"Hey {user_data['first_name']}, welcome back! What's on your mind today?")
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "Welcome! I'm your evidence-based AI Coach for all things fitness, nutrition, and habit-building. May I know your first name?"
        )
        return ASKING_NAME

async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (function is unchanged)
    user = update.effective_user
    name = update.message.text.strip()
    user_data = {"first_name": name, "history": []}
    save_user_data(user.id, user_data)
    logger.info(f"New user {name} ({user.id}) onboarded.")
    await update.message.reply_text(
        f"Nice to meet you, {name}! How can I help you today?"
    )
    return ConversationHandler.END

def get_ai_response_with_context(history: list, user_name: str) -> str:
    # ... (function is unchanged)
    from groq import Groq
    system_message = {"role": "system", "content": f"You are communicating with a user named {user_name}. {SYSTEM_PROMPT}"}
    messages_to_send = [system_message] + history
    try:
        client = Groq(api_key=GROQ_API_KEY)
        chat_completion = client.chat.completions.create(
            messages=messages_to_send, model="llama3-70b-8192", temperature=0.75, max_tokens=2048,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Error calling Groq API with context: {e}")
        return "Apologies, my systems are under a bit of strain right now. Please try your query again in a moment."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (function is unchanged)
    user = update.effective_user
    user_data = load_user_data(user.id)
    if not user_data.get("first_name"):
        await update.message.reply_text("Welcome! Please use the /start command to set up your profile first.")
        return
    user_message = update.message.text
    logger.info(f"Message from {user_data['first_name']} ({user.id}): '{user_message}'")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    user_data["history"].append({"role": "user", "content": user_message})
    ai_response = get_ai_response_with_context(
        user_data["history"][-CONVERSATION_MEMORY_LENGTH:], user_data["first_name"]
    )
    user_data["history"].append({"role": "assistant", "content": ai_response})
    save_user_data(user.id, user_data)
    logger.info(f"AI Response to {user_data['first_name']}: '{ai_response[:100].replace(chr(10),' ')}...'")
    await update.message.reply_text(ai_response)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (function is unchanged)
    await update.message.reply_text("Process cancelled. Let me know if you need anything else!")
    return ConversationHandler.END

# --- NEW: Plan Creation Functions ---
async def create_plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the personalized plan creation conversation."""
    await update.message.reply_text(
        "Awesome! I can create a personalized plan for you. To get started, what are you looking for?\n\n"
        "You can choose: **Diet Plan**, **Workout Plan**, or **Both**."
    )
    return ASKING_PLAN_TYPE

# We will add all the other data gathering functions here in Phase 2

# --- UPDATED main() function ---
def main() -> None:
    """Runs the bot with multiple conversation handlers."""
    if not TELEGRAM_TOKEN or not GROQ_API_KEY:
        logger.critical("CRITICAL ERROR: TELEGRAM_TOKEN or GROQ_API_KEY not found. Exiting.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # --- Onboarding Conversation Handler ---
    onboarding_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASKING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_name)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # --- Plan Creation Conversation Handler (We will build this out in the next phase) ---
    plan_conv = ConversationHandler(
        entry_points=[CommandHandler("create_plan", create_plan_start)],
        states={
            ASKING_PLAN_TYPE: [
                # For now, just a placeholder. We will add the real logic next.
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_plan_start) 
            ],
            # We will add all other states here in Phase 2
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # We add the handlers to the application
    application.add_handler(onboarding_conv)
    application.add_handler(plan_conv)
    # The general message handler must be last
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Atomic Coach is starting with polling...")
    application.run_polling()

# --- Run the bot directly ---
if __name__ == '__main__':
    main()
