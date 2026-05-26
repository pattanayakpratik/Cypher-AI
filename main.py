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
import threading
import sounddevice as sd
from dotenv import load_dotenv
import sqlite3
from newsdataapi import NewsDataApiClient
import edge_tts
import asyncio
from datetime import datetime, timedelta
import random
import io
import imaplib
import email
from email.header import decode_header
import json
import speedtest
from groq import Groq
import wikipedia
import re
from faster_whisper import WhisperModel
import sounddevice as sd
import numpy as np

load_dotenv()

# --- CONSTANTS & DICTIONARIES ---
ERROR_THRESHOLD = 300
HISTORY_FILE = "chat_memory.json"

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
    "take screenshot": ["printscreen"],
    "open emoji": ["win", "."],
    "mute microphone": ["win", "alt", "k"]
}

MEDIA_KEYS = {
    "volume up": "volumeup",
    "volume down": "volumedown",
    "volume mute": "volumemute",
    "mute": "volumemute",
    "play music": "playpause",
    "pause music": "playpause",
    "next song": "nexttrack",
    "previous song": "prevtrack",
    "brightness up": "brightnessup",
    "brightness down": "brightnessdown"
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

class CypherCore:
    def __init__(self):
        # UI Callbacks
        self.ui_print = print
        self.close_callback = None
        self.ui_state_callback = None
        
        # System Flags
        self.is_running = False
        self.stop_speaking_flag = False
        self.speech_id_counter = 0
        self.chat_history = []
        
        # API Clients
        self.gemini_client = None
        self.groq_client = None

        # Threading & Concurrency
        self.speech_thread = None
        self.speech_lock = threading.Lock()
        self.alarm_event = threading.Event()

        # --- NEW OFFLINE AUDIO SETUP ---
        self.ui_print("Booting AI Audio Models (This takes a moment...)")
        self.stt_model = WhisperModel("base.en", device="cpu", compute_type="int8")

        # Wikimedia Setup
        wikipedia.set_lang("en")

        # TTS Event Loop
        self.tts_loop = asyncio.new_event_loop()
        threading.Thread(target=self._start_tts_loop, daemon=True).start()

        # Hotkeys
        k.add_hotkey("esc", self.stop_speaking)

        # Pygame Mixer Setup
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            pygame.mixer.init(frequency=24000, channels=1)
        except Exception as e:
            print("Pygame Mixer Initialization Error:", e)

    def _start_tts_loop(self):
        """Starts the asyncio event loop for TTS in a separate thread."""
        asyncio.set_event_loop(self.tts_loop)
        self.tts_loop.run_forever()

    def set_callbacks(self, ui_print_fn, close_fn, state_fn):
        """Sets the UI callbacks for printing, closing, and state updates."""
        if ui_print_fn: 
            self.ui_print = ui_print_fn
        if close_fn: 
            self.close_callback = close_fn
        if state_fn: 
            self.ui_state_callback = state_fn

    def set_ui_state(self, state):
        """Updates the UI state through the callback."""
        if self.ui_state_callback:
            self.ui_state_callback(state)

    def stop_execution(self):
        """Stops all ongoing processes, including speech and resets flags."""
        self.is_running = False
        self.stop_speaking_flag = True
        if pygame.mixer.get_init():
            pygame.mixer.stop()
        self.ui_print("System halting...")

    def stop_speaking(self):
        """Sets the flag to stop any ongoing speech and halts audio playback."""
        self.stop_speaking_flag = True
        if pygame.mixer.get_init():
            pygame.mixer.stop()
            pygame.mixer.music.stop()

    def ok_sir(self):
        self.speak("Okay sir")

    def check_env_variable(self):
        """Checks for required environment variables and initializes API clients."""
        self.ui_print("Performing system checks...")
        required_keys = [
            "GEMINI_API_KEY", 
            "GROQ_API_KEY", 
            "OPENWEATHER_KEY", 
            "NEWS_API_KEY", 
            "EMAIL_USER", 
            "EMAIL_PASS"
        ]
        missing_keys = [key for key in required_keys if not os.getenv(key)]
        
        if missing_keys:
            self.ui_print(f"Warning: The following environment variables are missing: {', '.join(missing_keys)}")
        
        if os.getenv("GEMINI_API_KEY"):
            self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        if os.getenv("GROQ_API_KEY"):
            self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            
        if not os.path.exists("contact.db"):
            self.ui_print("Warning: contact.db database file is missing.")
        self.init_db()

    def init_db(self):
        """Initializes the SQLite database and creates necessary tables if they don't exist."""
        conn = sqlite3.connect("contact.db")
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, phone_number TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS email_contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, email TEXT)''')
        conn.commit()
        conn.close()

    def add_contact(self):
        """Guides the user through adding a new contact, either a WhatsApp number or an email address, and saves it to the database."""
        self.speak("Do you want to save a WhatsApp number, or an Email address?")
        self.wait_until_silent()
        contact_type = self.listen().lower()
        
        if not contact_type: 
            return
            
        if "whatsapp" in contact_type or "number" in contact_type or "phone" in contact_type:
            self.speak("What is the name of the contact?")
            self.wait_until_silent()
            name = self.listen()
            if not name:
                self.speak("I didn't catch the name. Cancelling.")
                return
                
            self.speak("What is the phone number?")
            self.wait_until_silent()
            number_spoken = self.listen()
            
            clean_number = "".join(filter(str.isdigit, number_spoken))
            
            if len(clean_number) > 10 and clean_number.startswith("91"):
                clean_number = clean_number[2:]
            elif len(clean_number) == 11 and clean_number.startswith("0"):
                clean_number = clean_number[1:]

            if not re.match(r"^[6-9]\d{9}$", clean_number):
                self.speak("That doesn't seem to be a valid 10-digit mobile number. Cancelling.")
                return
                
            try:
                conn = sqlite3.connect("contact.db")
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM contacts WHERE name=?", (name.lower(),))
                if cursor.fetchone():
                    cursor.execute("UPDATE contacts SET phone_number=? WHERE name=?", (clean_number, name.lower()))
                    self.speak(f"Updated existing WhatsApp number for {name}.")
                else:
                    cursor.execute("INSERT INTO contacts (name, phone_number) VALUES (?, ?)", (name.lower(), clean_number))
                    self.speak(f"Successfully saved WhatsApp number for {name}.")
                conn.commit()
            except sqlite3.Error as e:
                self.speak("A database error occurred.")
                print(f"DB Error: {e}")
            finally:
                if 'conn' in locals(): 
                    conn.close()
            
        elif "email" in contact_type:
            self.speak("What is the name of the contact?")
            self.wait_until_silent()
            name = self.listen()
            if not name:
                self.speak("I didn't catch the name. Cancelling.")
                return
                
            self.speak("What is the email address? Say 'at' and 'dot' where appropriate.")
            self.wait_until_silent()
            email_spoken = self.listen().lower()
            
            clean_email = email_spoken.replace(" at ", "@").replace(" dot ", ".").replace(" ", "")
            pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
            if not re.match(pattern, clean_email):
                self.speak("That email address format is invalid. Cancelling.")
                return
            
            try:
                conn = sqlite3.connect("contact.db")
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM email_contacts WHERE name=?", (name.lower(),))
                if cursor.fetchone():
                    cursor.execute("UPDATE email_contacts SET email=? WHERE name=?", (clean_email, name.lower()))
                    self.speak(f"Updated existing email address for {name}.")
                else:
                    cursor.execute("INSERT INTO email_contacts (name, email) VALUES (?, ?)", (name.lower(), clean_email))
                    self.speak(f"Successfully saved email address for {name}.")
                conn.commit()
            except sqlite3.Error as e:
                self.speak("A database error occurred.")
                print(f"DB Error: {e}")
            finally:
                if 'conn' in locals(): 
                    conn.close()
            
        else:
            self.speak("I didn't understand the contact type. Please try again.")

    def speak(self, text):
        """Converts text to speech using edge-tts, plays it back, and handles interruption and UI state updates."""
        with self.speech_lock:
            if pygame.mixer.get_init():
                pygame.mixer.stop()
                pygame.mixer.music.stop()

            self.speech_id_counter += 1
            my_id = self.speech_id_counter
            self.stop_speaking_flag = False

        self.set_ui_state("processing")

        def run_wrapper():
            """Wrapper function to run TTS and playback in a separate thread."""
            target_source = io.BytesIO()
            try:
                communicate = edge_tts.Communicate(text, "hi-IN-SwaraNeural", rate="+20%")
                async def collect_audio():
                    async for chunk in communicate.stream():
                        if my_id != self.speech_id_counter: 
                            return
                        if chunk["type"] == "audio":
                            target_source.write(chunk["data"])

                future = asyncio.run_coroutine_threadsafe(collect_audio(), self.tts_loop)
                future.result()

                if my_id != self.speech_id_counter: 
                    return
                target_source.seek(0)
            except Exception as e:
                self.set_ui_state("idle")
                return

            try:
                if not pygame.mixer.get_init():
                    self.set_ui_state("idle")
                    return
                    
                sound = pygame.mixer.Sound(file=target_source)

                if my_id != self.speech_id_counter: 
                    return
                self.ui_print(f"CYPHER: {text}")
                
                channel = pygame.mixer.Channel(0)
                channel.play(sound)

                while channel.get_busy():
                    if self.stop_speaking_flag or my_id != self.speech_id_counter:
                        channel.stop()
                        break
                    time.sleep(0.05)
            except Exception as e:
                print(f"Playback Error: {e}")
            finally:
                if my_id == self.speech_id_counter:
                    self.set_ui_state("idle")

        self.speech_thread = threading.Thread(target=run_wrapper, daemon=True)
        self.speech_thread.start()

    def wait_until_silent(self):
        """Blocks until the current speech has finished playing or is interrupted."""
        if self.speech_thread and self.speech_thread.is_alive():
            self.speech_thread.join(timeout=10)

    def listen(self, duration=5):
        self.set_ui_state("listening")
        fs = 16000
        
        try:
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
            sd.wait()
            
            self.set_ui_state("processing")
            audio_data = np.squeeze(recording)
            segments, info = self.stt_model.transcribe(audio_data, beam_size=5)
            text = "".join([segment.text for segment in segments]).strip()
            
            self.ui_print(f"USER: {text}")
            self.set_ui_state("idle")
            return text
            
        except Exception as e:
            print(f"Mic Error: {e}")
            self.set_ui_state("idle")
            return ""

    def save_memory(self):
        """Saves the current chat history to a JSON file, ensuring that the history does not exceed a certain length to manage memory effectively."""
        MAX_HISTORY = 30
        if len(self.chat_history) > MAX_HISTORY:
            self.chat_history = self.chat_history[:4] + self.chat_history[-(MAX_HISTORY - 4):]
            
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self.chat_history, f)
        except Exception as e:
            print(f"Memory Save Error: {e}")

    def load_memory(self):
        """Loads the chat history from a JSON file if it exists, otherwise initializes a new chat history. Handles potential corruption of the memory file gracefully."""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    self.chat_history = json.load(f)
                print("Previous chat history loaded.")
                return
            except Exception as e:
                print("Memory corrupted, starting fresh.")
        self.init_chat()

    def init_chat(self):
        """Initializes the chat history with a predefined system prompt and user instructions to set the tone and behavior of the AI assistant."""
        self.chat_history = [
            {"role": "user", "parts": [{"text": "You are CYPHER, a stylish, empathetic, and witty AI assistant. Speak in a mix of English and Hindi (Hinglish) when appropriate, and always address the user as 'Sir'."}]},
            {"role": "model", "parts": [{"text": "Namaste Sir. Systems are online. I am Cypher, ready to assist."}]},
            {"role": "user", "parts": [{"text": "You are CYPHER, created by Pratik Pattanayak."}]},
            {"role": "user", "parts": [{"text": "CRITICAL RULE: You must always give extremely short, punchy, and direct responses. NEVER exceed 1 or 2 sentences unless I explicitly ask you for a detailed explanation. Do not use markdown formatting. Be quick and conversational."}]},
        ]

    def reset_chat(self):
        """Clears the current chat history and resets it to the initial system prompt, effectively starting a new conversation with a clean slate."""
        self.init_chat()
        self.save_memory()
        self.speak("Memory Cleared. Starting fresh.")

    def ai_process(self, prompt):
        """Processes the user's prompt through the Gemini API, with a fallback to the Groq API in case of failure. Updates the chat history and handles errors gracefully, ensuring that the user is informed of any connectivity issues with the AI modules."""
        if not self.gemini_client and not self.groq_client:
            return "System Warning: Both primary and backup AI modules are missing their API keys."
        
        self.chat_history.append({"role": "user", "parts": [{"text": prompt}]})
        
        try:
            if not self.gemini_client:
                raise Exception("Gemini Client not initialized.")
                
            response = self.gemini_client.models.generate_content(
                model="gemini-2.5-flash", contents=self.chat_history
            )
            reply = response.text.strip().replace("*", "").replace("#", "").replace("`", "")
            
            self.chat_history.append({"role": "model", "parts": [{"text": reply}]})
            self.save_memory()
            return reply

        except Exception as gemini_error:
            print(f"Gemini Brain Offline ({gemini_error}). Switching to Groq Backup...")
            
            try:
                if not self.groq_client:
                    raise Exception("Groq Client not initialized.")
                    
                groq_history = []
                for msg in self.chat_history:
                    role = "assistant" if msg["role"] == "model" else "user"
                    content = msg["parts"][0]["text"]
                    groq_history.append({"role": role, "content": content})
                    
                groq_response = self.groq_client.chat.completions.create(
                    messages=groq_history,
                    model="llama-3.3-70b-versatile" 
                )
                
                reply = groq_response.choices[0].message.content.strip().replace("*", "").replace("#", "").replace("`", "")
                
                self.chat_history.append({"role": "model", "parts": [{"text": reply}]})
                self.save_memory()
                return reply
                
            except Exception as groq_error:
                print(f"Groq Brain Offline: {groq_error}")
                if self.chat_history and self.chat_history[-1]["role"] == "user":
                    self.chat_history = self.chat_history[:-1]
                return "I have lost connection to both my primary and backup servers, sir."

    def speak_while_thinking(self, prompt):
        """Processes the user's prompt through the AI and speaks the response, ensuring that the UI state is updated appropriately and that the user is informed of any delays or issues with the AI response generation."""
        res = self.ai_process(prompt)
        if res:
            self.speak(res)
            self.wait_until_silent()

    def open_app(self, app):
        """Attempts to open an application by simulating keyboard input to search for the app in the Windows Start menu. Handles potential errors gracefully and informs the user if the application cannot be opened."""
        try:
            pyautogui.hotkey("win", "s")
            time.sleep(0.15) 
            pyautogui.write(app, interval=0.01) 
            time.sleep(0.15) 
            k.press_and_release("enter")
        except Exception as e:
            print(e)
            self.speak("Unable to open application.")

    def greet(self):
        """Generates a greeting based on the current time of day and speaks it to the user, setting a friendly and personalized tone for the interaction."""
        hour = int(datetime.now().hour)
        greeting = ""
        if hour >= 0 and hour < 5:
            greeting = "You are up late, Sir."
        elif hour >= 5 and hour < 12:
            greeting = "Good Morning, Sir."
        elif hour >= 12 and hour < 18:
            greeting = "Good Afternoon, Sir."
        else:
            greeting = "Good Evening, Sir."
        self.speak(f"{greeting} I am Cypher. How may I assist you?")

    def shutdown_sequence(self):
        """Speaks a random farewell message from a predefined list, waits for the speech to finish, and then triggers the close callback to shut down the system gracefully."""
        farewell_messages = [
            "Powering down all systems. Have a productive day, Sir.",
            "Disconnecting from the mainframe. Namaste, Sir.",
            "Shutting down. I will be ready when you need me next.",
            "Going offline. Take care, Sir.",
            "System hibernation initiated. Goodbye.",
        ]
        choice = random.choice(farewell_messages)
        self.speak(choice)
        self.wait_until_silent()
        if self.close_callback:
            self.close_callback()

    def get_email_from_db(self, name_spoken):
        """Retrieves an email address from the database based on the spoken name. Handles database errors gracefully and informs the user if a database error occurs."""
        try:
            conn = sqlite3.connect("contact.db")
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM email_contacts WHERE LOWER(name) = ?", (name_spoken.lower().strip(),))
            result = cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            print(f"Database Error: {e}")
            self.speak("A database error occurred while retrieving the email address.")
            return None
        finally:
            if 'conn' in locals(): 
                conn.close()

    def send_mail(self):
        """Guides the user through sending an email by first asking for the recipient's name, retrieving the email address from the database, and then prompting for the subject and body of the email. Finally, it sends the email using SMTP and handles any errors that may occur during the process."""
        self.speak("Whom do you want to email?")
        self.wait_until_silent()
        name = self.listen()
        if not name:
            self.speak("I didn't hear a name.")
            return

        email_address = self.get_email_from_db(name)

        if email_address:
            while True:
                self.wait_until_silent()
                mail_subject = self.get_mail_subject()
                if mail_subject:
                    break

            while True:
                self.wait_until_silent()
                mail_body = self.get_mail_body()
                if mail_body: 
                    break

            self.send_email_smtp(email_address, mail_subject, mail_body)
        else:
            self.speak(f"I couldn't find an email for {name}")

    def get_mail_body(self):
        """Prompts the user for the body of the email, waits for the user to finish speaking, and then returns the transcribed text. Handles cases where the user does not provide any input."""
        self.speak("What should I say in the email?")
        self.wait_until_silent()
        return self.listen()

    def get_mail_subject(self):
        """Prompts the user for the subject of the email, waits for the user to finish speaking, and then returns the transcribed text. Handles cases where the user does not provide any input."""
        self.speak("What is the subject of the email?")
        self.wait_until_silent()
        return self.listen()

    def send_email_smtp(self, to_address, subject, body):
        """Sends an email using the SMTP protocol with the provided recipient address, subject, and body. Handles authentication using environment variables for the email credentials and manages potential errors during the sending process, ensuring that the user is informed of the success or failure of the email delivery."""
        from_address = os.getenv("EMAIL_USER")
        password = os.getenv("EMAIL_PASS")
        if not from_address or not password:
            self.speak("Email credentials are not configured in the environment variables.")
            return
        message = f"Subject: {subject}\n\n{body}"
        server = None
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(from_address, password)
            server.sendmail(from_address, to_address, message)
            self.speak("Email has been sent successfully.")
        except Exception as e:
            print(e)
            self.speak("Sorry, I was unable to send the email.")
        finally:
            if server: 
                server.quit()

    def check_emails(self):
        """Checks for new emails in the user's inbox using the IMAP protocol, retrieves the subject and sender of the latest unread emails, and speaks this information to the user. Handles authentication using environment variables for the email credentials and manages potential errors during the email retrieval process, ensuring that the user is informed of any issues accessing their inbox."""
        user = os.getenv("EMAIL_USER")
        password = os.getenv("EMAIL_PASS")
        
        if not user or not password:
            self.speak("Email credentials are not configured.")
            return
        
        try:
            self.speak("Checking for new emails, Sir...")
            self.wait_until_silent()

            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(user, password)
            mail.select("inbox")

            status, messages = mail.search(None, "UNSEEN")
            email_ids = messages[0].split()

            if not email_ids:
                self.speak("You have no new emails, Sir.")
                self.wait_until_silent()
                return

            count = len(email_ids)
            self.speak(f"You have {count} new emails.")
            self.wait_until_silent()
            if count > 3:
                self.speak("Reading the latest 3 emails. subject and sender only, Sir.")
                self.wait_until_silent()

            for i in range(min(3, count)):
                latest_email_id = email_ids[-(i + 1)] 
                _, msg_data = mail.fetch(latest_email_id, "(RFC822)")

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject_parts = decode_header(msg["Subject"])
                        subject = "".join([
                            (part[0].decode(part[1] or "utf-8") if isinstance(part[0], bytes) else str(part[0]))
                            for part in subject_parts
                        ])

                        from_header = msg.get("From")
                        if from_header:
                            from_parts = decode_header(from_header)
                            from_ = "".join([
                                (part[0].decode(part[1] or "utf-8") if isinstance(part[0], bytes) else str(part[0]))
                                for part in from_parts
                            ])
                            if "<" in from_:
                                from_ = from_.split("<")[0].strip().replace('"', "")
                        else:
                            from_ = "Unknown"

                        self.speak(f"Email {i+1} from {from_}. Subject: {subject}")
                        self.wait_until_silent()
                        time.sleep(0.5)

            self.speak("That is all for now, Sir.")

        except Exception as e:
            print(e)
            self.speak("I encountered an error while accessing your inbox, Sir.")
        finally:
            if 'mail' in locals():
                try:
                    mail.close()
                    mail.logout()
                except: 
                    pass

    def get_weather(self, city):
        """Fetches the current weather information for a specified city using the OpenWeather API. Handles potential errors such as missing API keys, city not found, and network issues gracefully, providing informative feedback to the user in each case."""
        try:
            api_key = os.getenv("OPENWEATHER_KEY")
            if not api_key:
                return "Error: OpenWeather API key is missing from the environment variables."

            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
            headers = {"User-Agent": "CypherVoiceAssistant/1.0"}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 404:
                return f"I'm sorry, I couldn't find any weather data for the city {city}."
                
            if response.status_code == 200:
                data = response.json()
                city_name = data['name']
                temp = round(data['main']['temp'])
                description = data['weather'][0]['description']
                humidity = data['main']['humidity']
                wind_speed = data['wind']['speed']
                return f"Currently in {city_name}, it is {temp} degrees Celsius with {description}. The humidity is at {humidity} percent, with a wind speed of {wind_speed} meters per second."
            else:
                return "There was an error communicating with the weather server."
                
        except requests.exceptions.RequestException as e:
            return "I am currently unable to connect to the weather network. Please check your internet connection."
        except Exception as e:
            return "Sorry, I encountered an internal error while fetching the weather."

    def get_news(self):
        """Fetches the latest news headlines using the NewsData API. Handles potential errors such as missing API keys, issues with the API response, and network problems gracefully, providing informative feedback to the user in each case."""
        try:
            api = NewsDataApiClient(apikey=os.getenv("NEWS_API_KEY"))
            response = api.latest_api(country="in", language="en")

            if response.get("status") == "success":
                articles = response.get("results", [])
                news_brief = "Here are the top news headlines. "
                for i in range(min(5, len(articles))):
                    news_brief += f"{i+1}. {articles[i]['title']}. "
                print(news_brief)
                return news_brief
            else:
                return "Sorry, I could not fetch the news at this moment."
                
        except Exception as e:
            print(f"News API Error: {e}")
            return "Unable to fetch news right now due to a network error."

    def get_whatsapp_number_from_db(self, name_spoken):
        """Retrieves a WhatsApp number from the database based on the spoken name. Cleans and formats the phone number to ensure it is in the correct format for sending messages. Handles database errors gracefully and informs the user if a database error occurs."""
        try:
            conn = sqlite3.connect("contact.db")
            cursor = conn.cursor()
            cursor.execute("SELECT phone_number FROM contacts WHERE LOWER(name) = ?", (name_spoken.lower().strip(),))
            result = cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Database Error: {e}")
            return None
        finally:
            if 'conn' in locals(): 
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

    def prompt_whatsapp_message(self):
        """Guides the user through sending a WhatsApp message by first asking for the recipient's name, retrieving the phone number from the database, and then prompting for the message content. Finally, it sends the message using the pywhatkit library and handles any errors that may occur during the process."""
        self.speak("Whom do you want to send message?")
        self.wait_until_silent()
        name = self.listen()

        if not name:
            self.speak("I didn't hear a name.")
            return

        phone_number = self.get_whatsapp_number_from_db(name)

        if not phone_number:
            self.speak(f"I couldn't find a phone number for {name}")
            return

        self.speak("What is the message?")
        self.wait_until_silent()
        message = self.listen()

        if not message:
            self.speak("I didn't hear a message.")
            return

        threading.Thread(target=self.send_whatsapp_message, args=(phone_number, message), daemon=True).start()

    def send_whatsapp_message(self, phone_number, message):
        self.speak("Sending message...")
        try:
            # We import it here so it doesn't crash the app on startup!
            import pywhatkit as wb 
            wb.sendwhatmsg_instantly(phone_number, message, wait_time=15, tab_close=True, close_time=3)
            self.speak("Message sent successfully.")
        except Exception as e:
            print(f"WhatsApp/Internet Error: {e}")
            self.speak("Sorry, I am unable to connect to WhatsApp at the moment. Please check the internet connection.")

    def search_wikipedia(self, topic):
        """Searches Wikipedia for a given topic and returns a brief summary. Handles potential errors such as disambiguation, page not found, and network issues gracefully, providing informative feedback to the user in each case."""
        if not topic:
            return "I didn't catch the topic, sir."
        try:
            result = wikipedia.summary(topic, sentences=2)
            return f"According to Wikipedia: {result}"
        except wikipedia.exceptions.DisambiguationError:
            return "There are too many different results for that topic. Please be more specific."
        except wikipedia.exceptions.PageError:
            return "I couldn't find any matching page on Wikipedia, sir."
        except Exception as e:
            print(f"Wikipedia Error: {e}")
            return "Connection to Wikipedia failed, sir."  

    def check_internet_speed(self):
        """Checks the current internet speed using the speedtest library and returns the download speed, upload speed, and ping. Handles potential errors during the speed test process gracefully and informs the user if the internet speed check fails."""
        try:
            self.speak("Checking internet speed, please wait...")
            self.wait_until_silent()
            st = speedtest.Speedtest()
            st.get_best_server()
            download_speed = st.download(threads=1) / 1_000_000
            upload_speed = st.upload(threads=1) / 1_000_000
            ping = st.results.ping
            return f"Download {download_speed:.1f} Mbps, Upload {upload_speed:.1f} Mbps, Ping {ping:.0f} ms"
        except Exception as e:
            print(e)
            return "Internet speed check failed, sir."

    def set_alarm(self, time_str):
        """Sets an alarm for a specified time in HH:MM format. The alarm will trigger a spoken notification when the time is reached. Handles potential errors in time parsing and ensures that the alarm can be cancelled if needed."""
        self.alarm_event.clear()
        def alarm_worker():
            try:
                now = datetime.now()
                alarm_datetime = datetime.strptime(time_str, "%H:%M")
                alarm_datetime = alarm_datetime.replace(year=now.year, month=now.month, day=now.day)

                if alarm_datetime <= now:
                    alarm_datetime += timedelta(days=1)

                sleep_seconds = (alarm_datetime - datetime.now()).total_seconds()
                was_cancelled = self.alarm_event.wait(timeout=sleep_seconds)

                if not was_cancelled:
                    self.speak("Alarm ringing, Sir!")
            except Exception as e:
                print(f"Alarm Error: {e}")
                self.speak("Failed to set alarm, sir.")
        threading.Thread(target=alarm_worker, daemon=True).start()

    def process_command(self, c):
        """Processes a user command by checking for various triggers and executing the corresponding actions. Handles a wide range of commands including opening websites, executing hotkeys, controlling media playback, managing applications, fetching information, and more. Provides feedback to the user for each action taken and ensures that the UI state is updated appropriately throughout the process."""
        c_lower = c.lower()
        self.ui_print(f"Processing: {c}")

        # Check for web links first
        for site, url in WEB_LINKS.items():
            if site in c_lower:
                self.speak(f"Opening {site}, Sir.")
                self.wait_until_silent()
                return webbrowser.open(url)

        # Check for hotkeys next
        for trigger, keys in HOTKEYS.items():
            if trigger in c_lower:
                self.speak(f"Executing {trigger}, Sir.")
                self.wait_until_silent()
                return pyautogui.hotkey(*keys)

        # Check for media controls
        for key, media_key in MEDIA_KEYS.items():
            if key in c_lower:
                self.speak("Right away, Sir.")
                self.wait_until_silent()
                return pyautogui.press(media_key)

        # Check for application openings
        if "open" in c_lower:
            app_name = c_lower.replace("open", "").strip()
            actual_app_name = APPS_NAMES.get(app_name, app_name)
            self.speak(f"Opening {actual_app_name}, Sir.")
            self.wait_until_silent()
            self.open_app(actual_app_name)
            
        # Check for typing command
        elif "type what i say" in c_lower:
            self.speak("What do you want to type?")
            self.wait_until_silent()
            text = self.listen()
            if text:
                pyautogui.typewrite(text)
                pyautogui.press("enter")
                
        # Check for sleep command
        elif "put on sleep" in c_lower:
            pyautogui.hotkey("win", 'x')
            time.sleep(0.2)
            pyautogui.press('u')
            time.sleep(0.2)
            pyautogui.press('s')
            
        # Check for shutdown command
        elif "shutdown" in c_lower:
            self.speak("Are you sure you want to shut down the computer, Sir? Say yes to confirm.")
            self.wait_until_silent()
            confirmation = self.listen()
            if confirmation and "yes" in confirmation.lower():
                self.speak("Shutting down.")
                os.system("shutdown /s /t 1")
            else:
                self.speak("Shutdown cancelled.") 
            
        # Check for restart command
        elif "restart" in c_lower:
            self.speak("Are you sure you want to restart the system, Sir? Say yes to confirm.")
            self.wait_until_silent()
            confirmation = self.listen()
            if confirmation and "yes" in confirmation.lower():
                self.speak("Restarting.")
                os.system("shutdown /r /t 1")
            else:
                self.speak("Restart cancelled.")
            
        # Check for weather command
        elif "weather" in c_lower:
            city = c_lower.split("in")[-1].strip() if "in" in c_lower else "Mumbai"
            res = self.get_weather(city)
            self.speak(res)
            self.wait_until_silent()
            
        # Check for send email command
        elif "send email" in c_lower:
            self.send_mail()
            
        # Check for check email command
        elif "check email" in c_lower or "read email" in c_lower:
            self.check_emails()
            
        # Check for check internet speed command
        elif "check internet speed" in c_lower:
            self.speak(self.check_internet_speed())
            self.wait_until_silent()
            
        # Check for news command
        elif "news" in c_lower:
            self.speak(self.get_news())
            self.wait_until_silent()
            
        # Check for send WhatsApp message command
        elif "send message on whatsapp" in c_lower:
            self.prompt_whatsapp_message()
        
        # Check for add contact command
        elif "add contact" in c_lower or "save contact" in c_lower or "new contact" in c_lower:
            self.add_contact()
            
        # Check for Wikipedia search command
        elif "wikipedia" in c_lower:
            topic = re.sub(r"(search wikipedia for|wikipedia|who is|what is)", "", c_lower).strip()
            if not topic:
                self.speak("What is the topic?")
                self.wait_until_silent()
                topic = self.listen()
                
            if topic:
                self.speak(f"Searching Wikipedia for {topic}, Sir.")
                self.wait_until_silent()
                self.speak(self.search_wikipedia(topic))
                self.wait_until_silent()
                
        # Check for conversational words
        elif any(phrase in c_lower for phrase in ["new session", "reset chat", "clear history"]):
            self.reset_chat()

        # Check for time, date, and day commands
        elif "time" in c_lower:
            self.speak(f"The current time is {datetime.now().strftime('%H:%M')}")
            
        elif "date" in c_lower:
            self.speak(f"Today's date is {datetime.now().strftime('%B %d, %Y')}")
            
        elif "day" in c_lower:
            self.speak(f"Today is {datetime.now().strftime('%A')}")

        # Check for presence confirmation
        elif "are you there" in c_lower:
            self.speak("Yes sir, I am here.")
            
        # Check for stop commands
        elif "turn off" in c_lower or "stop" in c_lower:
            if "stop speaking" in c_lower or c_lower.strip() == "stop":
                self.stop_speaking()
            else:
                self.shutdown_sequence()

        # Check for alarm commands
        elif "set alarm" in c_lower:
            self.speak("At what time should I set the alarm, Sir? Please say it in HH:MM format.")
            self.wait_until_silent()
            alarm_time = self.listen()
            alarm_time = alarm_time.replace(" ", "").replace(".", ":")
            try:
                datetime.strptime(alarm_time, "%H:%M")
                self.speak(f"Setting alarm for {alarm_time}, Sir.")
                self.set_alarm(alarm_time)
            except ValueError:
                self.speak("I received an invalid time format. Cancelling alarm.")
                
        # Check for cancel/stop alarm commands
        elif "cancel alarm" in c_lower or "stop alarm" in c_lower:
            self.alarm_event.set()
            self.speak("The active alarm has been cancelled, Sir.")
        
        # If no specific command is recognized, check if the input is conversational or if it should be processed as a general query to the AI
        else:
            conversational_words = ["hello", "hi", "hey", "thanks", "yes", "no", "why", "who", "what", "wow"]
            if len(c.split()) < 2 and c_lower not in conversational_words:
                self.speak("Could you please be more specific, Sir?")
                self.wait_until_silent()
            else:
                self.set_ui_state("processing")
                self.speak_while_thinking(c)
def activate_assistant(self):
        self.is_running = True
        self.greet()
        self.ui_print("Sensors Online. Say 'Cypher' to activate.")

        fs = 16000
        wake_duration = 1.5 # 1.5 seconds is the perfect length for a wake word
        
        while self.is_running:
            self.set_ui_state("idle")
            try:
                # 1. Listen for 1.5 seconds
                recording = sd.rec(int(wake_duration * fs), samplerate=fs, channels=1, dtype='float32')
                sd.wait()
                audio_data = np.squeeze(recording)
                
                # 2. Transcribe it instantly (beam_size=1 makes it lightning fast)
                segments, info = self.stt_model.transcribe(audio_data, beam_size=1)
                text = "".join([segment.text for segment in segments]).lower().strip()
                
                # 3. Check if your name was spoken!
                # (Including common phonetic spellings Whisper might guess)
                if "cypher" in text or "cipher" in text or "saifer" in text:
                    self.set_ui_state("listening")
                    
                    activate_msg = ["Yes, Sir?", "At your service.", "I'm here, Sir.", "Ready, Sir."]
                    self.speak(random.choice(activate_msg))
                    self.wait_until_silent()
                    
                    # 4. Now listen for the actual command
                    command = self.listen(duration=5)
                    
                    if command:
                        if "stop listening" in command.lower() or "go to sleep" in command.lower():
                            self.speak("Entering standby mode.")
                        elif "turn off" in command.lower():
                            self.shutdown_sequence()
                            break
                        else:
                            self.process_command(command)
                            
            except Exception as e:
                # Silently ignore empty audio chunks or mic stutters
                time.sleep(0.1)
# Main execution
if __name__ == "__main__":
    core = CypherCore()
    core.check_env_variable()
    core.load_memory()
    core.activate_assistant()