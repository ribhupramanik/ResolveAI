from pathlib import Path
import re

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CHALLENGE_PATH = (
    PROJECT_ROOT
    / "data"
    / "challenge"
    / "challenge.csv"
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "generic"
)


EXPECTED_INTENT_CATEGORY = {
    "create_account": "ACCOUNT",
    "delete_account": "ACCOUNT",
    "edit_account": "ACCOUNT",
    "recover_password": "ACCOUNT",
    "registration_problems": "ACCOUNT",
    "switch_account": "ACCOUNT",

    "cancel_order": "ORDER",
    "change_order": "ORDER",
    "place_order": "ORDER",
    "track_order": "ORDER",

    "check_cancellation_fee": "CANCEL",

    "delivery_options": "DELIVERY",
    "delivery_period": "DELIVERY",

    "change_shipping_address": "SHIPPING",
    "set_up_shipping_address": "SHIPPING",

    "check_payment_methods": "PAYMENT",
    "payment_issue": "PAYMENT",

    "check_invoice": "INVOICE",
    "get_invoice": "INVOICE",

    "check_refund_policy": "REFUND",
    "get_refund": "REFUND",
    "track_refund": "REFUND",

    "contact_customer_service": "CONTACT",
    "contact_human_agent": "CONTACT",

    "complaint": "FEEDBACK",
    "review": "FEEDBACK",

    "newsletter_subscription": "SUBSCRIPTION",
}


APPROVED_CHALLENGE_TYPES = {
    "paraphrase",
    "typo",
    "colloquial",
    "real_entity",
    "indirect",
    "long_context",
    "distractor",
    "terse",
}

def normalize_text(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text

def validate_challenge():
    df = pd.read_csv(CHALLENGE_PATH)

    print("Challenge dataset shape:", df.shape)

    required_columns = {
        "instruction",
        "intent",
        "category",
        "challenge_type",
        "notes",
    }

    assert required_columns.issubset(df.columns), (
        "Missing required columns"
    )

    # Dataset size
    assert len(df) == 270, (
        f"Expected 270 rows, found {len(df)}"
    )

    # Intent count
    assert df["intent"].nunique() == 27, (
        "Expected exactly 27 intents"
    )

    intent_counts = df["intent"].value_counts()

    assert (intent_counts == 10).all(), (
        "Every intent must contain exactly 10 examples"
    )

    # Missing values
    assert not df[
        [
            "instruction",
            "intent",
            "category",
            "challenge_type",
        ]
    ].isna().any().any(), (
        "Missing required values found"
    )

    # Exact duplicates
    assert not df["instruction"].duplicated().any(), (
        "Exact duplicate instructions found"
    )

    # Normalized duplicates
    normalized = df["instruction"].map(
        normalize_text
    )

    assert not normalized.duplicated().any(), (
        "Normalized duplicate instructions found"
    )

    # Synthetic placeholders
    placeholder_mask = (
        df["instruction"]
        .str.contains(
            r"\{\{.*?\}\}",
            regex=True,
            na=False,
        )
    )

    assert not placeholder_mask.any(), (
        "Synthetic placeholders found"
    )

    # Challenge types
    unknown_types = (
        set(df["challenge_type"])
        - APPROVED_CHALLENGE_TYPES
    )

    assert not unknown_types, (
        f"Unknown challenge types: {unknown_types}"
    )

    # Intent/category mapping
    for _, row in df.iterrows():

        expected_category = (
            EXPECTED_INTENT_CATEGORY.get(
                row["intent"]
            )
        )

        assert expected_category is not None, (
            f"Unknown intent: {row['intent']}"
        )

        assert row["category"] == expected_category, (
            f"Incorrect category for "
            f"{row['intent']}: "
            f"{row['category']}"
        )

    print("Basic challenge validation: PASSED")


def check_bitext_overlap(challenge_df):

    challenge_texts = set(
        challenge_df["instruction"]
        .map(normalize_text)
    )

    total_overlap = set()

    for split in [
        "train",
        "validation",
        "test",
    ]:

        split_path = (
            PROCESSED_DIR
            / f"{split}.csv"
        )

        split_df = pd.read_csv(
            split_path
        )

        bitext_texts = set(
            split_df["instruction"]
            .map(normalize_text)
        )

        overlap = (
            challenge_texts
            & bitext_texts
        )

        print(
            f"{split.title()} overlap:",
            len(overlap),
        )

        total_overlap.update(
            overlap
        )

    assert len(total_overlap) == 0, (
        "Challenge examples overlap "
        "with Bitext data"
    )

    print(
        "Bitext leakage check: PASSED"
    )


if __name__ == "__main__":

    validate_challenge()

    challenge_df = pd.read_csv(
        CHALLENGE_PATH
    )

    check_bitext_overlap(
        challenge_df
    )

