import smtplib
import speech_recognition as sr
import webbrowser
import requests
import pygame
from google import genai
import os
import keyboard as k
import pyautogui
import time
from PIL import Image, ImageTk, ImageSequence
import threading
import pyaudio
from dotenv import load_dotenv
import sqlite3
from newsdataapi import NewsDataApiClient
import edge_tts
import asyncio
import pywhatkit as wb
import urllib.parse
from datetime import datetime
import random
import shutil
import io
import imaplib
import email
from email.header import decode_header
import sys
import json
import speedtest
from groq import Groq
import wikipedia

load_dotenv()
ui_print = print
close_callback = None
ui_state_callback = None
is_running = True

# global flags
speech_thread = None
stop_speaking = False
speech_id_counter = 0
chat_history = []
ai_thread = None
ai_result = None
ai_thinking = False
current_channel = None
speech_lock = threading.Lock()


# --- CONFIGURATION ---
# Lower value = More sensitive mic (Faster pickup)
ERROR_THRESHOLD = 300

# In main.py, where you configure the recognizer:
recognizer = sr.Recognizer()
recognizer.energy_threshold = ERROR_THRESHOLD
recognizer.dynamic_energy_threshold = True

# Adjust the pause threshold for faster processing after you stop speaking
# A lower value (e.g., 0.8) means it will process faster.
recognizer.pause_threshold = 0.8  



# --- NEW: DEDICATED TTS EVENT LOOP (Speed Optimization) ---
# This creates a permanent background thread for generating audio.
tts_loop = asyncio.new_event_loop()


def start_tts_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


# Start the TTS loop immediately
t = threading.Thread(target=start_tts_loop, args=(tts_loop,), daemon=True)
t.start()

# --- OPTIMIZED MIXER SETUP ---
try:
    # OPTIMIZATION: Updated to 24000Hz to match edge-tts native output (NeerjaNeural)
    # This avoids internal resampling latency.
    if pygame.mixer.get_init():
        pygame.mixer.quit()
    pygame.mixer.init(frequency=24000, channels=1)
except Exception as e:
    print("Pygame Mixer Initialization Error:", e)


def set_ui_callback(func):
    global ui_print
    ui_print = func


def set_close_callback(func):
    global close_callback
    close_callback = func


def set_ui_state_callback(func):
    global ui_state_callback
    ui_state_callback = func


def set_ui_state(state):
    """Updates the UI state (idle, listening, processing)"""
    if ui_state_callback:
        ui_state_callback(state)


def stop_execution():
    global is_running, stop_speaking
    is_running = False
    stop_speaking = True
    if pygame.mixer.get_init():
        pygame.mixer.stop()
    ui_print("System halting...")


# function for checking environment variable
def check_env_variable():
    print("Performing system checks...")
    required_keys = [
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "OPENWEATHER_KEY",
        "NEWS_API_KEY",
        "EMAIL_USER",
        "EMAIL_PASS",
    ]
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    if missing_keys:
        print(
            f"Warning: The following environment variables are missing: {', '.join(missing_keys)}"
        )
        # We don't exit here to allow partial functionality, but warn user
    if not os.path.exists("contact.db"):
        print("Warning: contact.db database file is missing.")
    init_db()

def init_db():
    """Creates the contact database and tables if they don't exist yet."""
    conn = sqlite3.connect("contact.db")
    cursor = conn.cursor()
    # Create WhatsApp table
    cursor.execute('''CREATE TABLE IF NOT EXISTS contacts 
                      (id INTEGER PRIMARY KEY, name TEXT, phone_number TEXT)''')
    # Create Email table
    cursor.execute('''CREATE TABLE IF NOT EXISTS email_contacts 
                      (id INTEGER PRIMARY KEY, name TEXT, email TEXT)''')
    conn.commit()
    conn.close()


