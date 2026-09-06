from datasets import load_dataset
import pandas as pd

DATASET_NAME = "bitext/Bitext-customer-support-llm-chatbot-training-dataset"

def load_bitext_dataset() -> pd.DataFrame:
  """
  Load the Bittext Customer Support Dataset from Hugging Face
    and return the training split as a pandas DataFrame.
  """

  dataset = load_dataset(DATASET_NAME, split="train")
  return dataset.to_pandas()


if __name__=="__main__":
  df = load_bitext_dataset()

  print("=" * 60)
  print("RESOLVEAI - BITEXT DATASET")
  print("=" * 60)

  print(f"\nDataset shape: {df.shape}")

  print("\nColumns:")
  print(df.columns.tolist())

  print("\nData Types:")
  print(df.dtypes)

  print("\nFirst 5 rows:")
  print(df.head())

  print("\nMissing Values")
  print(df.isnull().sum())

  print("\nNumber of Categories:")
  print(df["category"].nunique())

  print("\nNumber of intents:")
  print(df['intent'].nunique())