# 🧠 Cypher Voice Assistant 

**Cypher** is a futuristic, voice-activated AI assistant designed to automate tasks, control your PC, and provide intelligent responses using Google's Gemini AI. It features a sci-fi GUI inspired by Iron Man's F.R.I.D.A.Y., complete with a rotating core and hacker-style terminal.

## ⚡ Topics & Features

Cypher is equipped with a wide range of modules to handle daily tasks:

### 🤖 **Core AI**

* **Generative Intelligence:** Powered by **Google Gemini 1.5 Flash** for fast, witty, and context-aware conversations.
* **Voice Interaction:** Uses `SpeechRecognition` for listening and `Edge-TTS` for a high-quality, neural Indian-English voice (F.R.I.D.A.Y. style).
* **Wake Word Detection:** Activates specifically on the keyword **"Cypher"**.

### 🖥️ **Graphical Interface (GUI)**

* **Futuristic Design:** Built with **PyQt5**, featuring a transparent window and "Glassmorphism" aesthetic.
* **Live Animations:** A rotating reactor core that changes color based on status (Idle, Listening, Processing).
* **System Diagnostics:** Real-time HUD displaying CPU usage, RAM, Battery, and Network speeds.
* **Terminal Log:** A "hacker-style" typing log that displays internal processes and conversation history.

### 🛠️ **System Automation**

* **App Control:** Open any application (Chrome, VS Code, Notepad, Calculator, etc.).
* **Window Management:** Switch tabs, close windows, minimize/maximize.
* **Hardware Control:** Adjust Volume, Brightness, and Lock/Shutdown/Restart the PC.
* **Typing Mode:** Dictate text directly into any text field ("Type what I say").

### 🌐 **Online Connectivity**

* **Information Retrieval:** Fetches real-time **Weather** and **News** headlines.
* **Knowledge Base:** Searches **Wikipedia** for instant summaries of any topic.
* **Web Navigation:** Opens websites like Google, YouTube, LinkedIn, GitHub, etc.

### 📨 **Communication**

* **Email:** Sends emails using SMTP and reads unread emails from your Inbox (IMAP).
* **WhatsApp:** Sends automated WhatsApp messages to contacts in your database.

---

## 📂 Project Structure

```text
voiceAssistance/
│
├── main.py             # Core Logic (AI, Voice, Commands)
├── gui.py              # User Interface (PyQt5, Animations)
├── contact.db          # SQLite Database for Phone/Emails
├── .env                # API Keys (Keep this private!)
├── image.png           # Reactor Core Image asset
└── font/               # Custom Sci-Fi Fonts

```

---

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/YourUsername/Cypher-AI-Assistant.git
cd Cypher-AI-Assistant

```

### 2. Install Dependencies

Make sure you have Python installed. Then run:

```bash
pip install -r requirements.txt

```

*(Common libs: `pyqt5`, `speechrecognition`, `google-generativeai`, `pygame`, `edge-tts`, `pyautogui`, `psutil`)*

### 3. Configure Environment Variables

Create a `.env` file in the root folder and add your API keys:

```ini
GEMINI_API_KEY=your_gemini_key_here
OPENWEATHER_KEY=your_weather_key_here
NEWS_API_KEY=your_news_key_here
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_app_password

```

### 4. Setup Database

Ensure `contact.db` exists with a table `contacts` (name, phone_number) and `email_contacts` (name, email) for the communication features to work.

### 5. Run Cypher

Start the GUI (which automatically loads the backend):

```bash
python gui.py

```

---

## 🎮 Usage Guide

* **Start:** Click **"INITIATE PROTOCOL"** on the GUI.
* **Wake Up:** Say **"Cypher"** to grab her attention.
* **Commands:**
* *"Open VS Code"*
* *"What is the weather in Mumbai?"*
* *"Search Wikipedia for Artificial Intelligence"*
* *"Send an email to [Name]"*
* *"Turn off"* (Initiates shutdown sequence)



---

## 🛡️ Future Improvements

* [ ] **Vision Mode:** Analyze screen content using Gemini Vision.
* [ ] **Offline Wake Word:** Integrate Porcupine for faster wake-word detection.
* [ ] **Media Controls:** Spotify/YouTube Playback control.

---

**Built with 💙 by [Pratik Pattanayak]**
