# ResolveAI Challenge Dataset

This dataset is a manually curated out-of-distribution evaluation set for testing intent-classification generalization beyond the Bitext dataset.

The challenge set is not used for model training or hyperparameter tuning. It is designed to contain **27 intents across 11 categories, with exactly 10 examples per intent: 270 examples in total**.

This README is the benchmark specification and annotation guideline for `data/challenge/challenge.csv`. The requirements below describe the completed dataset; they do not imply that examples have already been authored, validated, or evaluated.

## Purpose and Scope

The benchmark tests whether a model recognizes familiar customer-support intents when they are expressed through independently authored language, rather than relying on Bitext templates or synthetic placeholder cues.

The examples are designed to include realistic customer language such as:

- Paraphrases.
- Spelling mistakes.
- Colloquial language.
- Realistic entities.
- Indirect requests.
- Longer contextual messages.
- Distractor terms.
- Terse queries.

Here, **out-of-distribution** refers to variation in wording, context, and entity presentation relative to the source dataset. The label space remains unchanged. This is a closed-set, single-intent English-language benchmark, not an evaluation of unseen intents, multilingual support, multi-intent handling, or rejection of out-of-scope requests.

This small, curated benchmark complements the regular Bitext test set. It does not establish performance on representative production traffic or prove freedom from all training-data contamination.

## Folder Structure

```text
ResolveAI/
└── data/
    └── challenge/
        ├── README.md
        └── challenge.csv
```

Keep release metadata, annotation decisions, and validation reports alongside the dataset or in a clearly linked project location. Documentation examples below illustrate labeling rules; they are not automatically benchmark rows and should not be copied into the scored set.

## Intent Definitions

The following table is the authoritative intent-to-category mapping for this benchmark. Preserve the exact label spelling and capitalization: lowercase snake_case for intents and uppercase for categories. In particular, `cancel_order` belongs to `ORDER`; only `check_cancellation_fee` belongs to `CANCEL`.

