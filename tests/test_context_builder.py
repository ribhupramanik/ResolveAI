import pytest

from src.rag.context_builder import (
  ContextBuilder,
  RetrievedContext
)

@pytest.fixture(scope="module")
def builder():
  return ContextBuilder()


def test_context_is_generated(builder):
  result = builder.build("where is my refund")

  assert isinstance( result, RetrievedContext)

  assert(result.retrieved_count > 0)

  assert result.context


def test_context_contains_expected_sections(builder):
  result = builder.build("where is my refund")

  assert("Customer request:" in result.context)

  assert("Historical resolution:" in result.context)

  assert("Intent:" in result.context)

  assert("Similarity:" in result.context)


def test_similarity_metadata_is_valid(builder,):
  result = builder.build("I forgot my password")

  assert( result.max_similarity is not None )

  assert( result.min_similarity is not None )

  assert( result.max_similarity >= result.min_similarity )

  assert ( result.max_similarity <= 1.0 + 1e-6 )

  assert( result.min_similarity >= -1.0 - 1e-6 )


def test_high_similarity_threshold_removes_results():

  builder = ContextBuilder( min_similarity=1.1 )

  result = builder.build( "where is my refund" )

  assert ( result.retrieved_count == 0 )

  assert ( result.context == "" )

  assert ( result.max_similarity is None )

  assert ( result.min_similarity is None )



def test_context_removes_duplicate_evidence(builder):

  result = builder.build( "my refund still hasn't arrived" )

  blocks = (result.context.strip().split("\n\n") )

  assert (len(blocks) == len(set(blocks)))