def addContact():
    speak("Do you want to save a WhatsApp number, or an Email address?")
    wait_until_silent()
    contact_type = speakToText().lower()
    
    if not contact_type:
        return
        
    if "whatsapp" in contact_type or "number" in contact_type or "phone" in contact_type:
        speak("What is the name of the contact?")
        wait_until_silent()
        name = speakToText()
        if not name:
            speak("I didn't catch the name. Cancelling.")
            return
            
        speak("What is the phone number?")
        wait_until_silent()
        number_spoken = speakToText()
        
        # Clean up number (removes spaces, hyphens, and text)
        clean_number = "".join(filter(str.isdigit, number_spoken))
        if len(clean_number) < 10:
            speak("That doesn't sound like a complete phone number. Cancelling.")
            return
            
        # Save to DB
        conn = sqlite3.connect("contact.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO contacts (name, phone_number) VALUES (?, ?)", (name.lower(), clean_number))
        conn.commit()
        conn.close()
        speak(f"Successfully saved WhatsApp number for {name}.")
        
    elif "email" in contact_type:
        speak("What is the name of the contact?")
        wait_until_silent()
        name = speakToText()
        if not name:
            speak("I didn't catch the name. Cancelling.")
            return
            
        speak("What is the email address? Say 'at' and 'dot' where appropriate.")
        wait_until_silent()
        email_spoken = speakToText().lower()
        
        # Clean up spoken email (e.g., "pratik at gmail dot com" -> "pratik@gmail.com")
        clean_email = email_spoken.replace(" at ", "@").replace(" dot ", ".").replace(" ", "")
        
        # Save to DB
        conn = sqlite3.connect("contact.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO email_contacts (name, email) VALUES (?, ?)", (name.lower(), clean_email))
        conn.commit()
        conn.close()
        speak(f"Successfully saved email address for {name}.")
        
    else:
        speak("I didn't understand the contact type. Please try again.")

# --- OPTIMIZED SPEAK FUNCTION ---
def speak(text):
    global speech_thread, stop_speaking, speech_id_counter

    # Thread lock prevents rapid-fire inputs from causing a race condition
    with speech_lock:
        # 1. Stop any current audio immediately
        if pygame.mixer.get_init():
            pygame.mixer.stop()
            pygame.mixer.music.stop()

        # 2. Increment ID: This tells any previous running 'speak' threads to abort
        speech_id_counter += 1
        my_id = speech_id_counter
        stop_speaking = False

    
    set_ui_state("processing")

    def run_wrapper():
        # Use BytesIO to hold Audio data in RAM
        target_source = io.BytesIO()

        try:
            # Generate Audio
            communicate = edge_tts.Communicate(text, "hi-IN-SwaraNeural", rate="+20%")

            async def collect_audio():
                async for chunk in communicate.stream():
                    # CHECK: If a new speak() command started, stop generating this one
                    if my_id != speech_id_counter:
                        return
                    
                    if chunk["type"] == "audio":
                        target_source.write(chunk["data"])

            # Run in the global loop
            future = asyncio.run_coroutine_threadsafe(collect_audio(), tts_loop)
            future.result()

            # CHECK: Before playing, did a new command come in?
            if my_id != speech_id_counter:
                return

            target_source.seek(0)

        except Exception as e:
            # print(f"TTS Error: {e}")
            set_ui_state("idle")
            return

        try:
            # Play using Sound object
            sound = pygame.mixer.Sound(file=target_source)

            # CHECK: Double check before playing
            if my_id != speech_id_counter:
                return
            ui_print(f"CYPHER: {text}")
            # FORCED SINGLE CHANNEL: Prevents overlapping audio natively
            channel = pygame.mixer.Channel(0)
            channel.play(sound)

            while channel.get_busy():
                # CHECK: Stop if user pressed ESC or new ID appeared
                if stop_speaking or my_id != speech_id_counter:
                    channel.stop()
                    break
                time.sleep(0.05)

        except Exception as e:
            print(f"Playback Error: {e}")
        finally:
            # Only reset to idle if this thread is still the active one
            if my_id == speech_id_counter:
                set_ui_state("idle")

    speech_thread = threading.Thread(target=run_wrapper, daemon=True)
    speech_thread.start()


def wait_until_silent():
    if speech_thread and speech_thread.is_alive():
        speech_thread.join()


def stopSpeaking():
    global stop_speaking
    stop_speaking = True
    if pygame.mixer.get_init():
        pygame.mixer.stop()  # Stops all active Sound channels
        pygame.mixer.music.stop()  # Stops any background music


# Bind Hotkey to stop speaking
k.add_hotkey("esc", stopSpeaking)


def okSir():
    speak("Okay sir")
    return


HISTORY_FILE = "chat_memory.json"


def save_memory():
    """Saves the current chat history to a file"""
    global chat_history
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(chat_history, f)
    except Exception as e:
        print(f"Memory Save Error: {e}")