| Category | Intent | Meaning | Boundary |
|---|---|---|---|
| ACCOUNT | `create_account` | User wants to create or open a new account. | If account creation is failing, use `registration_problems`. |
| ACCOUNT | `delete_account` | User wants to permanently close an account. | If they only want to edit details, use `edit_account`; switching profiles belongs to `switch_account`. |
| ACCOUNT | `edit_account` | User wants to modify information in an existing account. | If they want to move to another account, use `switch_account`; shipping-address changes belong to `change_shipping_address`. |
| ACCOUNT | `recover_password` | User forgot or needs to reset their password. | Registration failures belong to `registration_problems`; do not force unrelated login failures into this label. |
| ACCOUNT | `registration_problems` | User encounters an error while registering. | A normal signup request belongs to `create_account`. |
| ACCOUNT | `switch_account` | User wants to switch between existing accounts/profiles. | Editing current account information belongs to `edit_account`. |
| ORDER | `cancel_order` | User wants to cancel an existing order. | A question only about cancellation charges belongs to `check_cancellation_fee`. |
| ORDER | `change_order` | User wants to modify an existing order's contents, quantity, product, size, or variant. | Changing the delivery address belongs to `change_shipping_address`. |
| ORDER | `place_order` | User wants to place a new order or asks how to make a purchase. | Asking only about accepted payment methods belongs to `check_payment_methods`. |
| ORDER | `track_order` | User wants the status, location, progress, or expected arrival of a specific existing order. | General delivery timeframes belong to `delivery_period`. |
| CANCEL | `check_cancellation_fee` | User asks whether cancelling incurs a fee, charge, penalty, or deduction. | A request to perform cancellation belongs to `cancel_order`. |
| DELIVERY | `delivery_options` | User asks where or how delivery is available, including supported destinations and delivery choices. | Asking about delivery duration belongs to `delivery_period`. |
| DELIVERY | `delivery_period` | User asks about general delivery duration or shipping/delivery timeframes. | Status or arrival questions about a specific existing order belong to `track_order`. |
| SHIPPING | `change_shipping_address` | User wants to modify an already supplied shipping or delivery address. | Adding or configuring an address for the first time belongs to `set_up_shipping_address`. |
| SHIPPING | `set_up_shipping_address` | User wants to add, configure, or submit a shipping address. | Replacing or correcting an existing address belongs to `change_shipping_address`. |
| PAYMENT | `check_payment_methods` | User asks what payment methods are accepted, such as card, UPI, or cash on delivery. | A failed or otherwise problematic payment belongs to `payment_issue`. |
| PAYMENT | `payment_issue` | User reports a failed, declined, duplicated, stuck, incorrect, or otherwise problematic payment. | Merely asking which payment methods are available belongs to `check_payment_methods`. |
| INVOICE | `check_invoice` | User wants to inspect, verify, check, or understand an existing invoice or bill. | Obtaining, downloading, or receiving an invoice belongs to `get_invoice`. |
| INVOICE | `get_invoice` | User wants an invoice to be provided, downloaded, emailed, or retrieved. | Checking the contents of an invoice they already have belongs to `check_invoice`. |
| REFUND | `check_refund_policy` | User asks about refund rules, eligibility, conditions, fees, deadlines, or policy. | Initiating a refund belongs to `get_refund`; tracking an existing refund belongs to `track_refund`. |
| REFUND | `get_refund` | User wants to initiate or request a refund. | Status of a previously requested refund belongs to `track_refund`. |
| REFUND | `track_refund` | User wants the status of an already initiated refund. | Eligibility questions belong to `check_refund_policy`; a new request belongs to `get_refund`. |
| CONTACT | `contact_customer_service` | User wants to contact customer support/service or asks how to reach support. | An explicit request for a human agent belongs to `contact_human_agent`. |
| CONTACT | `contact_human_agent` | User specifically wants to speak or chat with a human, person, or representative. | General support contact information belongs to `contact_customer_service`. |
| FEEDBACK | `complaint` | User wants to complain or report dissatisfaction about a product, service, or experience. | An explicit request to submit a review or rating belongs to `review`; a specific supported action takes precedence over incidental dissatisfaction. |
| FEEDBACK | `review` | User wants to submit or share a review, rating, or evaluative feedback about their experience. | Reporting a grievance for support to address belongs to `complaint`. Sentiment alone does not decide the label. |
| SUBSCRIPTION | `newsletter_subscription` | User wants to subscribe to, unsubscribe from, or manage a newsletter subscription. | Unrelated paid-product or service subscriptions are outside this intent. |

### Required Category Distribution

| Category | Intents | Examples |
|---|---:|---:|
| ACCOUNT | 6 | 60 |
| ORDER | 4 | 40 |
| CANCEL | 1 | 10 |
| DELIVERY | 2 | 20 |
| SHIPPING | 2 | 20 |
| PAYMENT | 2 | 20 |
| INVOICE | 2 | 20 |
| REFUND | 3 | 30 |
| CONTACT | 2 | 20 |
| FEEDBACK | 2 | 20 |
| SUBSCRIPTION | 1 | 10 |
| **Total** | **27** | **270** |

## Challenge Example Writing Rules

1. Decide the intended label before writing the query, using the definitions and boundaries in this document.
2. Each example must contain one clearly identifiable primary intent. Exclude genuinely multi-intent requests such as “Cancel my order and refund the payment.”
3. Do not copy sentences from Bitext, lightly rewrite its examples, or reuse its templates by changing only names, numbers, or dates. Author from the intent definition rather than from a source example.
4. Do not use synthetic placeholders such as `{{Order Number}}`, `{{Refund Amount}}`, or `{{Delivery City}}`.
5. Use realistic values when appropriate: `order 728193`, `₹1,499`, `Kolkata`, or `September 10`. Customer identifiers and personal details must be fictional. Recognizable public place names and payment methods are acceptable.
6. Include natural linguistic variation such as typos, slang, indirect wording, longer explanations, and short queries. Keep the message understandable without external context.
7. Examples may contain words associated with another intent, but the primary intent must remain unambiguous. Background events, resolved problems, and negated requests can provide context without becoming additional active requests.
8. Do not change an example or its label based on a model prediction. Select and review the examples before inspecting challenge-set predictions.
9. Challenge examples must never be added to model-training data, few-shot demonstrations, or tuning datasets.
10. Each of the 27 intents must contain exactly 10 examples in the released benchmark.
11. Avoid mechanical variants of one sentence. Vary sentence structure, customer situation, vocabulary, and request style within each intent.
12. Do not make every example depend on obvious intent keywords, but do not remove essential meaning just to make a query difficult. Short examples must still identify a single intent.
13. Keep the necessary evidence in `instruction`. The `notes` field may explain a decision but must not supply facts missing from the customer message.
14. Avoid artificial label cues: category names, annotation comments, repeated intent-specific prefixes, or entity formats used exclusively as shortcuts for a class.

