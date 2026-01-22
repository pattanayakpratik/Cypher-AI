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
import os 
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

recognizer = sr.Recognizer()
recognizer.energy_threshold = ERROR_THRESHOLD
recognizer.dynamic_energy_threshold = False # Disable dynamic adjustment for speed


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
    # 16000Hz mono matches the edge_tts RAW format exactly.
    # This removes resampling/decoding overhead -> FASTER RESPONSE
    if pygame.mixer.get_init():
        pygame.mixer.quit()
    pygame.mixer.init(frequency=16000, channels=1)
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
    required_keys = ["GEMINI_API_KEY", "OPENWEATHER_KEY", "NEWS_API_KEY", "EMAIL_USER", "EMAIL_PASS"]
    missing_keys = [key for key in required_keys if not os.getenv(key)]
    if missing_keys:
        print(f"Warning: The following environment variables are missing: {', '.join(missing_keys)}")
        # We don't exit here to allow partial functionality, but warn user
    if not os.path.exists('contact.db'):
        print("Warning: contact.db database file is missing.")



# --- OPTIMIZED SPEAK FUNCTION ---
# In main.py

def speak(text):
    global speech_thread, stop_speaking, speech_id_counter
    
    # 1. Stop any current audio immediately
    if pygame.mixer.get_init():
        pygame.mixer.stop() 
        pygame.mixer.music.stop()
        
    # 2. Increment ID: This tells any previous running 'speak' threads to abort
    speech_id_counter += 1
    my_id = speech_id_counter
    
    stop_speaking = False
    ui_print(f"CYPHER: {text}")
    set_ui_state("processing")

    def run_wrapper():
        # Use BytesIO to hold Audio data in RAM
        target_source = io.BytesIO()

        try:
            # Generate Audio
            communicate = edge_tts.Communicate(
                text,
                "en-IN-NeerjaNeural", 
                rate="+15%"
            )

            async def collect_audio():
                async for chunk in communicate.stream():
                    # CHECK: If a new speak() command started, stop generating this one
                    if my_id != speech_id_counter: return 
                    
                    if chunk["type"] == "audio":
                        target_source.write(chunk["data"])

            # Run in the global loop
            future = asyncio.run_coroutine_threadsafe(
                collect_audio(), tts_loop
            )
            future.result() 
            
            # CHECK: Before playing, did a new command come in?
            if my_id != speech_id_counter: return

            target_source.seek(0)

        except Exception as e:
            # print(f"TTS Error: {e}") 
            set_ui_state("idle")
            return

        try:
            # Play using Sound object
            sound = pygame.mixer.Sound(file=target_source)
            
            # CHECK: Double check before playing
            if my_id != speech_id_counter: return
            
            channel = sound.play()
            
            while channel.get_busy():
                # CHECK: Stop if user pressed ESC or new ID appeared
                if stop_speaking or my_id != speech_id_counter:
                    channel.stop()
                    break
                time.sleep(0.05)

        except Exception as e:
            print(f"Playback Error: {e}")
        finally:
            set_ui_state("idle")

    speech_thread = threading.Thread(target=run_wrapper, daemon=True)
    speech_thread.start()

# 
def stopSpeaking():
    global stop_speaking
    stop_speaking = True
    if pygame.mixer.get_init():
        pygame.mixer.stop()       # Stops all active Sound channels
        pygame.mixer.music.stop() # Stops any background music

# Bind Hotkey to stop speaking
k.add_hotkey('esc', stopSpeaking)

def okSir():
    speak("Okay sir")
    return 

# --- UPDATED SYSTEM PROMPT ---
def init_chat():
    global chat_history
    chat_history = [
        {
            "role": "user", 
            "parts": [{"text": "You are CYPHER, a stylish, empathetic, and witty AI assistant inspired by F.R.I.D.A.Y. from Iron Man. You have deep knowledge of Indian history and Vedic wisdom. Speak in a mix of English and Hindi (Hinglish) when appropriate, and always address the user as 'Sir'."}]
        },
        {
            "role": "model", 
            "parts": [{"text": "Namaste Sir. Systems are online. I am Cypher, ready to assist."}]
        }
    ]