def load_memory():
    """Loads chat history from file on startup"""
    global chat_history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                chat_history = json.load(f)
            print("Previous chat history loaded.")
            return
        except Exception as e:
            print("Memory corrupted, starting fresh.")

    # If no file exists, start fresh
    init_chat()

# --- UPDATED INIT CHAT ---
def init_chat():
    global chat_history
    chat_history = [
        {
            "role": "user",
            "parts": [
                {
                    "text": "You are CYPHER, a stylish, empathetic, and witty AI assistant. Speak in a mix of English and Hindi (Hinglish) when appropriate, and always address the user as 'Sir'."
                }
            ],
        },
        {
            "role": "model",
            "parts": [
                {
                    "text": "Namaste Sir. Systems are online. I am Cypher, ready to assist."
                }
            ],
        },
        {
            "role": "user",
            "parts": [
                {
                    "text": "You are CYPHER, created by Pratik Pattanayak."
                }
            ],
        },
        {
            "role": "user",
            "parts": [
                {
                    # ---> THIS IS THE NEW STRICT RULE <---
                    "text": "CRITICAL RULE: You must always give extremely short, punchy, and direct responses. NEVER exceed 1 or 2 sentences unless I explicitly ask you for a detailed explanation. Do not use markdown formatting. Be quick and conversational."
                }
            ],
        },
    ]

def reset_chat():
    """Clears memory and deletes the file"""
    init_chat()
    save_memory()  # Overwrite the file with the fresh start
    speak("Memory Cleared. Starting fresh.")


def aiProcess(prompt):
    global chat_history
    
    # 1. Add user prompt to memory first
    chat_history.append({"role": "user", "parts": [{"text": prompt}]})
    
    try:
        # --- ATTEMPT 1: PRIMARY BRAIN (GEMINI) ---
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=chat_history
        )
        reply = response.text.strip().replace("*", "").replace("#", "").replace("`", "")
        
        # Save memory and return
        chat_history.append({"role": "model", "parts": [{"text": reply}]})
        save_memory()
        return reply

    except Exception as gemini_error:
        print(f"Gemini Brain Offline ({gemini_error}). Switching to Groq Backup...")
        
        try:
            # --- ATTEMPT 2: BACKUP BRAIN (GROQ) ---
            groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            
            # Groq needs a different memory format, so we quickly translate Cypher's memory
            groq_history = []
            for msg in chat_history:
                role = "assistant" if msg["role"] == "model" else "user"
                content = msg["parts"][0]["text"]
                groq_history.append({"role": role, "content": content})
                
            # Call Groq (Using LLaMA 3 8B because it is blazing fast)
            groq_response = groq_client.chat.completions.create(
                messages=groq_history,
                model="llama-3.3-70b-versatile" 
            )
            
            reply = groq_response.choices[0].message.content.strip().replace("*", "").replace("#", "").replace("`", "")
            
            # Save memory in original format so Gemini can read it when it comes back online
            chat_history.append({"role": "model", "parts": [{"text": reply}]})
            save_memory()
            return reply
            
        except Exception as groq_error:
            print(f"Groq Brain Offline: {groq_error}")
            
            # If BOTH brains fail, remove the prompt and apologize
            if chat_history and chat_history[-1]["role"] == "user":
                chat_history = chat_history[:-1]
            return "I have lost connection to both my primary and backup servers, sir."

def speak_while_thinking(prompt):
    res = aiProcess(prompt)
    if res:
        speak(res)
        wait_until_silent()  # Force the mic to stay off until she finishes her sentence


def speakToText(retries=3):
    for _ in range(retries):
        with sr.Microphone() as source:
            # Set UI to listening ONLY when the mic actually opens
            set_ui_state("listening") 
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
                set_ui_state("processing")
                
                # MUST BE A SINGLE LANGUAGE CODE! (This is what caused the crash)
                text = recognizer.recognize_google(audio, language="en-IN")
                ui_print(f"USER: {text}")
                
                set_ui_state("idle")
                return text
                
            except sr.WaitTimeoutError:
                set_ui_state("idle")
                continue
                
            except sr.UnknownValueError:
                set_ui_state("idle")
                speak("I didn't catch that, Sir.")
                wait_until_silent()
                continue
                
            except Exception as e:
                print(f"Mic Error: {e}")
                set_ui_state("idle")
                break
                
    set_ui_state("idle")
    return ""