## Challenge Types

Each row must have exactly one primary `challenge_type` from this list.

| Type | Description |
|---|---|
| `paraphrase` | Expresses the intent using wording unlike the training templates. |
| `typo` | Contains realistic spelling or typing mistakes. |
| `colloquial` | Uses casual or conversational language. |
| `real_entity` | Contains realistic IDs, prices, places, dates, or similar values. |
| `indirect` | Expresses the intent without obvious intent keywords. |
| `long_context` | Contains the request inside a longer explanation. |
| `distractor` | Contains vocabulary associated with another intent. |
| `terse` | Very short customer request. |

Choose the primary type according to the main difficulty deliberately introduced during authoring. If several types apply, the reviewer confirms the dominant one and may record secondary characteristics in `notes`. Do not store comma-separated or combined type labels in `challenge_type`. A realistic order number does not automatically make `real_entity` the primary type when the intended difficulty is an indirect request.

### Challenge-Type Diversity

The 10 examples for each intent should cover several naturally applicable types. Include a mix of direct and indirect wording, message lengths, and contexts. Review the collection for repetitive structures and for accidental associations between a challenge type and a particular intent.

Do **not** require exactly one example of every type for every intent, equal type counts, or a rigid per-intent allocation. There are eight types and ten examples per intent, and some combinations are less natural than others. Coverage should serve clear, realistic examples rather than a quota.

At release, report the overall primary-type counts and the intent-by-type distribution. Aim to represent all eight types across the benchmark; explain any absent type or substantial concentration. Secondary characteristics recorded in notes are descriptive and do not change primary-type counts. Type-based results are observational slices: an example may have several linguistic properties even though it has only one primary tag.

## Dataset Schema

Store the dataset as UTF-8, comma-delimited CSV with this exact header and column order:

```csv
instruction,intent,category,challenge_type,notes
```

| Column | Required value? | Description |
|---|---|---|
| `instruction` | Yes | Customer-support query; the only model-input field. |
| `intent` | Yes | Ground-truth intent from the 27-label table. |
| `category` | Yes | Parent category determined by the intent-to-category mapping. |
| `challenge_type` | Yes | One approved primary challenge type. |
| `notes` | No | Annotation rationale, boundary explanation, or secondary characteristics. |

All five columns must exist; `notes` values may be empty. Do not write a dataframe index column. Quote fields containing commas, quotation marks, or newlines using standard CSV escaping; double internal quotation marks. Use one physical line per example where practical. Preserve intended spelling mistakes in the stored instruction.

Keep author, reviewer, and release audit information in separate metadata so the evaluation schema stays stable. The dataset does not contain model predictions or confidence scores.

## Annotation Policy

1. **Draft:** Select the intended intent and primary challenge type, then write an original message.
2. **Review:** Read the instruction independently of its draft label where possible. Confirm that exactly one supported intent follows from the text and that its category is correct.
3. **Resolve:** Use the definitions and important boundaries below. Rewrite or exclude examples that remain ambiguous; do not invent an unstated customer history to justify the label.
4. **Document:** Add notes for non-obvious boundary decisions. Record unresolved disagreements and their resolution in an annotation log.
5. **Validate and freeze:** Complete the checks below before model predictions are inspected. Freeze the example text, labels, types, row order, and dataset version together.

A second human reviewer is recommended. If only one annotator is available, perform a separate review pass and disclose that limitation; do not claim independent review or inter-annotator agreement. Where independent annotations exist, record the reviewer count, agreement measure and sample size, and adjudication method.

Questions asking how to perform an action can carry that action's intent; the customer need not phrase the message as a command. Negative sentiment does not override a specific requested action. Exclude unsupported requests rather than assigning the nearest available label.

