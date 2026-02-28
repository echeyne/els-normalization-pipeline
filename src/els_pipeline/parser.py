"""Hierarchy parser for ELS pipeline."""

from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
from .models import (
    DetectedElement,
    NormalizedStandard,
    ParseResult,
    HierarchyLevel,
    HierarchyLevelEnum,
    StatusEnum,
)


def detect_hierarchy_depth(elements: List[DetectedElement]) -> int:
    """
    Detect the number of distinct hierarchy levels in the input elements.
    
    Args:
        elements: List of detected elements
        
    Returns:
        Number of distinct hierarchy levels (2, 3, 4, or more)
    """
    levels = set(element.level for element in elements)
    return len(levels)


def normalize_hierarchy_mapping(depth: int) -> Dict[int, Optional[HierarchyLevelEnum]]:
    """
    Create a mapping from detected level index to canonical level.
    
    Args:
        depth: Number of distinct hierarchy levels
        
    Returns:
        Dictionary mapping level index to canonical HierarchyLevelEnum
        
    Mapping rules:
    - 2 levels: Domain (0), Indicator (1), Strand=None, Sub_strand=None
    - 3 levels: Domain (0), Strand (1), Indicator (2), Sub_strand=None
    - 4+ levels: Domain (0), Strand (1), Sub_strand (2), Indicator (3+)
    """
    if depth == 2:
        return {
            0: HierarchyLevelEnum.DOMAIN,
            1: HierarchyLevelEnum.INDICATOR,
        }
    elif depth == 3:
        return {
            0: HierarchyLevelEnum.DOMAIN,
            1: HierarchyLevelEnum.STRAND,
            2: HierarchyLevelEnum.INDICATOR,
        }
    else:  # 4 or more levels
        return {
            0: HierarchyLevelEnum.DOMAIN,
            1: HierarchyLevelEnum.STRAND,
            2: HierarchyLevelEnum.SUB_STRAND,
            3: HierarchyLevelEnum.INDICATOR,
        }


def assign_canonical_levels(
    elements: List[DetectedElement]
) -> List[Tuple[DetectedElement, HierarchyLevelEnum]]:
    """
    Assign canonical hierarchy levels to detected elements based on depth.
    Preserves document order and uses first appearance to determine level position.
    
    Args:
        elements: List of detected elements with original levels
        
    Returns:
        List of tuples (element, canonical_level) in document order
    """
    # Track first appearance of each level to determine document order
    first_appearance: Dict[HierarchyLevelEnum, int] = {}
    for idx, element in enumerate(elements):
        if element.level not in first_appearance:
            first_appearance[element.level] = idx
    
    # Sort levels by their first appearance in the document
    present_levels = sorted(first_appearance.keys(), key=lambda level: first_appearance[level])
    depth = len(present_levels)
    
    # Get the canonical mapping based on depth
    mapping = normalize_hierarchy_mapping(depth)
    
    # Create a mapping from original level to canonical level
    # based on the order levels appear in the document
    original_to_canonical = {}
    for idx, original_level in enumerate(present_levels):
        canonical_level = mapping.get(idx)
        if canonical_level:
            original_to_canonical[original_level] = canonical_level
    
    # Assign canonical levels while preserving document order
    result = []
    for element in elements:
        canonical_level = original_to_canonical.get(element.level)
        if canonical_level:
            result.append((element, canonical_level))
    
    return result


def generate_standard_id(
    country: str, state: str, version_year: int, domain_code: str, indicator_code: str
) -> str:
    """
    Generate a deterministic Standard_ID.
    
    Args:
        country: Two-letter ISO 3166-1 alpha-2 country code
        state: Two-letter state code
        version_year: Year of the standards version
        domain_code: Domain code
        indicator_code: Indicator code
        
    Returns:
        Standard_ID in format: {COUNTRY}-{STATE}-{YEAR}-{DOMAIN_CODE}-{INDICATOR_CODE}
    """
    return f"{country}-{state}-{version_year}-{domain_code}-{indicator_code}"