# --- COMMAND ROUTING DICTIONARIES ---
WEB_LINKS = {
    "google": "https://www.google.com",
    "facebook": "https://www.facebook.com",
    "youtube": "https://www.youtube.com",
    "linkedin": "https://www.linkedin.com",
    "gmail": "https://mail.google.com",
    "instagram": "https://www.instagram.com",
    "github": "https://www.github.com",
    "internshala": "https://internshala.com",
    "indeed": "https://www.indeed.com",
}

HOTKEYS = {
    "close window": ["alt", "f4"],
    "close tab": ["ctrl", "w"],
    "switch window": ["alt", "tab"],
    "lock": ["win", "l"],
    "log off": ["win", "l"],
    "print": ["ctrl", "p"],
    "save file": ["ctrl", "s"],
    "select all": ["ctrl", "a"],
    "copy": ["ctrl", "c"],
    "paste": ["ctrl", "v"],
    "cut": ["ctrl", "x"],
    "find": ["ctrl", "f"],
    "take screenshot": ["printscreen"],    # PrtSc Key
    "open emoji": ["win", "."],            # F1 Key (Windows Emoji Panel)
    "mute microphone": ["win", "alt", "k"] # F8 Key (Windows 11 Mic Toggle)
}

MEDIA_KEYS = {
    "volume up": "volumeup",
    "volume down": "volumedown",
    "volume mute": "volumemute",
    "mute": "volumemute",                # Shorter command for F5
    "play music": "playpause",
    "pause music": "playpause",
    "next song": "nexttrack",
    "previous song": "prevtrack",
    "brightness up": "brightnessup",     # F3 Key
    "brightness down": "brightnessdown"  # F2 Key
}
APPS_NAMES = {
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "firefox": "Mozilla Firefox",
    "word": "Microsoft Word",
    "excel": "Microsoft Excel",
    "powerpoint": "Microsoft PowerPoint",
    "notepad": "Notepad",
    "calculator": "Calculator",
    "cmd": "Command Prompt",
    "terminal": "Windows Terminal",
    "vs code": "Visual Studio Code",
    "vs studio": "Visual Studio",
    "files" : "File Explorer",
    "file explorer" : "File Explorer",
}

def openApp(app):
    try:
        pyautogui.hotkey("win", "s")
        time.sleep(0.15)  # Minimized delay here
        pyautogui.write(app, interval=0.01)  # Faster typing speed
        time.sleep(0.15)  # Short pause to let search results populate
        k.press_and_release("enter")
    except:
        speak("I couldn't identify the application name.")


