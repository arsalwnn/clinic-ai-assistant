# Clinic AI Assistant

A Persian-language Telegram assistant for a pain-management clinic. It answers questions about the clinic using Retrieval-Augmented Generation (RAG), escalates risky messages to a human, and collects appointment requests that the clinic secretary confirms or rejects directly from Telegram.

> **Status:** working proof of concept. All clinic details in this repository are placeholders ("Dr. X"). This is **not** a medical device: it does not diagnose, and it does not recommend medication.

## Features

- **Persian Q&A over a clinic knowledge base**: opening hours, services, required documents, FAQs. Answers are grounded in retrieved text (Gemini embeddings + Chroma); if the answer is not in the knowledge base, the bot says so and refers the patient to the secretary instead of guessing.
- **Safety-first routing**: a deterministic red-flag keyword layer runs *before* any LLM call. Emergency symptoms and self-harm messages get a fixed, reviewed reply and an immediate alert to the secretary.
- **Intent classification**: an LLM classifies the remaining messages as `emergency`, `appointment`, `complaint`, `medical`, or `general`.
- **Guided appointment requests**: a step-by-step booking flow (name, phone, preferred time, reason, confirmation) with phone-number validation. It is a plain state machine, not an LLM, so it behaves predictably.
- **Human in the loop**: the secretary receives alerts in Telegram with inline *Confirm / Reject* buttons, and the patient is notified of the decision. The bot never promises a booking on its own.
- **Guardrails**: the prompt forbids diagnoses, drugs, and doses, and invites the patient to an in-person visit instead.

## How a message is handled

```mermaid
flowchart TD
    P["Patient (Telegram)"] --> B["telegram_bot.py"]
    B --> L["bot_logic.py: handle_message"]
    L --> R{"Red-flag or self-harm keywords?"}
    R -- yes --> E["Fixed emergency reply + secretary alert"]
    R -- no --> S{"Booking session active?"}
    S -- yes --> A["Booking state machine"]
    S -- no --> C["LLM intent classifier"]
    C -- emergency --> E
    C -- appointment --> A
    C -- complaint --> K["Empathetic reply + secretary alert"]
    C -- "medical / general" --> G["RAG: retrieve from Chroma, answer with Gemini"]
    A --> D[("appointments.csv")]
    A --> N["Secretary alert with Confirm / Reject buttons"]
```

## Tech stack

- Python (developed on 3.13)
- LangChain, Google Gemini (generation: `gemini-3.5-flash-lite`, embeddings: `gemini-embedding-001`)
- Chroma (local vector store)
- python-telegram-bot
- arabic-reshaper + python-bidi (only for readable Persian output in the terminal)

## Project structure

```
.
├── rag_core.py                # knowledge base ingestion, retriever, RAG answer
├── bot_logic.py               # red-flag layer, intent routing, booking flow
├── telegram_bot.py            # Telegram handlers, secretary alerts and buttons
├── clinic_info.example.txt    # sample knowledge base (copy to clinic_info.txt)
├── .env.example               # required environment variables
├── requirements.txt
└── README.md
```

## Setup

```bash
git clone https://github.com/arsalwnn/clinic-ai-assistant.git
cd clinic-ai-assistant

python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1      Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
```

1. Copy `.env.example` to `.env` and fill in the values below.
2. Copy `clinic_info.example.txt` to `clinic_info.txt` and edit it with the clinic's real information.
3. Optional: test retrieval in the terminal with `python rag_core.py`.
4. Run the bot:

```bash
python telegram_bot.py
```

### Environment variables

| Variable | Description |
|---|---|
| `GOOGLE_API_KEY` | Gemini API key from Google AI Studio |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `SECRETARY_CHAT_ID` | Telegram chat id that receives alerts and approves appointments (send `/myid` to the bot to find yours) |

If the Google API or Telegram is not reachable from your network, set `HTTP_PROXY` and `HTTPS_PROXY` in your shell before running.

When you change `clinic_info.txt` or the embedding model, delete the `chroma_db/` folder so the index is rebuilt.

## Design decisions

- **Safety rules are deterministic and run first.** Whether a message is an emergency should not depend on a model's judgment alone. The keyword list errs on the side of over-alerting.
- **Booking is a state machine.** It collects personal data and must be reliable and validated, so no LLM is involved.
- **Appointment requests, not bookings.** The secretary has the final say, which avoids double-booking and keeps a human accountable.
- **Knowledge base is plain text.** Adapting the assistant to another clinic means editing one file.
- **The vector index is persisted**, so documents are embedded once instead of on every start.

## Evaluation
All tests use small, hand-written Persian test sets.
Results show the prototype behaves as designed; they are not clinical validation.

| Component | Test set | Metric | Result |
|---|---|---|---|
| Red-flag layer | N emergency / self-harm messages | Recall | X/N |
| Red-flag layer | N ordinary messages | False-alert rate | X/N |
| Intent classifier | N messages, 5 classes | Accuracy | X% |
| RAG answers | N in-KB questions | Correct & grounded | X/N |
| Abstention | N out-of-KB questions | Correct "not in KB" | X/N |
| Booking flow | N unit tests | Passed | X/N |


## Known issues and engineering notes

- **Response latency and overlapping messages.** In informal testing with a
  few real users, each request took about 10 seconds (slow Gemini embedding
  calls were a significant contributor). Users who saw no reply assumed the
  bot had stalled and sent follow-up messages ("what happened?"). Because the
  previous request was still being processed, the bot answered these follow-ups
  out of context, producing off-target replies.
  **Mitigation:** when a new message arrives from a user whose previous message
  has not been answered yet, the bot waits about 5-6 seconds and then processes
  the new message as a separate, independent request. This reduced the problem.
  **Limitation:** this is a simple delay-based workaround, not proper per-user
  concurrency control. Messages are still handled independently, so a follow-up
  such as "what happened?" is not linked to the earlier question. Planned
  improvements: a per-user message queue or lock, async handling, an immediate
  "processing..." acknowledgment, and a faster (e.g. local multilingual)
  embedding model.
- **Network access in the development environment.** Reaching Telegram and the
  Gemini API required a VPN/proxy, which caused intermittent connection drops
  during development. This was addressed by using a more stable VPN rather than
  in code; timeout and retry handling is planned.


## Limitations and roadmap

- The red-flag keyword list is a starting point and **must be reviewed by a physician** before any real use.
- Appointments are stored in a local CSV; Google Sheets / Calendar integration is planned.
- Conversation state is kept in memory and is lost on restart.
- No consent flow or data-retention policy yet. The CSV contains patient names and phone numbers in plain text, which must be addressed before real use.
- Only Telegram is implemented; a WhatsApp channel is planned.

## Disclaimer

This project is a technical demo. It is not a medical device and must not be used for diagnosis or treatment decisions. In an emergency, contact local emergency services (115 in Iran).

## Author

AmirArsalan Rezaianzadeh · [GitHub](https://github.com/arsalwnn) · [LinkedIn](https://www.linkedin.com/in/amirarsalan-rezaian-zadeh-a8ab10426)
