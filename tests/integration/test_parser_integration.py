"""Integration tests for hierarchy parser."""

import pytest
from src.els_pipeline.models import DetectedElement, HierarchyLevelEnum
from src.els_pipeline.parser import parse_hierarchy, generate_standard_id


class TestDepthNormalization:
    """Test depth normalization for different hierarchy levels."""
    
    def test_two_level_hierarchy(self):
        """Test parsing a 2-level hierarchy (Domain + Indicator)."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN,
                code="LLD",
                title="Language and Literacy Development",
                description="Language domain",
                confidence=0.95,
                source_page=1,
                source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="LLD.1",
                title="Listening Skills",
                description="Child demonstrates listening skills",
                confidence=0.90,
                source_page=2,
                source_text="LLD.1 indicator text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="LLD.2",
                title="Speaking Skills",
                description="Child demonstrates speaking skills",
                confidence=0.92,
                source_page=3,
                source_text="LLD.2 indicator text",
                needs_review=False,
            ),
        ]
        
        result = parse_hierarchy(elements, "US", "CA", 2021)
        
        assert result.status == "success"
        assert len(result.standards) == 2
        
        for standard in result.standards:
            # Domain and indicator must be populated
            assert standard.domain is not None
            assert standard.domain.code == "LLD"
            assert standard.indicator is not None
            
            # Strand and sub_strand must be null
            assert standard.strand is None
            assert standard.sub_strand is None
    
    def test_three_level_hierarchy(self):
        """Test parsing a 3-level hierarchy (Domain + Strand + Indicator)."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN,
                code="LLD",
                title="Language and Literacy Development",
                description="Language domain",
                confidence=0.95,
                source_page=1,
                source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.STRAND,
                code="LLD.A",
                title="Listening and Speaking",
                description="Listening and speaking strand",
                confidence=0.93,
                source_page=2,
                source_text="LLD.A strand text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="LLD.A.1",
                title="Comprehension",
                description="Child demonstrates understanding",
                confidence=0.90,
                source_page=3,
                source_text="LLD.A.1 indicator text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="LLD.A.2",
                title="Expression",
                description="Child expresses ideas clearly",
                confidence=0.91,
                source_page=4,
                source_text="LLD.A.2 indicator text",
                needs_review=False,
            ),
        ]
        
        result = parse_hierarchy(elements, "US", "CA", 2021)
        
        assert result.status == "success"
        assert len(result.standards) == 2
        
        for standard in result.standards:
            # Domain, strand, and indicator must be populated
            assert standard.domain is not None
            assert standard.domain.code == "LLD"
            assert standard.strand is not None
            assert standard.strand.code == "LLD.A"
            assert standard.indicator is not None
            
            # Sub_strand must be null
            assert standard.sub_strand is None
    
    def test_four_level_hierarchy(self):
        """Test parsing a 4-level hierarchy (Domain + Strand + Sub-strand + Indicator)."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN,
                code="LLD",
                title="Language and Literacy Development",
                description="Language domain",
                confidence=0.95,
                source_page=1,
                source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.STRAND,
                code="LLD.A",
                title="Listening and Speaking",
                description="Listening and speaking strand",
                confidence=0.93,
                source_page=2,
                source_text="LLD.A strand text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.SUB_STRAND,
                code="LLD.A.1",
                title="Comprehension",
                description="Comprehension sub-strand",
                confidence=0.92,
                source_page=3,
                source_text="LLD.A.1 sub-strand text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="LLD.A.1.a",
                title="Understanding Complex Language",
                description="Child demonstrates understanding of complex language",
                confidence=0.90,
                source_page=4,
                source_text="LLD.A.1.a indicator text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="LLD.A.1.b",
                title="Following Directions",
                description="Child follows multi-step directions",
                confidence=0.91,
                source_page=5,
                source_text="LLD.A.1.b indicator text",
                needs_review=False,
            ),
        ]
        
        result = parse_hierarchy(elements, "US", "CA", 2021)
        
        assert result.status == "success"
        assert len(result.standards) == 2
        
        for standard in result.standards:
            # All four levels must be populated
            assert standard.domain is not None
            assert standard.domain.code == "LLD"
            assert standard.strand is not None
            assert standard.strand.code == "LLD.A"
            assert standard.sub_strand is not None
            assert standard.sub_strand.code == "LLD.A.1"
            assert standard.indicator is not None


class TestStandardIDGeneration:
    """Test Standard_ID generation and determinism."""
    
    def test_standard_id_format(self):
        """Test that Standard_ID follows the correct format."""
        standard_id = generate_standard_id("US", "CA", 2021, "LLD", "LLD.A.1.a")
        
        assert standard_id == "US-CA-2021-LLD-LLD.A.1.a"
        assert standard_id.startswith("US-")
        assert "2021" in standard_id
    
    def test_standard_id_determinism(self):
        """Test that Standard_ID generation is deterministic."""
        id1 = generate_standard_id("US", "CA", 2021, "LLD", "LLD.A.1.a")
        id2 = generate_standard_id("US", "CA", 2021, "LLD", "LLD.A.1.a")
        
        assert id1 == id2
    
    def test_standard_id_uniqueness(self):
        """Test that different inputs produce different Standard_IDs."""
        id1 = generate_standard_id("US", "CA", 2021, "LLD", "LLD.A.1.a")
        id2 = generate_standard_id("US", "CA", 2021, "LLD", "LLD.A.1.b")
        id3 = generate_standard_id("US", "TX", 2021, "LLD", "LLD.A.1.a")
        
        assert id1 != id2
        assert id1 != id3
        assert id2 != id3
    
    def test_standard_id_in_parsed_result(self):
        """Test that parsed standards have correct Standard_IDs."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN,
                code="LLD",
                title="Language and Literacy Development",
                description="Language domain",
                confidence=0.95,
                source_page=1,
                source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="LLD.1",
                title="Listening Skills",
                description="Child demonstrates listening skills",
                confidence=0.90,
                source_page=2,
                source_text="LLD.1 indicator text",
                needs_review=False,
            ),
        ]
        
        result = parse_hierarchy(elements, "US", "CA", 2021)
        
        assert len(result.standards) == 1
        standard = result.standards[0]
        
        expected_id = "US-CA-2021-LLD-LLD.1"
        assert standard.standard_id == expected_id


