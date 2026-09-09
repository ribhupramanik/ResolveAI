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

    group_df = (
        df[
            ["normalized_instruction", "intent"]
        ]
        .drop_duplicates(
            subset=["normalized_instruction"]
        )
        .reset_index(drop=True)
    )