def processCommand(c):
    c_lower = c.lower()
    ui_print(f"Processing: {c}")
    
    # 1. Check simple Website Links automatically
    for site, url in WEB_LINKS.items():
        if site in c_lower:
            speak(f"Opening {site}, Sir.")
            wait_until_silent()
            return webbrowser.open(url)

    # 2. Check Keyboard Shortcuts automatically
    for trigger, keys in HOTKEYS.items():
        if trigger in c_lower:
            speak(f"Executing {trigger}, Sir.")
            wait_until_silent()
            return pyautogui.hotkey(*keys)

    # 3. Check Media/System Keys automatically
    for key, media_key in MEDIA_KEYS.items():
        if key in c_lower:
            speak("Right away, Sir.")
            wait_until_silent()
            return pyautogui.press(media_key)

    # 4. Handle Complex Commands & App Integrations
    if "open" in c_lower:
        app_name = c_lower.replace("open", "").strip()
        actual_app_name = APPS_NAMES.get(app_name, app_name)
        speak(f"Opening {actual_app_name}, Sir.")
        wait_until_silent()
        openApp(actual_app_name)
        
    elif "type what i say" in c_lower:
        speak("What do you want to type?")
        wait_until_silent()
        text = speakToText()
        if text:
            pyautogui.typewrite(text)
            pyautogui.press("enter")
            
    elif "put on sleep" in c_lower:
        pyautogui.hotkey("win", 'x')
        time.sleep(0.2)
        pyautogui.press('u')
        time.sleep(0.2)
        pyautogui.press('s')
        
    elif "shutdown" in c_lower:
        speak("Shutting down the computer, Sir.")
        wait_until_silent()
        os.system("shutdown /s /t 1") 
        
    elif "restart" in c_lower:
        speak("Restarting the system, Sir.")
        wait_until_silent()
        os.system("shutdown /r /t 1")
        
    elif "weather" in c_lower:
        city = c_lower.split("in")[-1].strip() if "in" in c_lower else "Mumbai"
        res = getWeather(city)
        speak(res)
        wait_until_silent()
        
    elif "send email" in c_lower:
        sendMail()
        
    elif "check email" in c_lower or "read email" in c_lower:
        check_emails()
        
    elif "check internet speed" in c_lower:
        res = check_internet_speed()
        speak(res)
        wait_until_silent()
        
    elif "news" in c_lower:
        speak(getNews())
        wait_until_silent()
        
    elif "send message on whatsapp" in c_lower:
        sendWhatsAppMessage()
    
    elif "add contact" in c_lower or "save contact" in c_lower or "new contact" in c_lower:
        addContact()
        
    elif "wikipedia" in c_lower:
        # 1. Clean the text here in the router!
        topic = c_lower.replace("search wikipedia for", "").replace("wikipedia", "").replace("who is", "").replace("what is", "").strip()
        
        # 2. If it's empty, ask the user
        if not topic:
            speak("What is the topic?")
            wait_until_silent()
            topic = speakToText()
            
        # 3. Pass the perfectly clean topic to the worker
        if topic:
            speak(f"Searching Wikipedia for {topic}, Sir.")
            wait_until_silent()
            speak(search_wikipedia(topic))
            wait_until_silent()
            
    # 5. Basic Chat & Status Checks
    elif any(phrase in c_lower for phrase in ["new session", "reset chat", "clear history"]):
        reset_chat()
        
    elif "time" in c_lower:
        speak(f"The current time is {datetime.now().strftime('%H:%M')}")
        
    elif "date" in c_lower:
        speak(f"Today's date is {datetime.now().strftime('%B %d, %Y')}")
        
    elif "day" in c_lower:
        speak(f"Today is {datetime.now().strftime('%A')}")
        
    elif "are you there" in c_lower:
        speak("Yes sir, I am here.")
        
    elif "turn off" in c_lower or "stop" in c_lower:
        if "stop speaking" in c_lower or c_lower.strip() == "stop":
            stopSpeaking()
        else:
            shutdown_sequence()
            
    # 6. Fallback to Gemini/Groq Brain
    else:
        conversational_words = ["hello", "hi", "hey", "thanks", "yes", "no", "why", "who", "what", "wow"]
        
        # If it's a single word, AND it's not a normal conversational word, block it.
        if len(c.split()) < 2 and c_lower not in conversational_words:
            speak("Could you please be more specific, Sir?")
            wait_until_silent()
        else:
            set_ui_state("processing")
            speak_while_thinking(c)

# --- UPDATED GREET FUNCTION ---
def greet():
    hour = int(datetime.now().hour)
    greeting = ""

    # Logic to determine the correct time of day
    if hour >= 0 and hour < 5:
        greeting = "You are up late, Sir."
    elif hour >= 5 and hour < 12:
        greeting = "Good Morning, Sir."
    elif hour >= 12 and hour < 18:
        greeting = "Good Afternoon, Sir."
    else:
        greeting = "Good Evening, Sir."

    # FIX: Combine the greeting and the name into one speak() call
    speak(f"{greeting} I am Cypher. How may I assist you?")


def shutdown_sequence():
    farewell_messages = [
        "Powering down all systems. Have a productive day, Sir.",
        "Disconnecting from the mainframe. Namaste, Sir.",
        "Shutting down. I will be ready when you need me next.",
        "Going offline. Take care, Sir.",
        "System hibernation initiated. Goodbye.",
    ]

    # Select a random message from the list
    choice = random.choice(farewell_messages)
    speak(choice)

    wait_until_silent()

    # NOW it is safe to close the GUI
    if close_callback:
        close_callback()


# fetching email from database
def get_email_from_db(name_spoken):
    conn = sqlite3.connect("contact.db")
    cursor = conn.cursor()
    # diverse query to handle partial matches
    cursor.execute(
        "SELECT email FROM email_contacts WHERE LOWER(name) LIKE ?",
        ("%" + name_spoken.lower().strip() + "%",),
    )
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    else:
        speak("I couldn't find that contact in the database.")
        return None


