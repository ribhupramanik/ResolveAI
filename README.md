<div align="center">

# ResolveAI

### Evidence-grounded AI customer support, with human-approved actions

**A full-stack RAG application that combines semantic retrieval, live order data, response validation, and auditable customer-support workflows.**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Frontend-149ECA?logo=react&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?logo=postgresql&logoColor=white)
![pgvector](https://img.shields.io/badge/pgvector-Vector_Search-6C63FF)
![Docker](https://img.shields.io/badge/Docker-Local_DB-2496ED?logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/Status-Portfolio_Demo-6366F1)

**[Try the Live Demo](https://resolve-ai-omega-lime.vercel.app/)**

**[Explore the architecture](#system-architecture) · [See the demo workflow](#demo-walkthrough) · [Run locally](#getting-started) · [Explore the API](#api-overview)**

**Live Demo:** [Try ResolveAI](https://resolve-ai-omega-lime.vercel.app/)

**Deployment:** React on Vercel · FastAPI on Northflank · PostgreSQL + pgvector on Neon · LLM inference via Groq

</div>

---

## The problem

A customer-support assistant should do more than write plausible-sounding replies. It needs to **retrieve relevant information, check live operational records, respect business rules, and avoid claiming an action happened when it did not**.

Generic chatbots can answer questions fluently while missing the actual order status, inventing a tracking number, or implying that a refund has already been initiated when the system has only checked eligibility.

**ResolveAI** is an engineering-focused customer-support prototype built to address those problems. It brings together a retrieval-augmented generation (RAG) pipeline, structured database tools, application-level response validation, and explicit confirmation for state-changing actions.

The project is designed as both a functioning application and an **inspectable AI-engineering demo**: evaluators can create controlled order scenarios in the browser, ask questions about those orders, and inspect the AI's tool usage and validation results.

## At a glance

| Capability                    | What ResolveAI demonstrates                                                                        |
| ----------------------------- | -------------------------------------------------------------------------------------------------- |
| Retrieval-augmented responses | Contextual retrieval over embedded customer-support examples and verified knowledge                |
| Live operational grounding    | Order and refund information obtained through database-backed tools                                |
| Guarded generation            | First-pass validation, a targeted retry when needed, and a deterministic safe fallback             |
| Human-in-the-loop actions     | Explicit Confirm/Reject flow before supported cancellations and refund initiation                  |
| State consistency             | Transactional execution, eligibility rechecks, and audit records                                   |
| Explainable demo UI           | Response-validation status, tool execution, evidence counts, model/provider and correction details |
| Scenario management           | Create, view, edit, delete, and test demo orders without manually managing IDs                     |
| Test coverage                 | Backend regression tests for APIs, action lifecycles, error cases and integrity protections        |

> **Operational boundary:** Refund initiation in ResolveAI is an **internal database workflow**, not a charge reversal through a live bank, payment processor, or courier service. Tracking details come from stored order records; there is no live carrier-location feed.

## Product screenshots

### Conversational assistance and AI Intelligence

![ResolveAI chat interface showing order lookup and response validation](docs/screenshots/chat-intelligence.png)

The Chat view includes conversation history, response content, pending-action controls when applicable, and an **AI Intelligence** panel showing tool usage and response-validation diagnostics.

### Recruiter-facing Order Scenario Manager

![ResolveAI order scenario manager](docs/screenshots/orders-manager.png)

The Orders view surfaces current orders and differentiates **seeded** records from **demo-managed** records. Recruiters can search, copy an order number, inspect its details, edit eligible demo records, and safely request deletion.

### Create a controlled order scenario

![ResolveAI create order form with estimated delivery date picker](docs/screenshots/order-creation.png)

Creation supports configurable order/payment status, amounts, shipping details and scenario presets. The backend generates the **order number and demo customer** automatically when they are not supplied.

---

## Key features

### 1. Retrieval-augmented generation

- Uses customer-support text embedded into a **384-dimensional vector space**.
- Stores embeddings in PostgreSQL with the **pgvector** extension.
- Assembles relevant retrieved context, verified knowledge, system capabilities, prior conversation history and operational tool results into generation prompts.
- Keeps factual data retrieval separate from model-generated wording.
- Includes a local ingestion pipeline; a completed local ingestion run populated **18,780 embedded support-ticket records**. This is a dataset/ingestion count, **not** a model accuracy result.

### 2. Grounded tool-assisted answers

The backend routes supported operational questions to tools that can retrieve authoritative data. Implemented operations include:

- **Order lookup:** status, payment status, amount, carrier, tracking number and estimated delivery.
- **Cancellation eligibility:** whether the order may be cancelled under the current business rules.
- **Refund eligibility:** whether a refund can be requested, with amount/currency context.
- **Refund status:** status of an existing internal refund record.

The assistant can explain **what is known** and **what is missing**. A `shipped` order without a carrier or estimated delivery should not be presented as having verified tracking details.

### 3. Response validation, correction and fallback

ResolveAI does not automatically trust its first generated response.

1. Generate a response using retrieved and operational evidence.
2. Validate the response against the available facts and allowed capabilities.
3. If validation rejects it, create a **second prompt with targeted corrective guidance**.
4. Validate the second response.
5. If both attempts fail, return a **fixed safe fallback** instead of presenting an unverified answer.

The validation logic includes checks for unsupported operational claims, such as implying that a refund was initiated when the tool only checked **refund eligibility**. The UI distinguishes **passed on first attempt**, **passed after retry**, and **safe fallback used**, with expandable correction details.

This is an application-level guardrail system. It reduces specific classes of unsupported responses; it does **not** guarantee that all hallucinations are impossible.

### 4. Human-approved actions and audit history

Some support interactions are **read-only**. Others could change persistent order state. ResolveAI treats those differently.

- An eligibility check is **not** an executed cancellation or initiated refund.
- Supported actions enter a **pending** state and require explicit user confirmation.
- Users can **Confirm** or **Reject** a pending action.
- Execution services recheck business conditions and record outcomes.
- Action status and execution audit data are stored in PostgreSQL.
- Refund records include status and transaction metadata; they represent internal workflow state, not real-money movement.

This separation helps prevent an LLM-generated statement from being confused with a completed business operation.

### 5. Interactive demo orders and presets

The React Order Scenario Manager lets an evaluator:

- Automatically create a customer and numeric `ORD-...` identifier.
- Choose **processing**, **shipped**, **delivered**, or **cancelled** order state.
- Set payment status, amount, currency and shipping address.
- Optionally add a carrier, tracking number and estimated delivery date using a calendar control.
- View full order details, edit an eligible demo record, or delete it after confirmation.
- Copy order numbers, or prepare an order-specific question via **Test in Chat**.
- Select prefilled scenarios for cancellation eligibility, refund eligibility, available tracking and missing tracking data.

Seeded orders are distinguished from demo-created records. **Deletion** is restricted by the API to demo-managed orders without refund or action history. **Editing** has additional history checks; public access restrictions for write operations remain a deployment task.

---

## System architecture

```mermaid
flowchart TD
    U[Recruiter / support user] --> FE[React + Vite frontend]
    FE --> API[FastAPI REST API]
    API --> CHAT[Conversation service]
    API --> DEMO[Demo order management]
    API --> DB[(PostgreSQL)]
    CHAT --> RAG[ResolveAI pipeline]
    RAG --> ROUTER[Operational tool router]
    ROUTER --> DB
    RAG --> RETRIEVAL[Semantic and verified-knowledge retrieval]
    RETRIEVAL --> VECTOR[(pgvector: 384-d embeddings)]
    VECTOR --- DB
    RAG --> PROMPT[Evidence-aware prompt builder]
    PROMPT --> GEN[Groq-hosted language model]
    GEN --> VAL[Response validator]
    VAL -->|Valid| OUT[Persist & display response + diagnostics]
    VAL -->|Rejected| RETRY[Targeted correction prompt]
    RETRY --> GEN2[Second generation attempt]
    GEN2 --> VAL2[Second validation]
    VAL2 -->|Valid| OUT
    VAL2 -->|Rejected| FALLBACK[Deterministic safe fallback]
    FALLBACK --> OUT
    CHAT --> ACTION[Pending-action workflow]
    ACTION -->|Confirm / Reject| EXEC[Execution service + audit]
    EXEC --> DB
    OUT --> FE
```

**Design choice:** the operational tools and database remain the source of truth for order state. The language model supplies the conversational explanation; it is not allowed to substitute invented values for missing database fields.

### AI request lifecycle

| Phase            | Responsibility                                                                         |
| ---------------- | -------------------------------------------------------------------------------------- |
| Request          | Receive a customer message in a persistent conversation                                |
| Tool routing     | Detect supported order, cancellation and refund intents; obtain structured results     |
| Retrieval        | Fetch relevant support context and verified knowledge                                  |
| Context assembly | Combine message history, retrieved material, system capabilities and operational facts |
| Generation       | Request a natural-language answer from the configured Groq provider                    |
| Validation       | Detect selected unsupported factual and action-state claims                            |
| Correction       | Retry once using validation feedback if the first answer fails                         |
| Fallback         | Return a safe fixed response when both generated answers are rejected                  |
| Persistence      | Store conversation messages and AI metadata for later inspection                       |

### Database entities

| Table                     | Purpose                                                            |
| ------------------------- | ------------------------------------------------------------------ |
| `support_tickets`         | Support text, intent labels, source split and vector embeddings    |
| `conversations`           | Persistent chat sessions                                           |
| `messages`                | User/assistant messages and JSONB AI metadata                      |
| `customers`               | Customer records, including automatically generated demo customers |
| `orders`                  | Status, payment, amount, shipping data and demo-management marker  |
| `refunds`                 | Internal refund initiation/status history                          |
| `pending_actions`         | Actions awaiting, receiving, or having received a decision         |
| `action_execution_audits` | Recorded execution outcomes and associated action history          |

SQLAlchemy models, foreign-key constraints, transactions and Alembic migrations keep the schema and action lifecycle explicit.

---

## Tech stack

| Layer                | Technology                                                                                      |
| -------------------- | ----------------------------------------------------------------------------------------------- |
| Web client           | React 19, Vite, JavaScript, utility-class styling                                               |
| API                  | Python 3.12, FastAPI, Pydantic                                                                  |
| Data access          | SQLAlchemy, PostgreSQL driver                                                                   |
| Database | PostgreSQL 18 (Neon), pgvector, JSONB |
| AI retrieval         | Sentence-transformer embeddings, vector similarity and application-specific knowledge retrieval |
| Text generation      | Groq API through a provider abstraction                                                         |
| Data preparation     | Python ingestion and preprocessing modules                                                      |
| Schema changes       | Alembic                                                                                         |
| Local infrastructure | Docker Compose with pgvector-enabled PostgreSQL                                                 |
| Quality checks       | pytest, Vite production build, ESLint                                                           |

The model is used through a provider interface. ResolveAI is **not** represented as having trained its own foundation model or fine-tuned the hosted LLM.

---

## Demo walkthrough

The following walkthrough demonstrates how to explore ResolveAI using the publicly hosted application. No local installation is required.

### Try ResolveAI — Recommended Demo Workflow

**[Launch the Live Demo](https://resolve-ai-omega-lime.vercel.app/)**

ResolveAI is an interactive customer-support AI demonstration. The best way to explore its capabilities is to **create a sample order first, then ask questions about that order in a new conversation**.

**Step 1 — Create a demo order**

1. Open the live demo and navigate to the **Orders** section.
2. Click **+ Create Order**.
3. Choose a predefined scenario or configure your own order details, including order status, payment status, amount, carrier, tracking number, and estimated delivery date.
4. Submit the form. ResolveAI automatically generates a customer and a unique order number.
5. **Copy the generated order number**, such as `ORD-10001`.

**Step 2 — Start a new conversation**

1. Navigate to **Chat**.
2. Click **+ New conversation**. On mobile, select the **Conversations** tab to access this option.
3. Ask ResolveAI a question using the order number you just created.

For example:

- "What is the current status of order ORD-10001?"
- "Has my order been paid for?"
- "Which courier is delivering my order?"
- "What is the tracking number and estimated delivery date?"
- "Can I cancel order ORD-10001?"
- "Am I eligible for a refund on order ORD-10001?"

Replace `ORD-10001` with your own generated order number.

**Step 3 — Inspect how ResolveAI works**

After receiving an AI-generated response, open **AI Intelligence** on desktop or **AI Insights** on mobile.

This panel displays:

- **Tool execution:** Which database-backed tool ResolveAI used.
- **Retrieved examples:** How many relevant support examples were retrieved.
- **Verified knowledge:** Additional knowledge used to ground the response.
- **Response validation:** Whether the generated response passed validation.
- **Generation attempts:** Whether ResolveAI needed to retry and correct its response.
- **Model and provider:** The LLM used to generate the answer.

Compare the AI's response with the actual order information displayed in **Orders → View**.

**Step 4 — Explore additional scenarios**

Try creating different orders to explore:

- **Shipped orders:** Check courier and tracking information.
- **Processing orders:** Ask about cancellation eligibility and test the confirmation workflow.
- **Delivered orders:** Explore refund eligibility and internal refund initiation.
- **Orders without tracking information:** Check whether ResolveAI acknowledges missing information rather than inventing it.

You can also use **Test in Chat** from the Orders section to prepare an order-specific question automatically.

> **Demo environment:** ResolveAI uses shared synthetic data. Conversations and demo orders may be visible to other visitors. Do not enter real customer information or sensitive personal details. Cancellation and refund operations are simulated within the application; they do not affect real purchases or transfer money.

### Scenario A — Accurate shipment details

1. Open **Orders → Create Order**.
2. Choose **Tracking Available**, or manually select `shipped` and `paid`.
3. Provide a demo carrier, tracking number and estimated delivery date.
4. Create the order. The customer and order number are generated automatically.
5. Use **Test in Chat** or copy the new order number.
6. Ask: **“Where is my order ORD-XXXXX? What is the courier, tracking number and expected delivery?”**
7. Verify the answer against **View Details** and inspect **AI Intelligence**.

### Scenario B — Missing tracking data

1. Create a **Tracking Unavailable** scenario.
2. Ask the same shipment question.
3. Check whether the assistant acknowledges absent carrier/tracking/ETA values instead of inventing them.

### Scenario C — Cancellation eligibility and confirmation

1. Create a paid order in `processing` state.
2. Ask: **“Can I cancel order ORD-XXXXX?”**
3. Inspect eligibility and any pending-action controls.
4. If intentionally testing execution, use the confirmation UI and observe the resulting order state and audit history.
5. Compare with a `shipped` order, where cancellation eligibility should be restricted.

### Scenario D — Refund eligibility versus execution

1. Create a suitable paid order and ask about refund eligibility.
2. Verify the assistant does not claim a refund was initiated solely because eligibility was checked.
3. Test the confirmation-based internal refund initiation flow when appropriate.
4. Compare the resulting refund status with the stored order/refund records.

**Important:** These scenarios demonstrate ResolveAI's simulated business-rule workflows. They do not initiate external payment transfers or call live carrier-tracking services.

---

## Getting started

### Prerequisites

- Python **3.12** and `pip`
- Node.js and npm (a recent version compatible with the installed Vite version)
- Docker Desktop or another Docker-compatible runtime
- Git
- A **Groq API key** for hosted text generation

### 1. Clone and enter the project

```bash
git clone https://github.com/ribhupramanik/ResolveAI.git
cd ResolveAI
```

### 2. Start PostgreSQL with pgvector

```bash
docker compose up -d
```

The existing local configuration uses a pgvector-enabled PostgreSQL container, with PostgreSQL accessible on **localhost port 5433**. Check `docker-compose.yml` for the actual credentials and database name in your environment.

### 3. Set up the Python environment

On macOS or Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a root `.env` using the database credentials from your Docker Compose configuration. For example:

```dotenv
DATABASE_URL=postgresql+psycopg://resolveai:YOUR_PASSWORD@127.0.0.1:5433/resolveai
GROQ_API_KEY=YOUR_GROQ_API_KEY
```

`DATABASE_URL` is used by SQLAlchemy and Alembic. Confirm the exact credential and model/provider environment variable names against the checked-out `src/rag/providers/` implementation before running with a different configuration.

**Never commit `.env`, real API keys, database passwords or connection strings containing real secrets.**

### 5. Apply database migrations

```bash
alembic upgrade head
```

The migration environment is in `migrations/env.py`; Alembic uses the project's SQLAlchemy database connection. Confirm that `DATABASE_URL` points to your **development** database before running migrations.

### 6. Populate retrieval data

The chatbot's semantic retrieval requires support-ticket records with generated embeddings. The codebase includes data preparation and loading modules under `src/data/`, including `preprocess.py` and `load_data.py`.

Run the ingestion process for your checkout using its documented dataset inputs, then verify that `support_tickets` contains vector rows. A previously completed local run inserted **18,780 records with 384-dimensional embeddings**; a fresh installation starts without those records unless the data is loaded.

Do not assume database migrations alone populate the vector knowledge base.

### 7. Run FastAPI

```bash
uvicorn src.api.main:app --reload
```

Open **http://127.0.0.1:8000/docs** for interactive Swagger documentation.

### 8. Run React

In a second terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Start the development server:

```bash
npm run dev
```

Open **http://localhost:5173**.

> **CORS note:** The FastAPI backend allows the local development origins and the deployed Vercel frontend. When deploying the frontend to a different domain, update the allowed origins in the backend CORS configuration.

---

## API overview

FastAPI exposes interactive endpoint schemas at `/docs`. Representative application endpoints:

| Method   | Endpoint                                                                            | Purpose                                               |
| -------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------- |
| `GET`    | `/api/v1/conversations`                                                             | List conversations                                    |
| `POST`   | `/api/v1/conversations`                                                             | Create a conversation                                 |
| `GET`    | `/api/v1/conversations/{id}/messages`                                               | Retrieve message history                              |
| `POST`   | `/api/v1/conversations/{id}/messages`                                               | Send a message to ResolveAI                           |
| `GET`    | `/api/v1/conversations/{id}/pending-action`                                         | Inspect current pending action                        |
| `POST`   | `/api/v1/conversations/{id}/pending-actions/{action_id}/confirm-and-execute`        | Confirm and execute supported cancellation action     |
| `POST`   | `/api/v1/conversations/{id}/pending-actions/{action_id}/refund/confirm-and-execute` | Confirm and initiate internal refund                  |
| `POST`   | `/api/v1/conversations/{id}/pending-actions/{action_id}/reject`                     | Reject a pending action                               |
| `GET`    | `/api/v1/orders/{order_number}`                                                     | Look up an order                                      |
| `GET`    | `/api/v1/demo/orders`                                                               | List order scenarios                                  |
| `POST`   | `/api/v1/demo/orders`                                                               | Create a demo order; number/customer may be generated |
| `PATCH`  | `/api/v1/demo/orders/{order_id}`                                                    | Update editable order properties                      |
| `DELETE` | `/api/v1/demo/orders/{order_id}`                                                    | Delete an eligible demo-managed order                 |

### Example: create a demo order

```bash
curl -X POST http://127.0.0.1:8000/api/v1/demo/orders \
  -H 'Content-Type: application/json' \
  -d '{
    "status": "shipped",
    "payment_status": "paid",
    "total_amount": "2499.00",
    "currency": "INR",
    "shipping_address": "Demo Shipping Address",
    "carrier": "Demo Courier",
    "tracking_number": "DEMO-TRACK-001",
    "estimated_delivery": "2026-10-20"
  }'
```

The response includes the newly generated `order_number`, `customer_id`, `customer_name` and `is_demo_managed` marker. The sample carrier and tracking number are **illustrative only**.

### Example: submit a conversational request

```bash
curl -X POST http://127.0.0.1:8000/api/v1/conversations/1/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"Where is order ORD-10001?"}'
```

The conversation ID and order identifier must exist in your local database. Endpoint shapes and response schemas can also be explored interactively through Swagger.

---

## Repository layout

The tree below highlights the principal project areas rather than enumerating every source file.

```text
ResolveAI/
├── frontend/
│   └── src/
│       ├── api/
│       ├── components/
│       ├── config/
│       │   └── orderPresets.js
│       └── App.jsx
├── migrations/
│   ├── env.py
│   └── versions/
├── src/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   └── schemas/
│   ├── data/
│   │   ├── preprocess.py
│   │   └── load_data.py
│   ├── db/
│   │   ├── database.py
│   │   └── models.py
│   ├── rag/
│   │   ├── pipeline.py
│   │   ├── response_validator.py
│   │   └── providers/
│   ├── services/
│   └── tools/
├── tests/
├── docs/
│   └── screenshots/
├── alembic.ini
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Testing and validation

The backend test suite exercises important correctness and regression cases, including:

- Creating, retrieving, updating and deleting demo orders.
- Automatic generation of customer records and unique order numbers.
- Input validation, duplicate identifiers and missing related records.
- Protection of seeded records from demo deletion.
- Rejection of order deletion when any action/refund history exists.
- Order-update restrictions when financial or action history is present.
- Conversation and pending-action state transitions.
- Confirmation-based cancellation/refund execution and audit creation.
- Response-validation failures, retries and fallback behavior.

Run backend tests from the repository root:

```bash
pytest -q
```

Tests use a dedicated **`resolveai_test`** PostgreSQL database, selected by `tests/conftest.py` before application imports. Create and migrate the test database before running the suite. Verify the actual database name before executing ad hoc test scripts or destructive SQL.

To check the frontend:

```bash
cd frontend
npm run build
npm run lint
```

Passing tests demonstrate the covered behavior; they are not a measured hallucination rate, production uptime guarantee, or substitute for adversarial evaluation.

---

## Safety boundaries and deployment readiness

ResolveAI is an **engineering portfolio prototype**, not a production financial or logistics service.

**Implemented safeguards**

- Backend business-rule checks before supported actions are executed.
- Explicit confirmation/rejection workflow.
- Database transactions, relationship constraints and execution audit records.
- Response-validation diagnostics and safe fallback logic.
- Controlled deletion of demo-managed orders with action/refund history checks.

ResolveAI is deployed as a publicly accessible engineering portfolio demo using Vercel, Northflank, Neon, and Groq. It uses shared synthetic data and is not intended for real customer records or financial transactions. Authentication, visitor isolation, and additional write-operation safeguards remain future improvements.

## Current scope and future improvements

| Delivered                                         | Possible next step                                      |
| ------------------------------------------------- | ------------------------------------------------------- |
| Public full-stack deployment on Vercel, Northflank, Neon, and Groq | Strengthen public API protections and introduce visitor isolation |
| Semantic retrieval and grounded operational tools | Retrieval benchmarks and latency measurements           |
| Response validation and retry/fallback            | Wider adversarial and missing-data evaluations          |
| Cancellation and internal refund workflows        | External system integration in a controlled environment |
| Manual and preset scenario creation               | Automated demo reset and visitor-specific sandboxing    |
| Backend regression tests                          | CI checks and production observability                  |

---

## Project intent

ResolveAI was built to explore a practical AI-engineering question:

> **How can an LLM-based support assistant remain useful and conversational while being constrained by real application data and explicit business actions?**

The answer explored here is a layered system: **retrieval for context, tools for facts, validation for claims, confirmation for side effects, and audit history for accountability**.

The focus is on implementing those boundaries in working application code—not merely presenting a chat interface around an external language model.

---

<div align="center">

**ResolveAI — From plausible answers to verifiable support workflows.**

Built as an AI engineering and full-stack portfolio project.

</div>
