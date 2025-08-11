# AudioToText

<div align="center">
  <h1>Telegram Audio‑to‑Text Bot</h1>
  <p><strong>Send audio/voice → process → get text (Speaker 1 / Speaker 2).</strong> Task queue, statuses, long‑text splitting, and gentle anti‑spam.</p>
  <p>
    <a href="#"><img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white"></a>
    <a href="#"><img alt="aiogram" src="https://img.shields.io/badge/aiogram-2.x-2C2D72"></a>
    <a href="#"><img alt="Selenium" src="https://img.shields.io/badge/Selenium-automated-43B02A?logo=selenium&logoColor=white"></a>
    <a href="#"><img alt="Audio" src="https://img.shields.io/badge/Audio-pydub-6BA539"></a>
  </p>
</div>

---

## 📚 Table of Contents

- [About](#about)
- [Problem It Solves](#problem)
- [Features](#features)
- [How It Works](#how)
- [Commands & UI](#ui)
- [Technical Highlights](#tech)
- [Security & Data](#privacy)
- [Limitations](#limits)
- [Roadmap](#roadmap)
- [Author](#author)

## 🧭 About <a id="about"></a>

A Telegram bot that accepts audio files (MP3/OGG/WAV/WMA) and voice messages, processes them, and returns a text transcript. Handy for quick notes, interviews, meetings, and podcasts.

This project was designed with **sales/support call analysis** in mind: turn a conversation into a **clean, speaker‑tagged transcript (Speaker 1 / Speaker 2)** and then feed it to an LLM (e.g., ChatGPT) to highlight coaching opportunities and mistakes.

> Portfolio edition focuses on architecture and UX, without deployment instructions.

## 🧠 Problem It Solves <a id="problem"></a>

- Teams struggle to review calls because manual transcription is slow and fragmented.
- This bot removes the friction: upload audio in Telegram → get a **high‑quality, speaker‑tagged** transcript → send to ChatGPT for **post‑call analysis** (objections, missed cues, next steps).
- Result: faster feedback loops, better training for managers/agents.

## ✨ Features <a id="features"></a>

- **Formats:** MP3, OGG, WAV, WMA, and Telegram voice messages.
- **Speaker tags:** dialogue transcripts labeled as **Speaker 1 / Speaker 2** for easier analysis.
- **Task queue:** multiple files go to a FIFO queue and are processed sequentially.
- **ETA hint:** rough waiting‑time estimate based on audio duration.
- **Processing toggle:** a switch to enable extra pre‑processing ("Parse with AI").
- **Statuses & notifications:** progress and completion updates.
- **Long texts:** smart splitting into chunks (up to 4096 chars each).
- **Cancellation:** users can cancel an in‑progress task.
- **LLM‑ready export:** transcript arrives in a format that’s easy to drop into ChatGPT for evaluation of mistakes and improvement points.

## ⚙️ How It Works <a id="how"></a>

1. The user sends audio/voice.
2. The bot saves the file, detects duration, and enqueues a FIFO task.
3. Via browser automation the bot uploads the file to a speech‑to‑text service and starts transcription.
4. When ready, the text is fetched and sent back (split into parts if needed).
5. Temporary files are removed.
6. _(Optional for coaching)_ The bot formats the transcript as an **LLM‑ready prompt** you can paste into ChatGPT to analyze manager performance and extract action items.

## 💬 Commands & UI <a id="ui"></a>

- **/start** — greeting and a keyboard with “Parse with AI” and “Cancel”.
- **“Parse with AI”** — enables/disables extra pre‑processing.
- **“Cancel”** — stops the current task.

## 🧩 Technical Highlights <a id="tech"></a>

- **Stack:** Python 3.12, aiogram 2.x, Selenium (headless Chrome), pydub, Faker.
- **Queue:** custom FIFO queue with background processing and status messages.
- **Transcription:** integration via browser automation (Selenium); recognition language — Russian (extensible).
- **UX details:** smooth status updates ("transcribing…"), careful long‑reply splitting, gentle anti‑spam cooldown.

## 🛡️ Security & Data <a id="privacy"></a>

- Temporary audio files are stored locally during processing and then removed.
- No user data is shared with third parties for marketing.
- Keep secrets/tokens in **environment variables** and exclude them from the repo.

## 🚧 Limitations <a id="limits"></a>

- Dependency on the external speech‑to‑text service availability/stability.
- **Per‑file length limit:** the free tier supports \~30 minutes per audio file; the current scheme allows an unlimited number of tasks.
- The current version uses synchronous browser automation; for higher loads, move to workers and `asyncio.Queue`/a message queue.

## 🗺️ Roadmap <a id="roadmap"></a>

- Migrate to aiogram 3.x and `asyncio.Queue`.
- Persistent queue (Redis/RQ) and workers for background jobs.
- Language selection in UI.
- Switch to ASR APIs (Whisper/Deepgram/Vosk/Cloud) as an alternative to browser automation.
- Built‑in **LLM analysis flow** (auto‑send transcript to ChatGPT/OpenAI API, scorecards, checklists).
- Rich statuses (ETA/progress), throttling, and retries.

## 👤 Author <a id="author"></a>

**Vlad Khoroshylov** — Instagram: **@vlad.khoro**.

> This repository is for portfolio purposes and to showcase the architecture/UX approach to “audio → text”. A banner and demo GIF can be added later under `docs/`.
