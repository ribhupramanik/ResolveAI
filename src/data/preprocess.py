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


def create_split_assignments(
    df: pd.DataFrame,
    validation_size: float = 0.15,
    test_size: float = 0.15
) -> dict:
    """
    Assign every normalized-instruction group to exactly one
    train, validation, or test split.
    """

    group_label_counts = (
        df.groupby("normalized_instruction")["intent"]
        .nunique()
    )

    if (group_label_counts > 1).any():
        raise ValueError(
            "Normalized instructions contain conflicting intent labels."
        )

    group_df = (
        df[
            ["normalized_instruction", "intent"]
        ]
        .drop_duplicates(
            subset=["normalized_instruction"]
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

    for key in train_groups["normalized_instruction"]:
        split_assignments[key] = "train"

    for key in validation_groups["normalized_instruction"]:
        split_assignments[key] = "validation"

    for key in test_groups["normalized_instruction"]:
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

def prepare_dataframe(
    df: pd.DataFrame,
    placeholder_strategy: str = "raw"
) -> pd.DataFrame:
    """
    Prepare the dataset for machine learning.
    """

    df = df.copy()

    df["normalized_instruction"] = (
        df["instruction"]
        .apply(normalize_for_grouping)
    )

    df["processed_instruction"] = (
        df["instruction"]
        .apply(
            lambda text: preprocess_text(
                text,
                placeholder_strategy
            )
        )
    )

    empty_processed = (
        df["processed_instruction"]
        .str.strip()
        .eq("")
        .sum()
    )

    print(
        "Empty processed instructions:",
        empty_processed
    )

    if empty_processed > 0:
      raise ValueError(
          f"Found {empty_processed} empty processed instructions."
      )


    return df

def create_leakage_safe_splits(
    df: pd.DataFrame,
    train_size: float = 0.70,
    validation_size: float = 0.15,
    test_size: float = 0.15,
):
    """
    Create train, validation, and test datasets while ensuring
    normalized-equivalent instructions remain in the same split.

    Splitting is stratified at the normalized-instruction group level
    using intent labels.
    """

    if round(
        train_size + validation_size + test_size,
        10
    ) != 1.0:
        raise ValueError(
            "train_size + validation_size + test_size "
            "must equal 1."
        )
    group_label_counts = (
        df.groupby("normalized_instruction")["intent"]
        .nunique()
    )

    conflicting_groups = group_label_counts[
        group_label_counts > 1
    ]

    if not conflicting_groups.empty:
        raise ValueError(
            "Found normalized instructions mapped to multiple intents."
        )

    group_df = (
        df[
            ["normalized_instruction", "intent"]
        ]
        .drop_duplicates(
            subset=["normalized_instruction"]
        )
        .reset_index(drop=True)
    )

    relative_test_size = (
        test_size /
        (validation_size + test_size)
    )

    train_groups, temp_groups = train_test_split(
        group_df,
        test_size=validation_size + test_size,
        stratify=group_df["intent"],
        random_state=RANDOM_STATE
    )

    validation_groups, test_groups = train_test_split(
        temp_groups,
        test_size=relative_test_size,
        stratify=temp_groups["intent"],
        random_state=RANDOM_STATE
    )

    train_group_keys = set(
        train_groups["normalized_instruction"]
    )

    validation_group_keys = set(
        validation_groups["normalized_instruction"]
    )

    test_group_keys = set(
        test_groups["normalized_instruction"]
    )

    train_df = df[
        df["normalized_instruction"].isin(
            train_group_keys
        )
    ].copy()

    validation_df = df[
        df["normalized_instruction"].isin(
            validation_group_keys
        )
    ].copy()

    test_df = df[
        df["normalized_instruction"].isin(
            test_group_keys
        )
    ].copy()

    return train_df, validation_df, test_df


def verify_no_group_leakage(
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    test_df: pd.DataFrame
) -> bool:
    """
    Verify that normalized instructions do not overlap
    between dataset splits.
    """

    train_groups = set(
        train_df["normalized_instruction"]
    )

    validation_groups = set(
        validation_df["normalized_instruction"]
    )

    test_groups = set(
        test_df["normalized_instruction"]
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
        "Train ↔ Validation overlap:",
        len(train_validation_overlap)
    )

    print(
        "Train ↔ Test overlap:",
        len(train_test_overlap)
    )

    print(
        "Validation ↔ Test overlap:",
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

    placeholder_strategy = "raw"

    df = prepare_dataframe(
        df,
        placeholder_strategy=placeholder_strategy
    )

    train_df, validation_df, test_df = (
        create_leakage_safe_splits(df)
    )

    print_split_statistics(
        train_df,
        validation_df,
        test_df
    )

    print_intent_distribution(
          train_df,
         "Train"
    )
    
    print_intent_distribution(
       validation_df,
       "Validation"
    )

    print_intent_distribution(
        test_df,
        "Test"
    )
    

    print("\nLeakage Check")
    print("=" * 50)

    leakage_safe = verify_no_group_leakage(
        train_df,
        validation_df,
        test_df
    )

    print(
        "\nLeakage-safe split:",
        leakage_safe
    )

    complete_split = verify_split_completeness(
        df,
        train_df,
        validation_df,
        test_df
    )

    print(
        "\nAll rows assigned:",
        complete_split
    )

    save_splits(
        train_df,
        validation_df,
        test_df,
        placeholder_strategy
    )