class TestOrphanDetection:
    """Test orphan detection for elements without parent hierarchy."""
    
    def test_orphaned_indicator_without_domain(self):
        """Test that indicators without matching domains are orphaned."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="ORPHAN.1",
                title="Orphaned Indicator",
                description="This indicator has no parent domain",
                confidence=0.90,
                source_page=1,
                source_text="orphan text",
                needs_review=False,
            ),
        ]
        
        result = parse_hierarchy(elements, "US", "CA", 2021)
        
        # The orphan should be in orphaned_elements
        assert len(result.orphaned_elements) == 1
        assert result.orphaned_elements[0].code == "ORPHAN.1"
        
        # The orphan should not be in standards
        assert len(result.standards) == 0
    
    def test_valid_and_orphaned_mixed(self):
        """Test parsing with both valid and orphaned elements."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN,
                code="LLD",
                title="Language and Literacy Development",
                description="Language domain",
                confidence=0.95,
                source_page=1,
                source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="LLD.1",
                title="Valid Indicator",
                description="This indicator has a parent domain",
                confidence=0.90,
                source_page=2,
                source_text="valid text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="ORPHAN.1",
                title="Orphaned Indicator",
                description="This indicator has no parent domain",
                confidence=0.90,
                source_page=3,
                source_text="orphan text",
                needs_review=False,
            ),
        ]
        
        result = parse_hierarchy(elements, "US", "CA", 2021)
        
        # One valid standard
        assert len(result.standards) == 1
        assert result.standards[0].indicator.code == "LLD.1"
        
        # One orphaned element
        assert len(result.orphaned_elements) == 1
        assert result.orphaned_elements[0].code == "ORPHAN.1"


class TestTreeAssembly:
    """Test tree assembly with various input structures."""
    
    def test_multiple_domains(self):
        """Test parsing with multiple domains."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN,
                code="LLD",
                title="Language and Literacy Development",
                description="Language domain",
                confidence=0.95,
                source_page=1,
                source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="LLD.1",
                title="Listening Skills",
                description="Child demonstrates listening skills",
                confidence=0.90,
                source_page=2,
                source_text="LLD.1 indicator text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN,
                code="CD",
                title="Cognitive Development",
                description="Cognitive domain",
                confidence=0.95,
                source_page=3,
                source_text="CD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="CD.1",
                title="Problem Solving",
                description="Child demonstrates problem solving",
                confidence=0.90,
                source_page=4,
                source_text="CD.1 indicator text",
                needs_review=False,
            ),
        ]
        
        result = parse_hierarchy(elements, "US", "CA", 2021)
        
        assert result.status == "success"
        assert len(result.standards) == 2
        
        # Check that each standard has the correct domain
        domains = {std.domain.code for std in result.standards}
        assert domains == {"LLD", "CD"}
    
    def test_elements_flagged_for_review(self):
        """Test that elements flagged for review are excluded."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN,
                code="LLD",
                title="Language and Literacy Development",
                description="Language domain",
                confidence=0.95,
                source_page=1,
                source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="LLD.1",
                title="Valid Indicator",
                description="This indicator is valid",
                confidence=0.90,
                source_page=2,
                source_text="valid text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR,
                code="LLD.2",
                title="Low Confidence Indicator",
                description="This indicator needs review",
                confidence=0.60,
                source_page=3,
                source_text="low confidence text",
                needs_review=True,
            ),
        ]
        
        result = parse_hierarchy(elements, "US", "CA", 2021)
        
        # Only the valid indicator should be parsed
        assert len(result.standards) == 1
        assert result.standards[0].indicator.code == "LLD.1"
    
    def test_empty_elements_list(self):
        """Test parsing with an empty elements list."""
        elements = []
        
        result = parse_hierarchy(elements, "US", "CA", 2021)
        
        assert result.status == "error"
        assert len(result.standards) == 0
        assert result.error is not None
    
    def test_no_indicators(self):
        """Test parsing with only domains (no indicators)."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN,
                code="LLD",
                title="Language and Literacy Development",
                description="Language domain",
                confidence=0.95,
                source_page=1,
                source_text="LLD domain text",
                needs_review=False,
            ),
        ]
        
        result = parse_hierarchy(elements, "US", "CA", 2021)
        
        assert result.status == "error"
        assert len(result.standards) == 0
        assert "No indicator elements found" in result.error