init_chat()

def reset_chat():
    init_chat()
    speak("Memory Cleared. Starting fresh.")

def aiProcess(prompt):
    global chat_history
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        chat_history.append({"role": "user", "parts": [{"text": prompt}]})
        
        # Using Flash model for speed and stability
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=chat_history
        )
        reply = response.text.strip().replace("*", "").replace("#", "").replace("`", "")
        chat_history.append({"role": "model", "parts": [{"text": reply}]})
        return reply

    except Exception as e:
        print(f"AI Error: {e}")
        if chat_history and chat_history[-1]["role"] == "user":
            chat_history.pop()
        return "I cannot connect to the brain, sir."
    
# thinking phase 
thinking_phrases = [
    "Hmm… let me think, Sir.",
    "Processing that, Sir.",
    "Interesting question… one moment.",
    "Let me access the archives, Sir.",
    "Analyzing now…"
]

def thinking_speaker():
    global ai_thinking
    ai_thinking = True

    phrase = random.choice(thinking_phrases)
    speak(phrase)

    # Wait silently while AI works
    while ai_thinking:
        time.sleep(0.1)


def run_ai(prompt):
    global ai_result, ai_thinking
    try:
        ai_result = aiProcess(prompt)
    finally:
        ai_thinking = False


def speak_while_thinking(prompt):
    global ai_thread, ai_result
    ai_result = None   # 🔥 RESET

    ai_thread = threading.Thread(
        target=run_ai,
        args=(prompt,),
        daemon=True
    )
    ai_thread.start()

    thinking_thread = threading.Thread(
        target=thinking_speaker,
        daemon=True
    )
    thinking_thread.start()

    ai_thread.join()

    stopSpeaking()

    if ai_result:
        speak(ai_result)


def speakToText(retries=3):
    set_ui_state("listening")
    for _ in range(retries):
        with sr.Microphone() as source:
            try:
                # Optimized: No adjustment loop here (handled globally/once)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                set_ui_state("processing")
                # en-IN for Indian accent support
                text = recognizer.recognize_google(audio, language="en-IN")
                ui_print(f"USER: {text}")
                return text
            except sr.UnknownValueError:
                speak("I didn't catch that, Sir.")
            except Exception as e:
                print(f"Mic Error: {e}")
                break
    set_ui_state("idle")
    return ""

