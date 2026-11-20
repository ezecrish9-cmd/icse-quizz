# 📚 ICSE 10th Quiz Telegram Bot

> **"I am designed exclusively for ICSE 10TH"**

A lightweight, asynchronous Telegram bot built with **Python 3.14** and `python-telegram-bot` (v22+). It supports both **Solo Practice in Direct Messages (DM)** with instant question progression and **Live Multiplayer Tournaments in Groups** with separated Global Leaderboards.

---

## 🌟 Game Modes

### 1. 🎯 Solo Practice in DM (Personal Chat)
- **Instant Progression:** In private DM, you don't wait for a 20-second timer. The moment you answer a question, the bot gives you 1.5s to view the explanation and automatically sends the next question!
- **Interactive Dashboard:** Accessible via `/start` with 1-click buttons:
  - `[🚀 Play Solo Quiz]`
  - `[📅 Daily Quiz Pack]`
  - `[🏆 Global Leaderboards]`
  - `[👤 My Performance Profile]`
  - `[➕ Add Me to a Group]`
- **ICSE Report Card:** Displays your score out of 5, accuracy percentage, correct/incorrect count, and your updated **Worldwide Solo Rank**, plus `[🔁 Play Again]` for instant replays.

### 2. ⚔️ Multiplayer Group Tournaments
- Triggered by `/quiz` or `/start` inside any Telegram group.
- **Slash Command Autocomplete:** Typing `/` in any group immediately pops up the bot's command menu.
- **Anti-Hijack Protection:** Only the initiator or group admins can select the subject and topic.
- Timed native Telegram Quiz polls (20s countdown per question).
- Live podium celebration (🥇 1st, 2nd, 3rd) and persistent group standings.

### 3. 📅 Daily Quiz Pack (`/dailyquiz` or `/daily`)
- Pulls 1 question from each of the 9 ICSE subjects (9 questions total).
- **Untimed:** Solved at your own pace without any countdown timer, in both DM and groups.

---

## 📚 Supported ICSE 10th Subjects

All questions are tailored strictly to the official ICSE Class 10 curriculum:

1. ⚡ **PHYSICS** (*Mechanics, Work & Energy*, *Light, Sound & Electricity*)
2. 📐 **MATHS** (*Commercial Mathematics & Algebra*, *Geometry, Trigonometry & Mensuration*)
3. 🧬 **BIOLOGY** (*Cell Cycle & Genetics*, *Human & Plant Physiology*)
4. 🧪 **CHEMISTRY** (*Periodic Table & Chemical Bonding*, *Acids, Metallurgy & Organic Chemistry*)
5. 📜 **HISTORY** (*Indian National Movement*, *Contemporary World & UN*)
6. 🌍 **GEOGRAPHY** (*Climate & Soils of India*, *Resources & Agriculture*)
7. 💻 **COMPUTER** (*Java OOP Basics*, *Arrays & String Handling*)
8. 🎭 **ENGLISH 2 (Literature)**
   - **Prose (Treasure Chest Class 10):**
     - *With the Photographer* (Stephen Leacock)
     - *The Elevator* (William Sleator)
     - *The Girl Who Can* (Ama Ata Aidoo)
     - *The Pedestrian* (Ray Bradbury)
     - *The Last Lesson* (Alphonse Daudet)
   - **Poetry (Treasure Chest Class 10):**
     - *Haunted Houses* (H.W. Longfellow)
     - *The Glove and the Lions* (Leigh Hunt)
     - *When Great Trees Fall* (Maya Angelou)
     - *A Considerable Speck* (Robert Frost)
     - *The Power of Music* (Sukumar Ray)
   - **Julius Caesar:** Shakespeare's Acts 3, 4, 5
9. ✍️ **ENGLISH 1 (Language)** (*Grammar & Prepositions*, *Transformation of Sentences*)

---

## 📜 Commands Autocomplete (Type `/` in Chat)

Commands registered automatically on startup:

| Command | Description |
| :--- | :--- |
| `/quiz` | Start an ICSE quiz tournament in groups, or solo practice in DM |
| `/dailyquiz` | Send daily 1-question pack from all 9 subjects (untimed) |
| `/leaderboard` | View group standings or worldwide Solo/Tournament champions |
| `/mystats` | View your personal report card, points, and ranks |
| `/stopquiz` | Stop the active quiz round |
| `/help` | View ICSE syllabus and bot instructions |

---

## 🚀 How to Run the Bot

Double-click **`start_bot.bat`** in the project folder, or run:
```powershell
& "C:\Users\EzeCr\AppData\Local\Python\bin\python.exe" run.py
```
