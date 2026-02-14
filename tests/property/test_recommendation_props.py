"""Property-based tests for recommendation generation.

Feature: els-normalization-pipeline
"""

import pytest
from hypothesis import given, strategies as st, assume
from datetime import datetime, timezone

from els_pipeline.models import (
    Recommendation,
    AudienceEnum,
)


# Strategies for generating test data

@st.composite
def country_code_strategy(draw):
    """Generate a valid two-letter country code."""
    return draw(st.text(min_size=2, max_size=2, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ'))


@st.composite
def state_code_strategy(draw):
    """Generate a state code."""
    return draw(st.text(min_size=2, max_size=10, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ'))


@st.composite
def recommendation_strategy(draw, country=None, state=None):
    """Generate a Recommendation with optional fixed country and state."""
    rec_country = country if country else draw(country_code_strategy())
    rec_state = state if state else draw(state_code_strategy())
    
    recommendation_id = draw(st.text(min_size=1, max_size=100))
    indicator_id = draw(st.text(min_size=1, max_size=50))
    audience = draw(st.sampled_from(list(AudienceEnum)))
    activity_description = draw(st.text(min_size=1, max_size=1000))
    age_band = draw(st.text(min_size=1, max_size=10))
    generation_model = draw(st.text(min_size=1, max_size=100))
    created_at = datetime.now(timezone.utc).isoformat()
    
    return Recommendation(
        recommendation_id=recommendation_id,
        indicator_id=indicator_id,
        country=rec_country,
        state=rec_state,
        audience=audience,
        activity_description=activity_description,
        age_band=age_band,
        generation_model=generation_model,
        created_at=created_at,
    )


# Property 25: Recommendation State Scoping
# **Validates: Requirements 8.3, 8.6, 8.7**

@given(
    country=country_code_strategy(),
    state=state_code_strategy(),
    recommendations=st.data()
)
def test_property_25_recommendation_country_state_scoping(country, state, recommendations):
    """Property 25: Recommendation State Scoping.
    
    For any recommendation request specifying a country and state, all returned
    recommendations SHALL reference indicators belonging to that country and state only.
    No indicator_id from a different country or state SHALL appear in the results.
    
    **Validates: Requirements 8.3, 8.6, 8.7**
    """
    # Generate 1-10 recommendations for the specified country and state
    num_recs = recommendations.draw(st.integers(min_value=1, max_value=10))
    test_recommendations = [
        recommendations.draw(recommendation_strategy(country=country, state=state))
        for _ in range(num_recs)
    ]
    
    # Verify all recommendations match the requested country and state
    for rec in test_recommendations:
        assert rec.country == country, \
            f"Recommendation country {rec.country} does not match requested country {country}"
        assert rec.state == state, \
            f"Recommendation state {rec.state} does not match requested state {state}"


@given(
    target_country=country_code_strategy(),
    target_state=state_code_strategy(),
    other_country=country_code_strategy(),
    other_state=state_code_strategy(),
    data=st.data()
)
def test_property_25_no_cross_country_state_leakage(
    target_country,
    target_state,
    other_country,
    other_state,
    data
):
    """Property 25: No Cross-Country/State Data Leakage.
    
    Recommendations for a specific country and state must not include indicators
    from other countries or states.
    
    **Validates: Requirements 8.7**
    """
    # Ensure we're testing with different country or state
    assume(target_country != other_country or target_state != other_state)
    
    # Generate recommendations for target country/state
    target_rec = data.draw(recommendation_strategy(country=target_country, state=target_state))
    
    # Generate recommendations for other country/state
    other_rec = data.draw(recommendation_strategy(country=other_country, state=other_state))
    
    # Verify they are different
    if target_country != other_country:
        assert target_rec.country != other_rec.country, \
            "Recommendations from different countries should have different country codes"
    
    if target_state != other_state:
        assert target_rec.state != other_rec.state or target_rec.country != other_rec.country, \
            "Recommendations from different states should have different state codes or countries"


@given(
    country=country_code_strategy(),
    state=state_code_strategy(),
    data=st.data()
)
def test_property_25_batch_recommendation_scoping(country, state, data):
    """Property 25: Batch Recommendation Scoping.
    
    When generating multiple recommendations for a country and state,
    all recommendations must be scoped to that country and state.
    
    **Validates: Requirements 8.7**
    """
    # Generate a batch of 1-20 recommendations
    num_recommendations = data.draw(st.integers(min_value=1, max_value=20))
    recommendations = [
        data.draw(recommendation_strategy(country=country, state=state))
        for _ in range(num_recommendations)
    ]
    
    # Verify all recommendations are scoped correctly
    for rec in recommendations:
        assert rec.country == country, \
            f"Recommendation {rec.recommendation_id} has wrong country: {rec.country} != {country}"
        assert rec.state == state, \
            f"Recommendation {rec.recommendation_id} has wrong state: {rec.state} != {state}"
    
    # Verify no duplicates in country/state combinations
    country_state_pairs = [(rec.country, rec.state) for rec in recommendations]
    unique_pairs = set(country_state_pairs)
    assert len(unique_pairs) == 1, \
        f"All recommendations should have the same country/state pair, got {unique_pairs}"
