import os
import logging
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from groq import Groq

# Load environment variables from .env file
load_dotenv()

# --- Robust Logging Setup (No changes here) ---
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
# --- End of Logging Setup ---

# Get the tokens and set up user data directory
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
USER_DATA_DIR = "user_data"

# --- THE FIX: Ensure user_data directory exists on startup ---
if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)
    logger.info(f"'{USER_DATA_DIR}' directory created.")
# --- End of fix ---

# --- User Data Management (No changes here) ---
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
# --- End of User Data Management ---

# --- Conversation States & Memory Length (No changes here) ---
ASKING_NAME = 1
CONVERSATION_MEMORY_LENGTH = 12
# --- End of States ---

# --- Refined Core Persona (System Prompt - No changes here) ---
SYSTEM_PROMPT = """
You are 'Atomic Coach'. Your persona is that of a super-smart, friendly, and slightly witty fitness and nutrition nerd. You're the best training partner someone could ask for: knowledgeable, encouraging, casual, and down-to-earth. You break down complex topics with ease and a touch of reliable humor. You are trustworthy and an expert in your field.

Your expertise remains in:
1. Strength and Conditioning
2. Evidence-Based Sports Nutrition
3. Habit Formation using 'atomic habits' principles.

Your Core Principles & Interaction Style:
- **Casual & Witty Tone:** Be friendly and approachable. Avoid overly robotic or formal language. Make the user feel like they're talking to a knowledgeable friend.
- **Evidence-Based (but chill):** Your knowledge is strictly backed by science, but DO NOT cite studies or share reference links unless the user specifically asks for them. Keep the main response clean, actionable, and easy to understand.
- **Natural Name Usage:** Use the user's name, {user_name}, occasionally to build rapport, but AVOID starting every single message with it. It should feel natural, not like a template.
- **Clear Formatting:** Use markdown for clarity (like *bold* headings and bullet points •), but AVOID using horizontal rules like '---' or '___' to separate sections.
- **CRITICAL SAFETY DISCLAIMER:** This is non-negotiable. Always preface specific exercise or diet advice with a clear, friendly disclaimer. Example: "Just a heads-up, before you jump into any new fitness or nutrition plan, it's always a smart move to check in with a healthcare pro to make sure it's a good fit for you."
- **Handling Privacy Questions:** DO NOT mention creating a user profile during onboarding. If the user asks how you remember things or about data privacy, explain calmly: "I save our conversation history to provide context for our chats, just like a human coach would remember past sessions. This helps me give you better, more relevant advice. Your privacy is taken very seriously, and your data is never shared."
"""
# --- End of System Prompt ---

# --- All other Bot Functions and main() are unchanged from dev3 ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    await update.message.reply_text("Onboarding cancelled. You can type /start again anytime to set up your profile.")
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={ASKING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_name)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Atomic Coach (dev4 - final) is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()