def build_hierarchy_tree(
    elements_with_levels: List[Tuple[DetectedElement, HierarchyLevelEnum]]
) -> Dict[str, Dict]:
    """
    Build a hierarchy tree from elements with canonical levels.
    
    Args:
        elements_with_levels: List of (element, canonical_level) tuples
        
    Returns:
        Dictionary representing the hierarchy tree structure
    """
    tree: Dict[str, Dict] = {}
    
    # Group by canonical level
    by_level: Dict[HierarchyLevelEnum, List[DetectedElement]] = defaultdict(list)
    for element, canonical_level in elements_with_levels:
        by_level[canonical_level].append(element)
    
    # Build tree structure
    domains = by_level.get(HierarchyLevelEnum.DOMAIN, [])
    strands = by_level.get(HierarchyLevelEnum.STRAND, [])
    sub_strands = by_level.get(HierarchyLevelEnum.SUB_STRAND, [])
    indicators = by_level.get(HierarchyLevelEnum.INDICATOR, [])
    
    for domain in domains:
        tree[domain.code] = {
            "element": domain,
            "strands": {},
        }
        
        # Match strands to this domain (by code prefix or simple matching)
        for strand in strands:
            if strand.code.startswith(domain.code):
                tree[domain.code]["strands"][strand.code] = {
                    "element": strand,
                    "sub_strands": {},
                }
                
                # Match sub_strands to this strand
                for sub_strand in sub_strands:
                    if sub_strand.code.startswith(strand.code):
                        tree[domain.code]["strands"][strand.code]["sub_strands"][
                            sub_strand.code
                        ] = {
                            "element": sub_strand,
                            "indicators": [],
                        }
                        
                        # Match indicators to this sub_strand
                        for indicator in indicators:
                            if indicator.code.startswith(sub_strand.code):
                                tree[domain.code]["strands"][strand.code][
                                    "sub_strands"
                                ][sub_strand.code]["indicators"].append(indicator)
    
    return tree


def extract_standards_from_tree(
    tree: Dict[str, Dict],
    country: str,
    state: str,
    version_year: int,
    depth: int,
) -> List[NormalizedStandard]:
    """
    Extract NormalizedStandard objects from the hierarchy tree.
    
    Args:
        tree: Hierarchy tree structure
        country: Two-letter ISO 3166-1 alpha-2 country code
        state: State code
        version_year: Version year
        depth: Hierarchy depth
        
    Returns:
        List of NormalizedStandard objects
    """
    standards = []
    
    for domain_code, domain_data in tree.items():
        domain_element = domain_data["element"]
        domain_level = HierarchyLevel(
            code=domain_element.code,
            name=domain_element.title,
            description=None,
        )
        
        if depth == 2:
            # Domain + Indicator only
            # Find indicators that belong to this domain
            # Since we don't have strands/sub_strands, indicators should be direct children
            # We need to handle this case differently
            pass
        elif depth == 3:
            # Domain + Strand + Indicator
            for strand_code, strand_data in domain_data["strands"].items():
                strand_element = strand_data["element"]
                strand_level = HierarchyLevel(
                    code=strand_element.code,
                    name=strand_element.title,
                    description=None,
                )
                
                # Find indicators for this strand
                # (indicators would be stored differently for depth 3)
                pass
        else:
            # Domain + Strand + Sub_strand + Indicator
            for strand_code, strand_data in domain_data["strands"].items():
                strand_element = strand_data["element"]
                strand_level = HierarchyLevel(
                    code=strand_element.code,
                    name=strand_element.title,
                    description=None,
                )
                
                for sub_strand_code, sub_strand_data in strand_data["sub_strands"].items():
                    sub_strand_element = sub_strand_data["element"]
                    sub_strand_level = HierarchyLevel(
                        code=sub_strand_element.code,
                        name=sub_strand_element.title,
                        description=None,
                    )
                    
                    for indicator_element in sub_strand_data["indicators"]:
                        indicator_level = HierarchyLevel(
                            code=indicator_element.code,
                            name=indicator_element.title,
                            description=indicator_element.description,
                        )
                        
                        standard_id = generate_standard_id(
                            country, state, version_year, domain_code, indicator_element.code
                        )
                        
                        standard = NormalizedStandard(
                            standard_id=standard_id,
                            country=country,
                            state=state,
                            version_year=version_year,
                            domain=domain_level,
                            strand=strand_level,
                            sub_strand=sub_strand_level,
                            indicator=indicator_level,
                            source_page=indicator_element.source_page,
                            source_text=indicator_element.source_text,
                        )
                        standards.append(standard)
    
    return standards