# send mail function
def sendMail():
    speak("Whom do you want to email?")
    wait_until_silent()
    name = speakToText()
    if not name:
        speak("I didn't hear a name.")
        return

    email_address = get_email_from_db(name)

    if email_address:
        while True:
            wait_until_silent()
            mail_subject = getMailSubject()
            if mail_subject:
                break

        while True:
            wait_until_silent()
            mail_body = getMailBody()
            if mail_body:
                break

        send_email_smtp(email_address, mail_subject, mail_body)
    else:
        speak(f"I couldn't find an email for {name}")


# mail body
def getMailBody():
    speak("What should I say in the email?")
    wait_until_silent()
    body = speakToText()
    return body


# mail subject
def getMailSubject():
    speak("What is the subject of the email?")
    wait_until_silent()
    subject = speakToText()
    return subject


def send_email_smtp(to_address, subject, body):
    from_address = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")

    message = f"Subject: {subject}\n\n{body}"

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(from_address, password)
        server.sendmail(from_address, to_address, message)
        server.quit()
        speak("Email has been sent successfully.")
    except Exception as e:
        print(e)
        speak("Sorry, I was unable to send the email.")


# check emails
def check_emails():
    try:
        speak("Checking for new emails, Sir...")
        wait_until_silent()

        # Connect to Gmail IMAP
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
        mail.select("inbox")

        # Search for unread emails
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()

        if not email_ids:
            speak("You have no new emails, Sir.")
            wait_until_silent()
            return

        count = len(email_ids)
        speak(f"You have {count} new emails.")
        wait_until_silent()

        # Read the latest 3 emails
        for i in range(min(3, count)):
            latest_email_id = email_ids[-(i + 1)]  # Get latest first
            _, msg_data = mail.fetch(latest_email_id, "(RFC822)")

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    # Correctly decode multi-part encoded subjects
                    subject_parts = decode_header(msg["Subject"])
                    subject = "".join(
                        [
                            (
                                part[0].decode(part[1] or "utf-8")
                                if isinstance(part[0], bytes)
                                else str(part[0])
                            )
                            for part in subject_parts
                        ]
                    )

                    # Decode and clean Sender Name
                    from_header = msg.get("From")
                    if from_header:
                        from_parts = decode_header(from_header)
                        from_ = "".join(
                            [
                                (
                                    part[0].decode(part[1] or "utf-8")
                                    if isinstance(part[0], bytes)
                                    else str(part[0])
                                )
                                for part in from_parts
                            ]
                        )
                        # Strip email address <...> for cleaner TTS
                        if "<" in from_:
                            from_ = from_.split("<")[0].strip().replace('"', "")
                    else:
                        from_ = "Unknown"

                    # Just speak normally, and then tell the script to freeze!
                    speak(f"Email {i+1} from {from_}. Subject: {subject}")
                    wait_until_silent()

                    # Small pause between emails
                    time.sleep(0.5)

        speak("That is all for now, Sir.")
        mail.close()
        mail.logout()

    except Exception as e:
        print(e)
        speak("I encountered an error while accessing your inbox, Sir.")


