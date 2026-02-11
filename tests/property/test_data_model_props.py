"""Property-based tests for data model validation.

Feature: els-normalization-pipeline
"""

import pytest
from hypothesis import given, strategies as st
from datetime import datetime

from els_pipeline.models import (
    DetectedElement,
    HierarchyLevelEnum,
    EmbeddingRecord,
    Recommendation,
    AudienceEnum,
)


# Strategies for generating test data

@st.composite
def detected_element_strategy(draw):
    """Generate a DetectedElement with valid fields."""
    level = draw(st.sampled_from(list(HierarchyLevelEnum)))
    code = draw(st.text(min_size=1, max_size=20))
    title = draw(st.text(min_size=1, max_size=100))
    description = draw(st.text(min_size=1, max_size=500))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    source_page = draw(st.integers(min_value=1, max_value=1000))
    source_text = draw(st.text(min_size=1, max_size=1000))
    needs_review = confidence < 0.7
    
    return DetectedElement(
        level=level,
        code=code,
        title=title,
        description=description,
        confidence=confidence,
        source_page=source_page,
        source_text=source_text,
        needs_review=needs_review,
    )


@st.composite
def embedding_record_strategy(draw):
    """Generate an EmbeddingRecord with all required fields."""
    indicator_id = draw(st.text(min_size=1, max_size=50))
    state = draw(st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',))))
    vector = draw(st.lists(st.floats(min_value=-1.0, max_value=1.0), min_size=1, max_size=1536))
    embedding_model = draw(st.text(min_size=1, max_size=100))
    embedding_version = draw(st.text(min_size=1, max_size=10))
    input_text = draw(st.text(min_size=1, max_size=1000))
    created_at = datetime.utcnow().isoformat()
    
    return EmbeddingRecord(
        indicator_id=indicator_id,
        state=state,
        vector=vector,
        embedding_model=embedding_model,
        embedding_version=embedding_version,
        input_text=input_text,
        created_at=created_at,
    )


@st.composite
def recommendation_strategy(draw):
    """Generate a Recommendation with all required fields."""
    recommendation_id = draw(st.text(min_size=1, max_size=100))
    indicator_id = draw(st.text(min_size=1, max_size=50))
    state = draw(st.text(min_size=2, max_size=2, alphabet=st.characters(whitelist_categories=('Lu',))))
    audience = draw(st.sampled_from(list(AudienceEnum)))
    activity_description = draw(st.text(min_size=1, max_size=1000))
    age_band = draw(st.text(min_size=1, max_size=10))
    generation_model = draw(st.text(min_size=1, max_size=100))
    created_at = datetime.utcnow().isoformat()
    
    return Recommendation(
        recommendation_id=recommendation_id,
        indicator_id=indicator_id,
        state=state,
        audience=audience,
        activity_description=activity_description,
        age_band=age_band,
        generation_model=generation_model,
        created_at=created_at,
    )


# Property 7: Detected Element Field Validity
# **Validates: Requirements 3.2, 3.3**

@given(detected_element_strategy())
def test_property_7_detected_element_field_validity(element):
    """Property 7: Detected Element Field Validity.
    
    For any detected element, confidence in [0.0, 1.0] and level in valid set.
    
    **Validates: Requirements 3.2, 3.3**
    """
    # Confidence must be in valid range
    assert 0.0 <= element.confidence <= 1.0, \
        f"Confidence {element.confidence} not in [0.0, 1.0]"
    
    # Level must be one of the valid hierarchy levels
    valid_levels = {level.value for level in HierarchyLevelEnum}
    assert element.level.value in valid_levels, \
        f"Level {element.level} not in valid set {valid_levels}"


# Property 18: Embedding Record Completeness
# **Validates: Requirements 6.3**

@given(embedding_record_strategy())
def test_property_18_embedding_record_completeness(record):
    """Property 18: Embedding Record Completeness.
    
    For any embedding record, all required fields present.
    
    **Validates: Requirements 6.3**
    """
    # All required fields must be present and non-empty
    assert record.indicator_id, "indicator_id must be present and non-empty"
    assert record.state, "state must be present and non-empty"
    assert record.vector, "vector must be present and non-empty"
    assert len(record.vector) > 0, "vector must contain at least one element"
    assert record.embedding_model, "embedding_model must be present and non-empty"
    assert record.embedding_version, "embedding_version must be present and non-empty"
    assert record.created_at, "created_at must be present and non-empty"
    assert record.input_text, "input_text must be present and non-empty"


# Property 23: Recommendation Record Completeness
# **Validates: Requirements 8.3, 8.6**

@given(recommendation_strategy())
def test_property_23_recommendation_record_completeness(recommendation):
    """Property 23: Recommendation Record Completeness.
    
    For any recommendation, all required fields present and valid.
    
    **Validates: Requirements 8.3, 8.6**
    """
    # All required fields must be present and non-empty
    assert recommendation.recommendation_id, \
        "recommendation_id must be present and non-empty"
    assert recommendation.indicator_id, \
        "indicator_id must be present and non-empty"
    assert recommendation.state, \
        "state must be present and non-empty"
    assert recommendation.audience in [AudienceEnum.PARENT, AudienceEnum.TEACHER], \
        f"audience must be 'parent' or 'teacher', got {recommendation.audience}"
    assert recommendation.activity_description, \
        "activity_description must be present and non-empty"
    assert len(recommendation.activity_description) > 0, \
        "activity_description must not be empty"
    assert recommendation.age_band, \
        "age_band must be present and non-empty"
    assert recommendation.generation_model, \
        "generation_model must be present and non-empty"
    assert recommendation.created_at, \
        "created_at must be present and non-empty"