# to open application 
def openCommand(c):
    if "chrome" in c.lower():
        okSir()
        pyautogui.hotkey('win','s')
        time.sleep(1)
        pyautogui.write("chrome", interval=0.1)
        k.press_and_release('enter')
    elif "whatsapp" in c.lower():
        okSir()
        pyautogui.hotkey('win','s')
        time.sleep(1)
        pyautogui.write("whatsapp", interval=0.1)
        k.press_and_release('enter')
    elif "copilot" in c.lower():
        okSir()
        pyautogui.hotkey('win','s')
        time.sleep(1)
        pyautogui.write("copilot", interval=0.1)
        k.press_and_release('enter')
    elif "edge" in c.lower():
        okSir()
        pyautogui.hotkey('win','s')
        time.sleep(1)
        pyautogui.write("edge", interval=0.1)
        k.press_and_release('enter')
    elif "notepad" in c.lower():
        okSir()
        pyautogui.hotkey('win','s')
        time.sleep(1)
        pyautogui.write("notepad", interval=0.1)
        k.press_and_release('enter')
    elif "vs code" in c.lower():
        okSir()
        pyautogui.hotkey('win','s')
        time.sleep(1)
        pyautogui.write("visual studio code", interval=0.1)
        k.press_and_release('enter')
    elif "file" in c.lower():
        okSir()
        pyautogui.hotkey("win", 'e')
        time.sleep(1)
    elif "phone link" in c.lower():
        okSir()
        pyautogui.hotkey("win",'s')
        time.sleep(1)
        pyautogui.write("phone link", interval=0.1)
        k.press_and_release('enter')
    elif "word" in c.lower():
        okSir()
        pyautogui.hotkey("win",'s')
        time.sleep(1)
        pyautogui.write("word", interval=0.1)
        k.press_and_release('enter')
    elif "excel" in c.lower():
        okSir()
        pyautogui.hotkey("win",'s')
        time.sleep(1)
        pyautogui.write("excel", interval=0.1)
        k.press_and_release('enter')
    elif "powerpoint" in c.lower():
        okSir()
        pyautogui.hotkey("win",'s')
        time.sleep(1)
        pyautogui.write("powerpoint", interval=0.1)
        k.press_and_release('enter')
    elif "calculator" in c.lower():
        okSir()
        pyautogui.hotkey("win", 'r')
        time.sleep(1)
        pyautogui.write("calc", interval=0.1)
        k.press_and_release('enter')
    elif "task manager" in c.lower():
        okSir()
        pyautogui.hotkey("ctrl", 'shift', 'esc')
        time.sleep(1)
    elif "cmd" in c.lower():
        okSir()
        pyautogui.hotkey("win", 'r')
        time.sleep(1)
        pyautogui.write("cmd", interval=0.1)
        k.press_and_release('enter')
    elif "new tab" in c.lower():
        okSir()
        pyautogui.hotkey("ctrl", 't')
    elif "previous tab" in c.lower():
        okSir()
        pyautogui.hotkey("ctrl", 'shift', 't')
    elif "new window" in c.lower():
        okSir()
        pyautogui.hotkey("ctrl", 'n')
    elif "new incognito window" in c.lower():
        okSir()
        pyautogui.hotkey("ctrl", 'shift', 'n')
    else:
        okSir()
        openApp(c)

def openApp(app):
    try:
        appName = app.lower().replace("open", "").strip()
        pyautogui.hotkey("win",'s')
        time.sleep(0.5)
        pyautogui.write(appName, interval=0.1)
        k.press_and_release('enter')
    except:
        speak("I couldn't identify the application name.")