# weather fetch function
def getWeather(city):
    api_key = os.getenv("OPENWEATHER_KEY")
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    headers = {"User-Agent": "MyWeatherApp/1.0"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        weather_info = f"City: {data['name']}. Temperature: {data['main']['temp']} °C. Weather: {data['weather'][0]['description']}. Humidity: {data['main']['humidity']} %. Wind Speed: {data['wind']['speed']} m/s."
        print(weather_info)
        return weather_info
    else:
        print("Error: Unable to fetch weather information.")
        return "Error: Unable to fetch weather information."


# news fetch function
def getNews():
    api = NewsDataApiClient(apikey=os.getenv("NEWS_API_KEY"))
    response = api.latest_api(country="in", language="en")

    if response["status"] == "success":
        articles = response["results"]
        news_brief = "Here are the top news headlines. "

        for i in range(min(5, len(articles))):
            news_brief += f"{i+1}. {articles[i]['title']}. "

        print(news_brief)
        return news_brief
    else:
        print("Error: Unable to fetch news.")
        return "Sorry, I could not fetch the news."


# whatsapp message function
def get_whatsapp_number_from_db(name_spoken):
    conn = sqlite3.connect("contact.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT phone_number FROM contacts WHERE LOWER(name) LIKE ?",
        ("%" + name_spoken.lower().strip() + "%",),
    )
    result = cursor.fetchone()
    conn.close()

    if result:
        raw_number = result[0]
        clean_number = "".join(filter(str.isdigit, raw_number))
        if len(clean_number) == 10:
            clean_number = "+91" + clean_number
        if not clean_number.startswith("+"):
            clean_number = "+" + clean_number

        return clean_number

    return None


def sendWhatsAppMessage():
    speak("Whom do you want to send message?")
    wait_until_silent()
    name = speakToText()

    if not name:
        speak("I didn't hear a name.")
        return

    phone_number = get_whatsapp_number_from_db(name)

    if not phone_number:
        speak(f"I couldn't find a phone number for {name}")
        return

    speak("What is the message?")
    wait_until_silent()
    message = speakToText()

    if not message:
        speak("I didn't hear a message.")
        return

    send_whatsapp_message(phone_number, message)


def send_whatsapp_message(phone_number, message):
    speak("Sending message...")
    # Let PyWhatKit handle the wait and the safe tab closing automatically!
    wb.sendwhatmsg_instantly(
        phone_number, message, wait_time=15, tab_close=True, close_time=3
    )
    speak("Message sent successfully.")

# wikipedia search function
def search_wikipedia(topic):
    if not topic:
        return "I didn't catch the topic, sir."

    try:
        # Just search exactly what it was given!
        result = wikipedia.summary(topic, sentences=2)
        return f"According to Wikipedia: {result}"
        
    except wikipedia.exceptions.DisambiguationError:
        return "There are too many different results for that topic. Please be more specific."
    except wikipedia.exceptions.PageError:
        return "I couldn't find any matching page on Wikipedia, sir."
    except Exception as e:
        print(f"Wikipedia Error: {e}")
        return "Connection to Wikipedia failed, sir."  
# check internet speed
def check_internet_speed():
    try:
        # 1. Tell Cypher to speak normally
        speak("Checking internet speed, please wait...")

        # 2. Use your new function to FREEZE the program until she finishes talking
        wait_until_silent()

        # 3. NOW it is safe to run the speed test!
        st = speedtest.Speedtest()

        # Faster: skip full server scan
        st.get_best_server()

        download_speed = st.download(threads=1) / 1_000_000
        upload_speed = st.upload(threads=1) / 1_000_000
        ping = st.results.ping

        return f"Download {download_speed:.1f} Mbps, Upload {upload_speed:.1f} Mbps, Ping {ping:.0f} ms"

    except Exception as e:
        print(e)
        return "Internet speed check failed, sir."


def activateAssistant():
    global is_running
    is_running = True
    greet()

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)

        while is_running:
            set_ui_state("listening")
            print("Waiting for wake word...")
            try:
                while speech_thread and speech_thread.is_alive():
                    time.sleep(0.05)
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=4)

                set_ui_state("processing")
                word = recognizer.recognize_google(audio, language="en-IN").lower()
                print("Heard wake word:", word)

                if "turn off" in word:
                    shutdown_sequence()
                    return
                wake_words = ["cypher", "cipher", "saifer", "hey cypher"]

                if any(w in word for w in wake_words):
                    activate_msg = [
                        "Yes, Sir?",
                        "At your service.",
                        "I'm here, Sir.",
                        "Ready, Sir.",
                    ]
                    if random.random() < 0.7:
                        speak(random.choice(activate_msg))
                    else:
                        speak("hmm..")
                    active = True

                    while active and is_running:
                        try:
                            while speech_thread and speech_thread.is_alive():
                                time.sleep(0.05)

                            print("CYPHER Active...")
                            set_ui_state("listening")
                            audio_cmd = recognizer.listen(
                                source, timeout=5, phrase_time_limit=15
                            )

                            set_ui_state("processing")
                            command = recognizer.recognize_google(
                                audio_cmd, language="en-IN"
                            ).lower()
                            ui_print(f"USER: {command}")

                            if "stop listening" in command or "go to sleep" in command:
                                speak("Entering standby mode.")
                                active = False
                            elif "turn off" in command:
                                shutdown_sequence()
                                return
                            else:
                                processCommand(command)

                        except sr.WaitTimeoutError:
                            pass
                        except sr.UnknownValueError:
                            pass
                        finally:
                            set_ui_state("idle")

            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except Exception as e:
                print(f"Error: {e}")
            finally:
                if is_running:
                    set_ui_state("idle")


if __name__ == "__main__":
    check_env_variable()
    load_memory()
    activateAssistant()