def parse_hierarchy(
    elements: List[DetectedElement], country: str, state: str, version_year: int
) -> ParseResult:
    """
    Parse detected elements into normalized standards with canonical hierarchy.
    
    This function:
    1. Detects the number of distinct hierarchy levels
    2. Applies depth normalization based on detected levels
    3. Generates deterministic Standard_IDs
    4. Assembles the hierarchy tree
    5. Detects orphaned elements (no path to domain)
    
    Args:
        elements: List of detected hierarchical elements
        country: Two-letter ISO 3166-1 alpha-2 country code
        state: Two-letter state code
        version_year: Year of the standards version
        
    Returns:
        ParseResult containing normalized standards and orphaned elements
    """
    try:
        # Filter out elements flagged for review
        valid_elements = [e for e in elements if not e.needs_review]
        
        if not valid_elements:
            return ParseResult(
                standards=[],
                indicators=[],
                orphaned_elements=elements,
                status=StatusEnum.ERROR.value,
                error="No valid elements to parse (all flagged for review)",
            )
        
        # Detect hierarchy depth
        depth = detect_hierarchy_depth(valid_elements)
        
        # Assign canonical levels based on depth
        elements_with_canonical = assign_canonical_levels(valid_elements)
        
        # Group by canonical level for easier processing
        by_canonical: Dict[HierarchyLevelEnum, List[DetectedElement]] = defaultdict(
            list
        )
        for element, canonical_level in elements_with_canonical:
            by_canonical[canonical_level].append(element)
        
        # Extract components
        domains = by_canonical.get(HierarchyLevelEnum.DOMAIN, [])
        strands = by_canonical.get(HierarchyLevelEnum.STRAND, [])
        sub_strands = by_canonical.get(HierarchyLevelEnum.SUB_STRAND, [])
        indicators = by_canonical.get(HierarchyLevelEnum.INDICATOR, [])
        
        if not domains:
            return ParseResult(
                standards=[],
                indicators=[],
                orphaned_elements=valid_elements,
                status=StatusEnum.ERROR.value,
                error="No domain elements found",
            )
        
        if not indicators:
            return ParseResult(
                standards=[],
                indicators=[],
                orphaned_elements=valid_elements,
                status=StatusEnum.ERROR.value,
                error="No indicator elements found",
            )
        
        # Build standards based on depth using document order
        standards = []
        orphaned = []
        
        # Build a context-aware hierarchy using document order
        # Track the current parent at each level as we iterate through elements
        current_domain = None
        current_strand = None
        current_sub_strand = None
        
        # Process elements in document order to build hierarchy context
        # Use the original elements_with_canonical list which preserves order
        for element, canonical_level in elements_with_canonical:
            if canonical_level == HierarchyLevelEnum.DOMAIN:
                current_domain = element
                current_strand = None
                current_sub_strand = None
            elif canonical_level == HierarchyLevelEnum.STRAND:
                current_strand = element
                current_sub_strand = None  # Reset sub_strand when strand changes
            elif canonical_level == HierarchyLevelEnum.SUB_STRAND:
                current_sub_strand = element
            elif canonical_level == HierarchyLevelEnum.INDICATOR:
                # Build standard using current context (document-order parenting).
                # We do NOT require code-prefix matching because many state
                # standards use independent coding schemes (e.g. domain "ATL"
                # with indicator "1.1").  Document order is the authoritative
                # signal for parent–child relationships.
                if not current_domain:
                    orphaned.append(element)
                    continue
                
                # Build hierarchy levels
                domain_level = HierarchyLevel(
                    code=current_domain.code,
                    name=current_domain.title,
                    description=None,
                )
                
                strand_level = None
                if current_strand:
                    strand_level = HierarchyLevel(
                        code=current_strand.code,
                        name=current_strand.title,
                        description=None,
                    )
                
                sub_strand_level = None
                if current_sub_strand:
                    sub_strand_level = HierarchyLevel(
                        code=current_sub_strand.code,
                        name=current_sub_strand.title,
                        description=None,
                    )
                
                indicator_level = HierarchyLevel(
                    code=element.code,
                    name=element.title,
                    description=element.description,
                )
                
                # Generate Standard_ID
                standard_id = generate_standard_id(
                    country, state, version_year, current_domain.code, element.code
                )
                
                # Create NormalizedStandard
                standard = NormalizedStandard(
                    standard_id=standard_id,
                    country=country,
                    state=state,
                    version_year=version_year,
                    domain=domain_level,
                    strand=strand_level,
                    sub_strand=sub_strand_level,
                    indicator=indicator_level,
                    source_page=element.source_page,
                    source_text=element.source_text,
                )
                
                standards.append(standard)
        
        return ParseResult(
            standards=standards,
            indicators=[standard.model_dump() for standard in standards],
            orphaned_elements=orphaned,
            status=StatusEnum.SUCCESS.value,
            error=None,
        )
        
    except Exception as e:
        return ParseResult(
            standards=[],
            indicators=[],
            orphaned_elements=elements,
            status=StatusEnum.ERROR.value,
            error=f"Parsing failed: {str(e)}",
        )
