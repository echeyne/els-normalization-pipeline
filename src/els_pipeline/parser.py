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
    - 2 levels: Domain (0), Indicator (1), Subdomain=None, Strand=None
    - 3 levels: Domain (0), Subdomain (1), Indicator (2), Strand=None
    - 4+ levels: Domain (0), Subdomain (1), Strand (2), Indicator (3+)
    """
    if depth == 2:
        return {
            0: HierarchyLevelEnum.DOMAIN,
            1: HierarchyLevelEnum.INDICATOR,
        }
    elif depth == 3:
        return {
            0: HierarchyLevelEnum.DOMAIN,
            1: HierarchyLevelEnum.SUBDOMAIN,
            2: HierarchyLevelEnum.INDICATOR,
        }
    else:  # 4 or more levels
        return {
            0: HierarchyLevelEnum.DOMAIN,
            1: HierarchyLevelEnum.SUBDOMAIN,
            2: HierarchyLevelEnum.STRAND,
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
    subdomains = by_level.get(HierarchyLevelEnum.SUBDOMAIN, [])
    strands = by_level.get(HierarchyLevelEnum.STRAND, [])
    indicators = by_level.get(HierarchyLevelEnum.INDICATOR, [])
    
    for domain in domains:
        tree[domain.code] = {
            "element": domain,
            "subdomains": {},
        }
        
        # Match subdomains to this domain (by code prefix or simple matching)
        for subdomain in subdomains:
            if subdomain.code.startswith(domain.code):
                tree[domain.code]["subdomains"][subdomain.code] = {
                    "element": subdomain,
                    "strands": {},
                }
                
                # Match strands to this subdomain
                for strand in strands:
                    if strand.code.startswith(subdomain.code):
                        tree[domain.code]["subdomains"][subdomain.code]["strands"][
                            strand.code
                        ] = {
                            "element": strand,
                            "indicators": [],
                        }
                        
                        # Match indicators to this strand
                        for indicator in indicators:
                            if indicator.code.startswith(strand.code):
                                tree[domain.code]["subdomains"][subdomain.code][
                                    "strands"
                                ][strand.code]["indicators"].append(indicator)
    
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
            # Since we don't have subdomains/strands, indicators should be direct children
            # We need to handle this case differently
            pass
        elif depth == 3:
            # Domain + Subdomain + Indicator
            for subdomain_code, subdomain_data in domain_data["subdomains"].items():
                subdomain_element = subdomain_data["element"]
                subdomain_level = HierarchyLevel(
                    code=subdomain_element.code,
                    name=subdomain_element.title,
                    description=None,
                )
                
                # Find indicators for this subdomain
                # (indicators would be stored differently for depth 3)
                pass
        else:
            # Domain + Subdomain + Strand + Indicator
            for subdomain_code, subdomain_data in domain_data["subdomains"].items():
                subdomain_element = subdomain_data["element"]
                subdomain_level = HierarchyLevel(
                    code=subdomain_element.code,
                    name=subdomain_element.title,
                    description=None,
                )
                
                for strand_code, strand_data in subdomain_data["strands"].items():
                    strand_element = strand_data["element"]
                    strand_level = HierarchyLevel(
                        code=strand_element.code,
                        name=strand_element.title,
                        description=None,
                    )
                    
                    for indicator_element in strand_data["indicators"]:
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
                            subdomain=subdomain_level,
                            strand=strand_level,
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
        subdomains = by_canonical.get(HierarchyLevelEnum.SUBDOMAIN, [])
        strands = by_canonical.get(HierarchyLevelEnum.STRAND, [])
        indicators = by_canonical.get(HierarchyLevelEnum.INDICATOR, [])
        
        if not domains:
            return ParseResult(
                standards=[],
                orphaned_elements=valid_elements,
                status=StatusEnum.ERROR.value,
                error="No domain elements found",
            )
        
        if not indicators:
            return ParseResult(
                standards=[],
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
        current_subdomain = None
        current_strand = None
        
        # Process elements in document order to build hierarchy context
        # Use the original elements_with_canonical list which preserves order
        for element, canonical_level in elements_with_canonical:
            if canonical_level == HierarchyLevelEnum.DOMAIN:
                current_domain = element
                current_subdomain = None
                current_strand = None
            elif canonical_level == HierarchyLevelEnum.SUBDOMAIN:
                current_subdomain = element
                current_strand = None  # Reset strand when subdomain changes
            elif canonical_level == HierarchyLevelEnum.STRAND:
                current_strand = element
            elif canonical_level == HierarchyLevelEnum.INDICATOR:
                # Build standard using current context
                if not current_domain:
                    orphaned.append(element)
                    continue
                
                # For depth 3+, require subdomain
                if depth >= 3 and not current_subdomain:
                    orphaned.append(element)
                    continue
                
                # For depth 4, require strand
                if depth >= 4 and not current_strand:
                    orphaned.append(element)
                    continue
                
                # Build hierarchy levels
                domain_level = HierarchyLevel(
                    code=current_domain.code,
                    name=current_domain.title,
                    description=None,
                )
                
                subdomain_level = None
                if current_subdomain:
                    subdomain_level = HierarchyLevel(
                        code=current_subdomain.code,
                        name=current_subdomain.title,
                        description=None,
                    )
                
                strand_level = None
                if current_strand:
                    strand_level = HierarchyLevel(
                        code=current_strand.code,
                        name=current_strand.title,
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
                    subdomain=subdomain_level,
                    strand=strand_level,
                    indicator=indicator_level,
                    source_page=element.source_page,
                    source_text=element.source_text,
                )
                
                standards.append(standard)
        
        return ParseResult(
            standards=standards,
            orphaned_elements=orphaned,
            status=StatusEnum.SUCCESS.value,
            error=None,
        )
        
    except Exception as e:
        return ParseResult(
            standards=[],
            orphaned_elements=elements,
            status=StatusEnum.ERROR.value,
            error=f"Parsing failed: {str(e)}",
        )