## Important Intent Boundaries

The quoted messages in this section are documentation examples only.

### `create_account` vs `registration_problems`

- `create_account`: User wants to create an account normally. Example: “How do I open an account?”
- `registration_problems`: User is already trying to register but something is failing. Example: “The signup page keeps rejecting my email.”

### `get_refund` vs `track_refund` vs `check_refund_policy`

- `get_refund`: User wants to request a refund. Example: “I want my money back for this purchase.”
- `track_refund`: A refund has already been requested and the user wants its status. Example: “My refund was approved last week but the money still hasn't arrived.”
- `check_refund_policy`: User asks about rules or eligibility. Example: “Can sale items be refunded?”

A returned item alone does not establish that a refund was initiated. Give tracking examples enough context to establish a prior refund request or approval. Distinguish general policy time limits from the progress of a particular refund.

### `cancel_order` vs `check_cancellation_fee`

“Please cancel my order” requests cancellation. “Will I be charged if I cancel?” asks about the fee. Avoid examples that independently request both cancellation and fee information.

### `change_order` vs `change_shipping_address`

Changing an order's size, quantity, or product is `change_order`. Replacing its delivery destination is `change_shipping_address`, even when an order number is mentioned.

### `track_order` vs `delivery_period` vs `delivery_options`

“When will the order I placed yesterday arrive?” is `track_order`; a literal order number is not required. “How many days does standard delivery usually take?” is `delivery_period`. “Do you deliver to Kolkata?” or “Is express delivery available?” is `delivery_options`.

### `set_up_shipping_address` vs `change_shipping_address`

Adding a first or additional new shipping address is `set_up_shipping_address`. Correcting or replacing an address already supplied is `change_shipping_address`. Make that distinction explicit in the message; generic wording such as “help with my address” is insufficient.

### `check_payment_methods` vs `payment_issue`

“Do you accept UPI?” asks about accepted methods. “My UPI payment keeps failing” reports a payment issue. Mentioning a method does not make a failed transaction a methods query.

### `check_invoice` vs `get_invoice`

“Why does my invoice show two delivery charges?” asks to inspect an existing invoice. “Please email my invoice” asks to obtain it. Distinguish an invoice-line discrepancy from an actual duplicate payment, which belongs to `payment_issue`.

### `contact_customer_service` vs `contact_human_agent`

“What is your support email address?” is `contact_customer_service`. “Connect me to a real person” is `contact_human_agent`. Use the human-agent label when the request specifically seeks a person or representative, rather than inferring that all support contact implies a human.

### `complaint` vs `review`

Use the communicative purpose, not positive or negative sentiment. “I want to file a complaint about the rude courier” is `complaint`. “Where can I post a one-star review?” is `review`, despite its negative sentiment. A dissatisfied customer who specifically asks for a refund has `get_refund` as the primary intent when the grievance merely explains that request.

### `edit_account` vs `switch_account` vs `delete_account`

Changing an account email or phone number is `edit_account`. Moving to another existing profile is `switch_account`. Permanently closing the account is `delete_account`. Password recovery belongs to `recover_password`, and shipping-address requests use the dedicated shipping intents.

### `newsletter_subscription` vs `delete_account`

Stopping newsletter emails is `newsletter_subscription`; it does not mean deleting the account. Paid membership cancellation is outside this newsletter-specific intent and should be excluded unless another supported intent is clearly applicable.

## Leakage Prevention

The challenge set must remain independent from the Bitext training, validation, and test examples and from model-development decisions.

