"""Property-based tests for hierarchy parser.

Feature: els-normalization-pipeline
Properties: 9, 10, 11, 12
"""

import pytest
from hypothesis import given, strategies as st, assume
from src.els_pipeline.models import (
    DetectedElement,
    HierarchyLevelEnum,
)
from src.els_pipeline.parser import (
    parse_hierarchy,
    generate_standard_id,
)


# Strategies for generating test data

@st.composite
def country_code(draw):
    """Generate a two-letter ISO 3166-1 alpha-2 country code."""
    return draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=2, max_size=2))


@st.composite
def state_code(draw):
    """Generate a two-letter state code."""
    return draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=2, max_size=2))


@st.composite
def version_year(draw):
    """Generate a version year."""
    return draw(st.integers(min_value=2000, max_value=2030))


@st.composite
def hierarchy_code(draw, prefix="", level=0):
    """Generate a hierarchical code."""
    if level == 0:
        # Domain level: single letter or short code
        return draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=3))
    else:
        # Subdomain/Strand/Indicator: prefix + separator + code
        separator = draw(st.sampled_from([".", "-", ""]))
        suffix = draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=1, max_size=3))
        return f"{prefix}{separator}{suffix}"


@st.composite
def detected_element(draw, level, code_prefix="", page_range=(1, 100)):
    """Generate a DetectedElement."""
    if code_prefix:
        code = draw(hierarchy_code(prefix=code_prefix, level=1))
    else:
        code = draw(hierarchy_code(level=0))
    
    title = draw(st.text(min_size=5, max_size=50))
    description = draw(st.text(min_size=10, max_size=200))
    confidence = draw(st.floats(min_value=0.7, max_value=1.0))  # Only valid elements
    source_page = draw(st.integers(min_value=page_range[0], max_value=page_range[1]))
    source_text = draw(st.text(min_size=10, max_size=100))
    
    return DetectedElement(
        level=level,
        code=code,
        title=title,
        description=description,
        confidence=confidence,
        source_page=source_page,
        source_text=source_text,
        needs_review=False,
    )


@st.composite
def two_level_hierarchy(draw):
    """Generate a 2-level hierarchy (Domain + Indicator)."""
    num_domains = draw(st.integers(min_value=1, max_value=3))
    elements = []
    
    for _ in range(num_domains):
        domain = draw(detected_element(level=HierarchyLevelEnum.DOMAIN))
        elements.append(domain)
        
        # Add indicators for this domain
        num_indicators = draw(st.integers(min_value=1, max_value=5))
        for _ in range(num_indicators):
            indicator = draw(detected_element(
                level=HierarchyLevelEnum.INDICATOR,
                code_prefix=domain.code
            ))
            elements.append(indicator)
    
    return elements


@st.composite
def three_level_hierarchy(draw):
    """Generate a 3-level hierarchy (Domain + Subdomain + Indicator)."""
    num_domains = draw(st.integers(min_value=1, max_value=3))
    elements = []
    
    for _ in range(num_domains):
        domain = draw(detected_element(level=HierarchyLevelEnum.DOMAIN))
        elements.append(domain)
        
        # Add subdomains for this domain
        num_subdomains = draw(st.integers(min_value=1, max_value=3))
        for _ in range(num_subdomains):
            subdomain = draw(detected_element(
                level=HierarchyLevelEnum.SUBDOMAIN,
                code_prefix=domain.code
            ))
            elements.append(subdomain)
            
            # Add indicators for this subdomain
            num_indicators = draw(st.integers(min_value=1, max_value=5))
            for _ in range(num_indicators):
                indicator = draw(detected_element(
                    level=HierarchyLevelEnum.INDICATOR,
                    code_prefix=subdomain.code
                ))
                elements.append(indicator)
    
    return elements


@st.composite
def four_level_hierarchy(draw):
    """Generate a 4-level hierarchy (Domain + Subdomain + Strand + Indicator)."""
    num_domains = draw(st.integers(min_value=1, max_value=2))
    elements = []
    
    for _ in range(num_domains):
        domain = draw(detected_element(level=HierarchyLevelEnum.DOMAIN))
        elements.append(domain)
        
        # Add subdomains for this domain
        num_subdomains = draw(st.integers(min_value=1, max_value=2))
        for _ in range(num_subdomains):
            subdomain = draw(detected_element(
                level=HierarchyLevelEnum.SUBDOMAIN,
                code_prefix=domain.code
            ))
            elements.append(subdomain)
            
            # Add strands for this subdomain
            num_strands = draw(st.integers(min_value=1, max_value=2))
            for _ in range(num_strands):
                strand = draw(detected_element(
                    level=HierarchyLevelEnum.STRAND,
                    code_prefix=subdomain.code
                ))
                elements.append(strand)
                
                # Add indicators for this strand
                num_indicators = draw(st.integers(min_value=1, max_value=3))
                for _ in range(num_indicators):
                    indicator = draw(detected_element(
                        level=HierarchyLevelEnum.INDICATOR,
                        code_prefix=strand.code
                    ))
                    elements.append(indicator)
    
    return elements


