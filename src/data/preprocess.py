import re
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from src.data.load_data import load_bitext_dataset

RANDOM_STATE = 42

PROCESSED_DATA_DIR = Path("data/processed")


def normalize_for_grouping(text: str) -> str:
    """
    Normalize customer instructions for duplicate grouping.

    This function is used only to ensure that equivalent instructions
    do not appear across train, validation, and test splits.
    """

    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)

    return text

def prepare_base_dataframe(
    df: pd.DataFrame
) -> pd.DataFrame:

    df = df.copy()

    df["normalized_instruction"] = (
        df["instruction"]
        .apply(normalize_for_grouping)
    )

    df["split_group_key"] = (
        df["instruction"]
        .apply(create_split_group_key)
    )

    return df

def create_preprocessing_variant(
    df: pd.DataFrame,
    placeholder_strategy: str
) -> pd.DataFrame:

    variant_df = df.copy()

    variant_df["processed_instruction"] = (
        variant_df["instruction"]
        .apply(
            lambda text: preprocess_text(
                text,
                placeholder_strategy
            )
        )
    )

    empty_processed = (
        variant_df["processed_instruction"]
        .str.strip()
        .eq("")
        .sum()
    )

    print(
        f"{placeholder_strategy}: "
        f"{empty_processed} empty processed instructions"
    )

    if empty_processed > 0:
        raise ValueError(
            f"{placeholder_strategy} produced "
            f"{empty_processed} empty instructions."
        )

    return variant_df

def apply_split_assignments(
    df: pd.DataFrame,
    split_assignments: dict
):

    df = df.copy()

    df["split"] = (df["split_group_key"].map(split_assignments))

    if df["split"].isna().any():
        raise ValueError(
            "Some rows did not receive a split assignment."
        )

    train_df = df[
        df["split"] == "train"
    ].copy()

    validation_df = df[
        df["split"] == "validation"
    ].copy()

    test_df = df[
        df["split"] == "test"
    ].copy()

    return train_df, validation_df, test_df

PLACEHOLDER_PATTERN = r"\{\{.*?\}\}"


def process_placeholders(
    text: str,
    strategy: str = "raw"
) -> str:
    """
    Process synthetic placeholders in customer instructions.

    Parameters
    ----------
    text : str
        Original customer instruction.

    strategy : str
        One of:
        - "raw": keep placeholders unchanged
        - "generic": replace all placeholders with ENTITY_TOKEN
        - "remove": remove placeholders completely
    """

    if strategy == "raw":
        return text

    if strategy == "generic":
        return re.sub(
            PLACEHOLDER_PATTERN,
            "ENTITY_TOKEN",
            text
        )

    if strategy == "remove":
        text = re.sub(
            PLACEHOLDER_PATTERN,
            " ",
            text
        )

        return re.sub(r"\s+", " ", text).strip()

    raise ValueError(
        "strategy must be one of: "
        "'raw', 'generic', or 'remove'"
    )

def create_split_group_key(text: str) -> str:
    """
    Create the grouping key used for train/validation/test splitting.

    Placeholders are removed before normalization so that different
    placeholder variants which collapse to the same model text remain
    in the same split.
    """

    text = process_placeholders(
        text,
        strategy="remove"
    )

    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)

    return text


def create_split_assignments(
    df: pd.DataFrame,
    validation_size: float = 0.15,
    test_size: float = 0.15
) -> dict:
    """
    Assign every split-group key to exactly one
    train, validation, or test split.
    """

    group_label_counts = (
        df.groupby("split_group_key")["intent"]
        .nunique()
    )

    conflicting_groups = group_label_counts[
        group_label_counts > 1
    ]

    print(
        "Conflicting split-group keys:",
        len(conflicting_groups)
    )

    if not conflicting_groups.empty:
        raise ValueError(
            "Some split-group keys map to multiple intents. "
            "Inspect conflicting groups before splitting."
        )

    group_df = (
        df[
            ["split_group_key", "intent"]
        ]
        .drop_duplicates(
            subset=["split_group_key"]
        )
        .reset_index(drop=True)
    )

    train_groups, temp_groups = train_test_split(
        group_df,
        test_size=validation_size + test_size,
        stratify=group_df["intent"],
        random_state=RANDOM_STATE
    )

    relative_test_size = (
        test_size /
        (validation_size + test_size)
    )

    validation_groups, test_groups = train_test_split(
        temp_groups,
        test_size=relative_test_size,
        stratify=temp_groups["intent"],
        random_state=RANDOM_STATE
    )

    split_assignments = {}

    for key in train_groups["split_group_key"]:
        split_assignments[key] = "train"

    for key in validation_groups["split_group_key"]:
        split_assignments[key] = "validation"

    for key in test_groups["split_group_key"]:
        split_assignments[key] = "test"

    return split_assignments


def preprocess_text(
    text: str,
    placeholder_strategy: str = "raw"
) -> str:
    """
    Apply minimal preprocessing to customer instructions.
    """

    text = process_placeholders(
        text,
        strategy=placeholder_strategy
    )

    text = text.strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