- Author from the taxonomy, without copying or lightly modifying source examples. Do not paste training examples into an assisted-authoring prompt.
- Prohibit synthetic `{{...}}` placeholders and template variants that differ only in entity values.
- Check exact and normalized duplicates within the challenge set and against **all three** frozen Bitext splits.
- For a reproducible baseline comparison key, apply Unicode NFKC normalization, case folding, leading/trailing whitespace removal, and whitespace collapsing. Keep the original instruction unchanged.
- Also compare the project's established split-group keys and the processed representations used by the evaluated pipelines, including applicable raw, generic-placeholder, and placeholder-removed variants. Record the actual preprocessing implementation and version; a newly invented comparison key is not a replacement for the project's leakage checks.
- Review near-duplicate wording and template similarity manually, supported by a documented similarity method if available. Exact matching cannot establish independence by itself. Resolve confirmed copied or lightly modified examples before release.
- Preserve a report of checks, collisions, decisions, source-split versions, and normalization settings. Dataset-overlap audits must not be used to tune models using the held-out Bitext test data.
- Never fit tokenizers, vocabularies, TF-IDF statistics, scalers, classifiers, calibration, or other learned components on challenge examples. Do not use the set for feature selection, early stopping, prompt selection, threshold tuning, or preprocessing changes.
- Do not use challenge examples as few-shot prompts, retrieval examples, augmentation seeds, or training data. Keep labels, categories, types, and notes out of model inputs.

If a model has already been developed using this challenge set or feedback from its errors, disclose that exposure. Its results on the same set are development results, not a fresh held-out estimate. Use a newly authored, independently frozen benchmark for a new held-out assessment.

## Dataset Validation Requirements

Before releasing `challenge-v1`, the finished CSV must pass all applicable checks. Preserve the report; do not mark a check as passed without running or performing it.

### Structural and Automated Checks

- [ ] File parses as UTF-8 CSV with exactly the five documented columns and no extra index column.
- [ ] Exactly 270 data rows, excluding the header.
- [ ] Exactly the 27 approved intent labels, with 10 examples per intent.
- [ ] Exactly the 11 approved categories, matching the required distribution.
- [ ] Every intent maps to its correct category.
- [ ] No missing, empty, or whitespace-only instructions, intents, categories, or challenge types; empty notes are allowed.
- [ ] Every challenge type is one approved value, with no combined tags.
- [ ] No exact or baseline-normalized duplicate instructions within the challenge set.
- [ ] No exact or baseline-normalized instruction overlap with the frozen Bitext train, validation, or test splits.
- [ ] Project split-group and processed-text overlap checks completed for each applicable pipeline representation; no unresolved collisions remain.
- [ ] No synthetic `{{...}}` placeholders, and no empty inputs after each frozen evaluation preprocessing pipeline.
- [ ] Overall challenge-type counts and intent-by-type counts recorded, including any missing coverage.

### Human Review Checks

- [ ] Every message has exactly one identifiable supported primary intent.
- [ ] Labels, boundaries, and primary type assignments agree with this guide.
- [ ] Notes do not supply missing evidence needed to infer the label.
- [ ] Examples are original, realistic, and diverse; no copied templates or unresolved near-duplicates remain.
- [ ] Customer identifiers and personal details are fictional.
- [ ] Annotation disagreements and any coverage limitations are documented.
- [ ] Dataset and annotation review completed without inspecting challenge-model predictions.
- [ ] Release version, file hash, provenance, and review status recorded before evaluation.

Structural validity does not prove semantic correctness; both automated checks and human review are required.

## Evaluation Protocol

### Before Evaluation

Finalize model selection, hyperparameters, prompts where relevant, preprocessing, label mapping, and any thresholds using the regular training and validation data. Declare the models to be compared before inspecting challenge results. Keep the regular Bitext test set separate and report its results separately.

Freeze the challenge release and the model artifacts. Use the same 270 rows for every model. Pass only `instruction` through each model's already finalized inference pipeline; call transformation and prediction steps without fitting on challenge data. Any model-specific preprocessing differences must have been decided before evaluation and must be documented.

### Required Results

| Output | Reporting requirement |
|---|---|
| Accuracy | Correct predictions divided by all 270 examples; include correct and incorrect counts. |
| Macro-F1 | Unweighted mean of F1 across the full fixed set of 27 intents. |
| Per-intent report | Precision, recall, F1, and support for each intent; support must be 10. |
| Confusion matrix | Raw counts with the same fixed 27-label ordering for every model; an additional row-normalized view is optional. |
| Challenge-type performance | Sample count, correct count, errors, and accuracy for each primary type. |

Use a documented zero-division convention of zero for undefined precision or F1. Do not silently omit labels with no predictions. Preserve the taxonomy-table label order, or publish an explicit fixed ordering with the report.