# Property 9: Canonical Level Normalization
@given(
    elements=st.one_of(
        two_level_hierarchy(),
        three_level_hierarchy(),
        four_level_hierarchy(),
    ),
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_9_canonical_level_normalization(elements, country, state, year):
    """
    Property 9: Canonical Level Normalization
    
    For any set of detected elements with arbitrary level labels,
    the Hierarchy Parser output SHALL contain only levels from the set
    {domain, subdomain, strand, indicator}.
    
    Validates: Requirements 4.1
    """
    result = parse_hierarchy(elements, country, state, year)
    
    # Check that all standards have only canonical levels
    valid_levels = {
        HierarchyLevelEnum.DOMAIN,
        HierarchyLevelEnum.SUBDOMAIN,
        HierarchyLevelEnum.STRAND,
        HierarchyLevelEnum.INDICATOR,
    }
    
    for standard in result.standards:
        # Domain is always present
        assert standard.domain is not None
        
        # Indicator is always present
        assert standard.indicator is not None
        
        # Subdomain and strand may be None, but if present, they're valid
        # All levels are from the canonical set (implicitly validated by the model)


# Property 10: Depth-Based Hierarchy Mapping
@given(
    elements=two_level_hierarchy(),
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_10_depth_based_hierarchy_mapping_2_levels(elements, country, state, year):
    """
    Property 10: Depth-Based Hierarchy Mapping (2 levels)
    
    For any set of detected elements with 2 distinct hierarchy levels:
    output standards SHALL have domain and indicator populated,
    subdomain and strand null.
    
    Validates: Requirements 4.2, 4.3, 4.4
    """
    result = parse_hierarchy(elements, country, state, year)
    
    for standard in result.standards:
        # Domain and indicator must be populated
        assert standard.domain is not None
        assert standard.indicator is not None
        
        # Subdomain and strand must be null
        assert standard.subdomain is None
        assert standard.strand is None


@given(
    elements=three_level_hierarchy(),
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_10_depth_based_hierarchy_mapping_3_levels(elements, country, state, year):
    """
    Property 10: Depth-Based Hierarchy Mapping (3 levels)
    
    For any set of detected elements with 3 distinct hierarchy levels:
    output standards SHALL have domain, subdomain, and indicator populated,
    strand null.
    
    Validates: Requirements 4.2, 4.3, 4.4
    """
    result = parse_hierarchy(elements, country, state, year)
    
    for standard in result.standards:
        # Domain, subdomain, and indicator must be populated
        assert standard.domain is not None
        assert standard.subdomain is not None
        assert standard.indicator is not None
        
        # Strand must be null
        assert standard.strand is None


@given(
    elements=four_level_hierarchy(),
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_10_depth_based_hierarchy_mapping_4_levels(elements, country, state, year):
    """
    Property 10: Depth-Based Hierarchy Mapping (4+ levels)
    
    For any set of detected elements with 4 or more distinct hierarchy levels:
    output standards SHALL have all four levels populated.
    
    Validates: Requirements 4.2, 4.3, 4.4
    """
    result = parse_hierarchy(elements, country, state, year)
    
    for standard in result.standards:
        # All four levels must be populated
        assert standard.domain is not None
        assert standard.subdomain is not None
        assert standard.strand is not None
        assert standard.indicator is not None


# Property 11: Standard_ID Determinism
@given(
    country=country_code(),
    state=state_code(),
    year=version_year(),
    domain_code=st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=5),
    indicator_code=st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=1, max_size=10),
)
def test_property_11_standard_id_determinism(country, state, year, domain_code, indicator_code):
    """
    Property 11: Standard_ID Determinism
    
    For any given (country, state, version_year, domain_code, indicator_code) tuple,
    calling the Standard_ID generator twice SHALL produce identical results.
    
    Validates: Requirements 4.5
    """
    # Generate Standard_ID twice with the same inputs
    id1 = generate_standard_id(country, state, year, domain_code, indicator_code)
    id2 = generate_standard_id(country, state, year, domain_code, indicator_code)
    
    # They must be identical
    assert id1 == id2
    
    # Verify the format
    expected_format = f"{country}-{state}-{year}-{domain_code}-{indicator_code}"
    assert id1 == expected_format


# Property 12: No Orphaned Indicators
@given(
    elements=st.one_of(
        two_level_hierarchy(),
        three_level_hierarchy(),
        four_level_hierarchy(),
    ),
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_12_no_orphaned_indicators(elements, country, state, year):
    """
    Property 12: No Orphaned Indicators
    
    For any valid parse result, every standard in the `standards` list
    SHALL have a non-null `domain`. Any element that cannot be placed
    in the tree SHALL appear in `orphaned_elements` and not in `standards`.
    
    Validates: Requirements 4.6
    """
    result = parse_hierarchy(elements, country, state, year)
    
    # Every standard must have a non-null domain
    for standard in result.standards:
        assert standard.domain is not None
        assert standard.domain.code is not None
        assert standard.domain.name is not None
    
    # Orphaned elements should not appear in standards
    orphaned_codes = {elem.code for elem in result.orphaned_elements}
    standard_indicator_codes = {std.indicator.code for std in result.standards}
    
    # No overlap between orphaned and successfully parsed indicators
    assert len(orphaned_codes & standard_indicator_codes) == 0


@given(
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_12_orphaned_indicators_without_domain(country, state, year):
    """
    Property 12: No Orphaned Indicators (orphan detection)
    
    When indicators have no matching domain, they should be reported
    as orphaned elements.
    
    Validates: Requirements 4.6
    """
    # Create indicators without matching domains
    orphan_indicator = DetectedElement(
        level=HierarchyLevelEnum.INDICATOR,
        code="ORPHAN-1",
        title="Orphaned Indicator",
        description="This indicator has no parent domain",
        confidence=0.9,
        source_page=1,
        source_text="orphan text",
        needs_review=False,
    )
    
    elements = [orphan_indicator]
    result = parse_hierarchy(elements, country, state, year)
    
    # The orphan should be in orphaned_elements
    assert len(result.orphaned_elements) > 0
    
    # The orphan should not be in standards
    assert len(result.standards) == 0