def verify_no_group_leakage(
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    test_df: pd.DataFrame
) -> bool:

    train_groups = set(
        train_df["split_group_key"]
    )

    validation_groups = set(
        validation_df["split_group_key"]
    )

    test_groups = set(
        test_df["split_group_key"]
    )

    train_validation_overlap = (
        train_groups & validation_groups
    )

    train_test_overlap = (
        train_groups & test_groups
    )

    validation_test_overlap = (
        validation_groups & test_groups
    )

    print(
        "Split-key Train ↔ Validation overlap:",
        len(train_validation_overlap)
    )

    print(
        "Split-key Train ↔ Test overlap:",
        len(train_test_overlap)
    )

    print(
        "Split-key Validation ↔ Test overlap:",
        len(validation_test_overlap)
    )

    return (
        len(train_validation_overlap) == 0
        and len(train_test_overlap) == 0
        and len(validation_test_overlap) == 0
    )

def verify_processed_text_leakage(
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    test_df: pd.DataFrame
) -> bool:
    """
    Check whether identical processed model inputs occur
    across dataset splits.
    """

    def model_text_set(df):
        return set(
            df["processed_instruction"]
            .str.lower()
            .str.strip()
            .str.replace(
                r"\s+",
                " ",
                regex=True
            )
        )

    train_texts = model_text_set(train_df)
    validation_texts = model_text_set(validation_df)
    test_texts = model_text_set(test_df)

    train_validation_overlap = (
        train_texts & validation_texts
    )

    train_test_overlap = (
        train_texts & test_texts
    )

    validation_test_overlap = (
        validation_texts & test_texts
    )

    print(
        "Processed-text Train ↔ Validation overlap:",
        len(train_validation_overlap)
    )

    print(
        "Processed-text Train ↔ Test overlap:",
        len(train_test_overlap)
    )

    print(
        "Processed-text Validation ↔ Test overlap:",
        len(validation_test_overlap)
    )

    return (
        len(train_validation_overlap) == 0
        and len(train_test_overlap) == 0
        and len(validation_test_overlap) == 0
    )

def print_split_statistics(
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    test_df: pd.DataFrame
):
    total = (
        len(train_df)
        + len(validation_df)
        + len(test_df)
    )

    print("\nDataset Split")
    print("=" * 50)

    print(
        f"Train:      {len(train_df):5d} "
        f"({len(train_df) / total * 100:.2f}%)"
    )

    print(
        f"Validation: {len(validation_df):5d} "
        f"({len(validation_df) / total * 100:.2f}%)"
    )

    print(
        f"Test:       {len(test_df):5d} "
        f"({len(test_df) / total * 100:.2f}%)"
    )

def save_splits(
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    test_df: pd.DataFrame,
    placeholder_strategy: str
):
    output_dir = (
        PROCESSED_DATA_DIR
        / placeholder_strategy
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    train_df.to_csv(
        output_dir / "train.csv",
        index=False
    )

    validation_df.to_csv(
        output_dir / "validation.csv",
        index=False
    )

    test_df.to_csv(
        output_dir / "test.csv",
        index=False
    )

    print(
        f"\nSaved processed datasets to:"
        f"\n{output_dir}"
    )

def verify_split_completeness(
    original_df: pd.DataFrame,
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    test_df: pd.DataFrame
) -> bool:

    split_total = (
        len(train_df)
        + len(validation_df)
        + len(test_df)
    )

    print(
        "Original rows:",
        len(original_df)
    )

    print(
        "Rows across splits:",
        split_total
    )

    return split_total == len(original_df)


def print_intent_distribution(
    df: pd.DataFrame,
    split_name: str
):
    distribution = (
        df["intent"]
        .value_counts(normalize=True)
        .sort_index()
        * 100
    )

    print(f"\n{split_name} intent distribution:")
    print(distribution.round(2))


if __name__ == "__main__":

    print("=" * 60)
    print("RESOLVEAI - DATA PREPROCESSING")
    print("=" * 60)

    df = load_bitext_dataset()

    print(
        f"\nLoaded dataset with {len(df)} rows."
    )

    df = prepare_base_dataframe(df)

    split_assignments = (
        create_split_assignments(df)
    )

    strategies = [
        "raw",
        "generic",
        "remove"
    ]

    for strategy in strategies:

        print("\n" + "=" * 60)
        print(
            f"PLACEHOLDER STRATEGY: "
            f"{strategy.upper()}"
        )
        print("=" * 60)

        variant_df = (
            create_preprocessing_variant(
                df,
                strategy
            )
        )

        train_df, validation_df, test_df = (
            apply_split_assignments(
                variant_df,
                split_assignments
            )
        )

        print_split_statistics(
            train_df,
            validation_df,
            test_df
        )

        leakage_safe = verify_no_group_leakage(
            train_df,
            validation_df,
            test_df
        )

        processed_text_safe = (
            verify_processed_text_leakage(
                train_df,
                validation_df,
                test_df
            )
        )

        print(
            "Processed-text leakage-safe:",
            processed_text_safe
        )

        print(
            "Leakage-safe:",
            leakage_safe
        )

        complete_split = (
            verify_split_completeness(
                variant_df,
                train_df,
                validation_df,
                test_df
            )
        )

        print(
            "All rows assigned:",
            complete_split
        )

        save_splits(
            train_df,
            validation_df,
            test_df,
            strategy
        )