For optional macro-F1 by challenge type, state the averaging label set explicitly. Prefer labels with ground-truth support in that slice, report which labels are present, and use the same slice label set for every model. Slice scores with different label coverage are not directly comparable. Primary-type slices do not isolate the causal effect of a single linguistic property.

Every benchmark row must receive one prediction. Count abstentions, invalid labels, and failed predictions as incorrect for headline accuracy and as missed true labels for intent recall/F1; report their counts separately and show an additional failure column if needed in the confusion display. Do not drop failed rows or replace them with an allowed label after inspecting the answer.

### Reproducibility and Interpretation

Record the dataset version and SHA-256 hash, model/checkpoint identifier, code revision, training-split version, preprocessing configuration, package versions, random seeds where applicable, and evaluation date. For remote models, record the provider's model identifier and generation settings. Save per-example predictions separately, keyed by dataset version and 1-based CSV data-row number, with the header excluded from row numbering.

Report results for all predeclared models. Do not select the best challenge score and then describe that same score as an unbiased estimate of model-selection performance. Repeated stochastic runs must be planned in advance, use the same protocol, and report variation rather than only the best run.

With 10 examples per intent, one error changes that intent's recall by 10 percentage points. One error changes overall accuracy by approximately 0.37 percentage points. Avoid strong claims from small score differences or sparse type slices. If reporting uncertainty intervals or paired comparisons, document the method and recognize that they do not make a curated sample representative of deployment traffic.

After evaluation, analyze errors against the frozen definitions without relabeling examples to agree with a model. Improvements informed by these errors constitute challenge-informed development and must be identified as such.

## Dataset Provenance and Versioning

**Base taxonomy:** The 27 intent labels and 11 parent categories follow the Bitext Customer Support taxonomy already adopted by ResolveAI. This guide preserves that project mapping and expands the original challenge README's wording and boundary rules.

**Example source:** Examples are to be independently authored for ResolveAI and manually reviewed. This specification does not certify that a completed dataset exists or that it was authored entirely without assistance. If AI tools assist drafting or review, disclose their role, model/version, date, and prompt or prompt reference; do not describe assisted examples as exclusively human-written.

**Target first release:** `challenge-v1`. Assign the release only after authoring, validation, and freezing are complete.

For each release, retain the following metadata in a release record:

| Field | What to record |
|---|---|
| Dataset version and status | Version identifier and draft/frozen status. |
| Release date | Actual date the dataset was frozen. |
| Maintainer and contributors | Author and reviewer names or stable identifiers, with their roles. |
| Authorship method | Human-only or assisted workflow, tools used, and review process. |
| Taxonomy/source reference | Exact Bitext dataset identifier, source URL, and revision used by the project; source-split versions or hashes used for overlap checks. |
| Dataset identity | `challenge.csv` SHA-256 hash, row count, schema, and repository commit. |
| Validation evidence | Report location, review outcomes, overlap-check configuration, and known limitations. |
| Changes | Added, removed, edited, or relabeled rows and the reason for each change. |
| Usage terms | Explicit terms for the independently authored examples and applicable source attribution; do not assume the source dataset's license automatically covers new content. |

Never silently replace a benchmark used for reported results. Changes to instructions, labels, categories, challenge types, row membership, or row ordering require a new dataset version and a change log. Preserve older releases and their predictions so prior results remain reproducible. Pure documentation clarifications may retain the dataset version if the CSV and labeling policy are unchanged; record the documentation revision.

If a genuine annotation defect is discovered after evaluation, log it, review it on semantic grounds independently of model preference, and publish a corrected version rather than editing the frozen release. Report the correction and its effect on comparability. A corrected or renamed version does not erase prior model-development exposure to the same examples.

## Release Checklist

- [ ] Author and review all 270 examples using this specification.
- [ ] Complete structural, semantic, diversity, and leakage checks.
- [ ] Record actual provenance, review limitations, and usage terms.
- [ ] Freeze `challenge.csv`, record its hash, and assign the dataset version.
- [ ] Finalize the models and evaluation configuration before inspecting predictions.
- [ ] Publish metrics, distributions, run metadata, and known limitations with the exact release identifier.