def processCommand(c):
    ui_print(f"Processing: {c}")
    links = {
        "google": "https://www.google.com",
        "facebook": "https://www.facebook.com",
        "youtube": "https://www.youtube.com",
        "linkedin": "https://www.linkedin.com",
        "gmail": "https://mail.google.com",
        "instagram": "https://www.instagram.com",
        "github": "https://www.github.com",
        "internshala": "https://internshala.com",
        "indeed": "https://www.indeed.com"
    }
    if "google" in c.lower():
        webbrowser.open(links["google"])
    elif "facebook" in c.lower():
        webbrowser.open(links["facebook"])
    elif "youtube" in c.lower():
        webbrowser.open(links["youtube"])
    elif "linkedin" in c.lower():
        webbrowser.open(links["linkedin"])
    elif "gmail" in c.lower():
        webbrowser.open(links["gmail"])
    elif "instagram" in c.lower():
        webbrowser.open(links["instagram"])
    elif "github" in c.lower():
        webbrowser.open(links["github"])
    elif "internshala" in c.lower():
        webbrowser.open(links["internshala"])
    elif "indeed" in c.lower():
        webbrowser.open(links["indeed"])
    elif "open" in c.lower():
        openCommand(c)
    elif "close window" in c.lower():
        pyautogui.hotkey('alt', 'f4')
    elif "close tab" in c.lower():
        pyautogui.hotkey('ctrl', 'w')
    elif "volume up" in c.lower():
        pyautogui.press('volumeup')
    elif "volume down" in c.lower():
        pyautogui.press('volumedown')
    elif "volume mute" in c.lower():
        pyautogui.press('volumemute')
    elif "brightness up" in c.lower():
        pyautogui.press('brightnessup')
    elif "brightness down" in c.lower():
        pyautogui.press('brightnessdown')
    elif "lock" in c.lower():
        pyautogui.hotkey("win", 'l')
    elif "sleep" in c.lower():
        pyautogui.hotkey("win", 'x')
        time.sleep(1)
        pyautogui.press('u')
        time.sleep(1)
        pyautogui.press('s')
    elif "shutdown" in c.lower():
        pyautogui.hotkey("win", 'x')
        time.sleep(1)
        pyautogui.press('u')
        time.sleep(1)
        pyautogui.press('u')
    elif "restart" in c.lower():
        pyautogui.hotkey("win", 'x')
        time.sleep(1)
        pyautogui.press('u')
        time.sleep(1)
        pyautogui.press('r')
    elif "log off" in c.lower():
        pyautogui.hotkey("win", 'l')
    elif "save file" in c.lower():
        pyautogui.hotkey("ctrl", "s")
    elif "select all" in c.lower():
        pyautogui.hotkey("ctrl", "a")
    elif "copy" in c.lower():
        pyautogui.hotkey("ctrl", "c")
    elif "paste" in c.lower():
        pyautogui.hotkey("ctrl", "v")
    elif "cut" in c.lower():
        pyautogui.hotkey("ctrl", "x")
    elif "find" in c.lower():
        pyautogui.hotkey("ctrl", "f")
    elif "type" in c.lower():
        if c.lower()=="type what i say":
            speak("What do you want to type?")
            text=speakToText()
            pyautogui.typewrite(text)
            pyautogui.press("enter")
    elif "weather" in c.lower():
        city=c.split("in")[-1].strip() if "in" in c.lower() else "Mumbai"
        weather_info = getWeather(city)
        speak(weather_info)
    elif "send email" in c.lower():
        sendMail()
    elif "check email" in c.lower() or "read email" in c.lower():
        check_emails()
    elif "news" in c.lower():
        news_info = getNews()
        speak(news_info)
    elif "switch window" in c.lower():
        pyautogui.hotkey("alt", 'tab')
    elif c.lower() in ["stop", "stop speaking"]:
        stopSpeaking()
    elif "send message on whatsapp" in c.lower():
        sendWhatsAppMessage()
    elif "wikipedia" in c.lower():
        speak("what is the topic?")
        c = speakToText()
        result = search_wikipedia(c)
        speak(result)
    elif "new session" in c.lower() or "reset chat" in c.lower() or "clear history" in c.lower():
        reset_chat()
    elif "time" in c.lower():
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        speak(f"The current time is {current_time}")
    elif "date" in c.lower():
        today = datetime.now()
        current_date = today.strftime("%B %d, %Y")
        speak(f"Today's date is {current_date}")
    elif "day" in c.lower():
        day = datetime.now()
        current_day = day.strftime("%A")
        speak(f"Today is {current_day}")
    elif "are you there" in c.lower():
        speak("Yes sir, I am here.")
    elif "turn off" in c.lower():
        shutdown_sequence()
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
        "System hibernation initiated. Goodbye."
    ]
    
    # Select a random message from the list
    choice = random.choice(farewell_messages)
    speak(choice)
    
    # Close the GUI if it is running
    if close_callback:
        close_callback()

# fetching email from database
def get_email_from_db(name_spoken):
    conn = sqlite3.connect('contact.db')
    cursor = conn.cursor()
    # diverse query to handle partial matches
    cursor.execute("SELECT email FROM email_contacts WHERE LOWER(name) LIKE ?", ('%' + name_spoken.lower().strip() + '%',))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else speak("I couldn't find that contact in the database.")

# send mail function
def sendMail():
    speak("Whom do you want to email?")
    name = speakToText()
    
    if not name:
        speak("I didn't hear a name.")
        return

    email_address = get_email_from_db(name)
    
    if email_address:
        mail_subject = getMailSubject()
        if not mail_subject: return # Stop if no subject heard
        
        mail_body = getMailBody()
        if not mail_body: return # Stop if no body heard
        
        # Proceed with sending email to email_address
        send_email_smtp(email_address, mail_subject, mail_body)
    else:
        speak(f"I couldn't find an email for {name}")

# mail body
def getMailBody():
    speak("What should I say in the email?")
    body = speakToText()
    return body
# mail subject
def getMailSubject():
    speak("What is the subject of the email?")
    subject = speakToText()
    return subject
def send_email_smtp(to_address, subject, body):
    from_address = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")
    
    message = f"Subject: {subject}\n\n{body}"
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
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
        
        # Connect to Gmail IMAP
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
        mail.select("inbox")
        
        # Search for unread emails
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()
        
        if not email_ids:
            speak("You have no new emails, Sir.")
            return

        count = len(email_ids)
        speak(f"You have {count} new emails.")

        # Read the latest 3 emails
        for i in range(min(3, count)):
            latest_email_id = email_ids[-(i+1)] # Get latest first
            _, msg_data = mail.fetch(latest_email_id, "(RFC822)")
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Decode Subject
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    # Decode Sender
                    from_ = msg.get("From")
                    
                    speak(f"Email {i+1} from {from_}. Subject: {subject}")
        
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
    headers = {
        "User-Agent": "MyWeatherApp/1.0"
    }
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

    if response['status'] == 'success':
        articles = response['results']
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
    conn = sqlite3.connect('contact.db')
    cursor = conn.cursor()
    cursor.execute("SELECT phone_number FROM contacts WHERE LOWER(name) LIKE ?", ('%' + name_spoken.lower().strip() + '%',))
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
    name = speakToText()
    
    if not name:
        speak("I didn't hear a name.")
        return

    phone_number = get_whatsapp_number_from_db(name)
    
    if not phone_number:
        speak(f"I couldn't find a phone number for {name}")
        return

    speak("What is the message?")
    message = speakToText()
    
    if not message:
        speak("I didn't hear a message.")
        return

    send_whatsapp_message(phone_number, message)

def send_whatsapp_message(phone_number, message):
    speak("Sending message...")
    speak("Waiting for 30 seconds to send the message.")
    wb.sendwhatmsg_instantly(phone_number, message, wait_time=20, tab_close=False)
    time.sleep(0.1) 
    pyautogui.hotkey('enter') 
    speak("Message sent successfully.")
    pyautogui.hotkey('ctrl', 'w') 

# wikipedia search function
def search_wikipedia(topic):
    if not topic:
        return "I didn't catch the topic, sir."
    
    clean_topic = topic.lower().replace("search wikipedia for", "").replace("who is", "").replace("what is", "").replace("wikipedia", "").strip()
    speak(f"Searching global database for {clean_topic}...")
    
    try:
        topic_encoded = urllib.parse.quote(clean_topic)
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic_encoded}"
        headers = {"User-Agent": "CypherAssistant/1.0"}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if "extract" in data:
                print(data["extract"])
                return data["extract"]
            
        return f"I could not find any specific records for {clean_topic} in the database."

    except Exception as e:
        print(e)
        return "Connection to Wikipedia failed, sir."

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
                # --- FIX: Correctly wait for speech to finish ---
                # Checks if the assistant is currently speaking and waits
                while speech_thread and speech_thread.is_alive():
                    time.sleep(0.1)

                audio = recognizer.listen(source, timeout=1, phrase_time_limit=3) 
                
                set_ui_state("processing") 
                word = recognizer.recognize_google(audio, language="en-IN").lower()

                if "turn off" in word:
                    shutdown_sequence()
                    return
                
                if "cypher" in word:
                    activate_msg = ["Yes, Sir?", "At your service.", "I'm here, Sir.", "Ready, Sir."]
                    speak(random.choice(activate_msg))
                    active = True
                    
                    while active and is_running:
                        try:
                            # --- FIX: Inner loop wait ---
                            # Wait for "Yes Sir?" or previous answer to finish
                            while speech_thread and speech_thread.is_alive():
                                time.sleep(0.1)

                            print("CYPHER Active...")
                            set_ui_state("listening") 
                            audio_cmd = recognizer.listen(source, timeout=3, phrase_time_limit=5)
                            
                            set_ui_state("processing") 
                            command = recognizer.recognize_google(audio_cmd, language="en-IN").lower()
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
                if is_running: set_ui_state("idle")


if __name__ == "__main__":
    check_env_variable()
    activateAssistant()