"""Structure detection module for ELS pipeline."""

import json
import logging
from typing import List, Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

from .models import TextBlock, DetectedElement, DetectionResult, HierarchyLevelEnum
from .config import Config

logger = logging.getLogger(__name__)

# Constants
CHARS_PER_TOKEN = 4
DEFAULT_TARGET_TOKENS = 2000
DEFAULT_OVERLAP_TOKENS = 200
MAX_PARSE_RETRIES = 2
MAX_BEDROCK_RETRIES = 2
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 16000


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text string.
    Uses a simple heuristic: ~4 characters per token.
    
    Args:
        text: Input text string
        
    Returns:
        Estimated token count
    """
    return len(text) // CHARS_PER_TOKEN


def _create_overlap_blocks(chunk: List[TextBlock], overlap_tokens: int) -> tuple[List[TextBlock], int]:
    """
    Create overlap blocks from the end of a chunk.
    
    Args:
        chunk: Current chunk of text blocks
        overlap_tokens: Target number of tokens for overlap
        
    Returns:
        Tuple of (overlap blocks, total overlap tokens)
    """
    overlap_blocks = []
    overlap_token_count = 0
    
    for prev_block in reversed(chunk):
        prev_tokens = estimate_tokens(prev_block.text)
        if overlap_token_count + prev_tokens <= overlap_tokens:
            overlap_blocks.insert(0, prev_block)
            overlap_token_count += prev_tokens
        else:
            break
    
    return overlap_blocks, overlap_token_count


def chunk_text_blocks(
    blocks: List[TextBlock], 
    target_tokens: int = DEFAULT_TARGET_TOKENS, 
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS
) -> List[List[TextBlock]]:
    """
    Chunk text blocks into groups of approximately target_tokens with overlap.
    
    This ensures the LLM can process large documents while maintaining context
    across chunk boundaries through overlapping content.
    
    Args:
        blocks: List of text blocks to chunk
        target_tokens: Target number of tokens per chunk (default: 2000)
        overlap_tokens: Number of tokens to overlap between chunks (default: 200)
        
    Returns:
        List of text block chunks, each containing approximately target_tokens
    """
    if not blocks:
        return []
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for block in blocks:
        block_tokens = estimate_tokens(block.text)
        
        # If adding this block would exceed target, finalize current chunk
        if current_chunk and current_tokens + block_tokens > target_tokens:
            chunks.append(current_chunk)
            
            # Create overlap from the end of the previous chunk
            overlap_blocks, overlap_token_count = _create_overlap_blocks(
                current_chunk, overlap_tokens
            )
            
            current_chunk = overlap_blocks
            current_tokens = overlap_token_count
        
        current_chunk.append(block)
        current_tokens += block_tokens
    
    # Add the final chunk if it has content
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def build_detection_prompt(blocks: List[TextBlock]) -> str:
    """
    Build a structured prompt for the LLM to detect hierarchy elements.
    
    The prompt is designed to extract educational standards hierarchy from
    early learning standards documents, identifying domains, subdomains,
    strands, and indicators with their associated metadata.
    
    Args:
        blocks: List of text blocks to analyze
        
    Returns:
        Formatted prompt string optimized for Claude Sonnet 4.5
    """
    # Combine text blocks with page numbers for context
    text_content = "\n".join([
        f"[Page {block.page_number}] {block.text}"
        for block in blocks
    ])
    
    prompt = f"""You are extracting the hierarchical structure from an early learning standards document. Your job is to identify every structural element and classify it into the correct hierarchy level.

STRICT RULE: You must use ONLY the exact titles, codes (as applicable), numbers, and names that appear in the document text. Do NOT invent any titles. If a code does not exist, assign an appropriate one.

HIERARCHY LEVELS (from highest to lowest):
1. "domain" — The broadest organizational category. These are top-level developmental areas that contain everything else. They typically appear as section headers or in a table of contents.
2. "subdomain" — An optional grouping within a domain, used by some states but not all. Only classify something as a subdomain if the document explicitly uses a term like "sub-strand", "sub-domain", "sub-area", or similar. Do NOT create subdomains that the document does not define.
3. "strand" — A major category within a domain. These are typically numbered groupings (e.g., "1.0", "2.0") that organize related indicators together.
4. "indicator" — The most specific level. These are individual learning goals, foundations, benchmarks, or skill statements. They describe what a child should know or be able to do. They are typically numbered with a decimal (e.g., "1.1", "1.2", "2.1").

HOW TO CLASSIFY:
- Look at how the document itself organizes content. Use the document's own hierarchy, not your assumptions.
- If the document labels something as a "Domain", "Area", or uses it as a top-level header, classify it as "domain".
- If the document labels something as a "Strand", "Standard", "Goal", or similar numbered grouping under a domain, classify it as "strand".
- If the document labels something as a "Sub-Strand", "Sub-Domain", or similar, classify it as "subdomain".
- If the document labels something as a "Foundation", "Indicator", "Benchmark", "Objective", "Skill", or it is a specific numbered learning statement, classify it as "indicator".
- Age-specific descriptions (e.g., "Early (3 to 4 ½ Years)", "Later (4 to 5 1/2 Years)", "By 36 months") are NOT separate elements. Include them as part of the parent indicator's description.

FIELD INSTRUCTIONS:
- "level": One of "domain", "subdomain", "strand", or "indicator".
- "code": The code or number from the document (e.g., "1.0", "1.1", "ATL"). If the document does not assign a code, apply an appropriate one"".
- "title": The exact title as written in the document. Do NOT paraphrase or shorten it.
- "description": The full descriptive text associated with this element, including any age-band details. Combine all age-specific text into one description. If there is no description beyond the title, use an empty string "".
- "confidence": A float between 0.0 and 1.0 reflecting how certain you are about the classification:
  - 0.95+ : Element is explicitly labeled with its level and has a clear code.
  - 0.85-0.94 : Element has clear structural cues but is not explicitly labeled.
  - 0.70-0.84 : Element fits the pattern but has some ambiguity.
  - Below 0.70 : Uncertain classification.
- "source_page": The page number from the [Page N] marker where this element appears.
- "source_text": The exact text from the document that you used to identify this element. Copy it verbatim.

OUTPUT FORMAT — Return ONLY a JSON array. No text before or after it.
[
  {{
    "level": "domain|subdomain|strand|indicator",
    "code": "exact code from document or empty string",
    "title": "exact title from document",
    "description": "full description from document including age-specific details",
    "confidence": 0.95,
    "source_page": 1,
    "source_text": "exact text copied from document"
  }}
]

FINAL REMINDERS:
- Return ONLY the JSON array. No markdown, no explanation, no commentary.
- Extract EVERY structural element you find. Do not skip any.
- Use the page numbers from the [Page N] markers in the text.

TEXT TO ANALYZE:

{text_content}"""
    
    return prompt


def _extract_json_from_response(response_text: str) -> str:
    """
    Extract JSON array from LLM response text.
    
    The LLM may sometimes include extra text before or after the JSON.
    This function extracts just the JSON array portion.
    
    Args:
        response_text: Raw response text from LLM
        
    Returns:
        Extracted JSON string
        
    Raises:
        ValueError: If no valid JSON array is found
    """
    response_text = response_text.strip()
    
    # Strip markdown code fences if present (e.g. ```json ... ```)
    if response_text.startswith("```"):
        lines = response_text.splitlines()
        # Drop the opening fence line and any closing fence
        response_text = "\n".join(
            line for line in lines[1:]
            if not line.strip().startswith("```")
        ).strip()
    
    logger.debug(f"Extracting JSON from response of length {len(response_text)}")
    
    # Find JSON array boundaries
    start_idx = response_text.find('[')
    end_idx = response_text.rfind(']')
    
    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        logger.error(f"No valid JSON array found. Response text: {response_text[:1000]}")
        raise ValueError("No valid JSON array found in response")
    
    json_str = response_text[start_idx:end_idx + 1]
    logger.debug(f"Extracted JSON string of length {len(json_str)}")
    
    return json_str


def _validate_element_data(elem_data: Dict[str, Any]) -> Optional[str]:
    """
    Validate element data has all required fields.
    
    Args:
        elem_data: Dictionary containing element data
        
    Returns:
        Error message if validation fails, None if valid
    """
    required_fields = ['level', 'code', 'title', 'description', 'confidence', 'source_page', 'source_text']
    missing_fields = [field for field in required_fields if field not in elem_data]
    
    if missing_fields:
        return f"Missing required fields: {missing_fields}"
    
    return None


def _create_detected_element(elem_data: Dict[str, Any], default_page: int) -> Optional[DetectedElement]:
    """
    Create a DetectedElement from validated element data.
    
    Args:
        elem_data: Dictionary containing element data
        default_page: Default page number if source_page is invalid
        
    Returns:
        DetectedElement object, or None if creation fails
    """
    try:
        # Validate and convert level
        level = HierarchyLevelEnum(elem_data['level'])
    except ValueError:
        logger.warning(f"Invalid hierarchy level '{elem_data['level']}', skipping element")
        return None
    
    # Ensure confidence is in valid range [0.0, 1.0]
    confidence = float(elem_data['confidence'])
    confidence = max(0.0, min(1.0, confidence))
    
    # Determine needs_review based on confidence threshold
    needs_review = confidence < Config.CONFIDENCE_THRESHOLD
    
    return DetectedElement(
        level=level,
        code=elem_data['code'],
        title=elem_data['title'],
        description=elem_data['description'],
        confidence=confidence,
        source_page=elem_data.get('source_page', default_page),
        source_text=elem_data['source_text'],
        needs_review=needs_review
    )


def parse_llm_response(response_text: str, blocks: List[TextBlock]) -> List[DetectedElement]:
    """
    Parse LLM response into DetectedElement objects.
    
    This function handles various edge cases including:
    - Extra text around the JSON array
    - Missing or invalid fields
    - Invalid hierarchy levels
    - Out-of-range confidence values
    
    Args:
        response_text: Raw response text from LLM
        blocks: Original text blocks (for fallback page numbers)
        
    Returns:
        List of DetectedElement objects (may be empty if parsing fails)
        
    Raises:
        json.JSONDecodeError: If response is not valid JSON
        ValueError: If response structure is invalid
    """
    logger.debug("Parsing LLM response")
    
    # Extract JSON from response
    json_text = _extract_json_from_response(response_text)
    elements_data = json.loads(json_text)
    
    if not isinstance(elements_data, list):
        logger.error(f"Response is not a JSON array, got type: {type(elements_data)}")
        raise ValueError("Response must be a JSON array")
    
    logger.info(f"Parsed {len(elements_data)} elements from LLM response")
    
    detected_elements = []
    default_page = blocks[0].page_number if blocks else 1
    
    for idx, elem_data in enumerate(elements_data):
        # Validate required fields
        validation_error = _validate_element_data(elem_data)
        if validation_error:
            logger.warning(f"Element {idx}: {validation_error}, skipping element")
            continue
        
        # Create detected element
        element = _create_detected_element(elem_data, default_page)
        if element:
            detected_elements.append(element)
            logger.debug(
                f"Element {idx}: {element.level.value} - {element.code} - "
                f"{element.title[:50]} (confidence: {element.confidence:.2f})"
            )
        else:
            logger.warning(f"Element {idx}: Failed to create DetectedElement")
    
    logger.info(f"Successfully created {len(detected_elements)} DetectedElement objects")
    
    return detected_elements


def _build_bedrock_request(prompt: str) -> Dict[str, Any]:
    """
    Build request body for Bedrock Claude API.
    
    Args:
        prompt: The prompt to send to the LLM
        
    Returns:
        Request body dictionary
    """
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": LLM_MAX_TOKENS,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": LLM_TEMPERATURE  # Low temperature for consistent structured output
    }


def _extract_text_from_bedrock_response(response_body: Dict[str, Any]) -> str:
    """
    Extract text content from Bedrock Claude response.
    
    Args:
        response_body: Parsed response body from Bedrock
        
    Returns:
        Extracted text content
        
    Raises:
        ValueError: If response format is unexpected
    """
    if 'content' not in response_body or len(response_body['content']) == 0:
        raise ValueError("Unexpected response format from Bedrock: missing content")
    
    return response_body['content'][0]['text']


def call_bedrock_llm(prompt: str, max_retries: int = MAX_BEDROCK_RETRIES) -> str:
    """
    Call Amazon Bedrock LLM (Claude Sonnet 4.5) with the given prompt.
    
    Implements retry logic for transient failures like throttling.
    Uses Claude Sonnet 4.5 for optimal performance on structured extraction tasks.
    
    Args:
        prompt: The prompt to send to the LLM
        max_retries: Maximum number of retry attempts (default: 2)
        
    Returns:
        LLM response text
        
    Raises:
        ClientError: If Bedrock API call fails after all retries
        ValueError: If response format is unexpected
    """
    bedrock = boto3.client('bedrock-runtime', region_name=Config.AWS_REGION)
    request_body = _build_bedrock_request(prompt)
    
    logger.info(f"Calling Bedrock with model: {Config.BEDROCK_LLM_MODEL_ID}")
    logger.debug(f"Prompt length: {len(prompt)} characters, ~{estimate_tokens(prompt)} tokens")
    
    for attempt in range(max_retries + 1):
        try:
            response = bedrock.invoke_model(
                modelId=Config.BEDROCK_LLM_MODEL_ID,
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response['body'].read())
            response_text = _extract_text_from_bedrock_response(response_body)
            
            logger.info(f"Bedrock response received: {len(response_text)} characters")
            logger.debug(f"Response preview: {response_text[:500]}...")
            
            return response_text
                
        except ClientError as e:
            if attempt < max_retries:
                logger.warning(
                    f"Bedrock API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                )
                continue
            else:
                logger.error(
                    f"Bedrock API call failed after {max_retries + 1} attempts: {e}"
                )
                raise
        except ValueError as e:
            logger.error(f"Invalid Bedrock response format: {e}")
            raise
    
    raise RuntimeError("Failed to get response from Bedrock after all retries")


def _process_chunk(
    chunk: List[TextBlock], 
    chunk_idx: int, 
    total_chunks: int
) -> List[DetectedElement]:
    """
    Process a single chunk of text blocks through the LLM.
    
    Implements retry logic for JSON parsing failures.
    
    Args:
        chunk: Text blocks to process
        chunk_idx: Index of this chunk (for logging)
        total_chunks: Total number of chunks (for logging)
        
    Returns:
        List of detected elements from this chunk
    """
    logger.info(
        f"Processing chunk {chunk_idx + 1}/{total_chunks} "
        f"({len(chunk)} blocks, ~{sum(estimate_tokens(b.text) for b in chunk)} tokens)"
    )
    
    # Build prompt for this chunk
    prompt = build_detection_prompt(chunk)
    
    # Try to parse LLM response with retries
    for parse_attempt in range(MAX_PARSE_RETRIES + 1):
        try:
            # Call Bedrock
            response_text = call_bedrock_llm(prompt)
            
            # Parse response
            elements = parse_llm_response(response_text, chunk)
            
            logger.info(
                f"Chunk {chunk_idx + 1}/{total_chunks}: Successfully detected "
                f"{len(elements)} elements"
            )
            
            return elements
            
        except (json.JSONDecodeError, ValueError) as e:
            if parse_attempt < MAX_PARSE_RETRIES:
                logger.warning(
                    f"Chunk {chunk_idx + 1}/{total_chunks}: Failed to parse LLM response "
                    f"(attempt {parse_attempt + 1}/{MAX_PARSE_RETRIES + 1}): {e}"
                )
                # Retry with the same prompt
                continue
            else:
                logger.error(
                    f"Chunk {chunk_idx + 1}/{total_chunks}: Failed to parse LLM response "
                    f"after {MAX_PARSE_RETRIES + 1} attempts: {e}"
                )
                # Return empty list rather than failing entire detection
                return []
    
    return []


def detect_structure(blocks: List[TextBlock], document_s3_key: str = "") -> DetectionResult:
    """
    Detect hierarchical structure in extracted text blocks using Claude Sonnet 4.5.
    
    This function:
    1. Chunks text blocks into manageable sizes with overlap
    2. Sends each chunk to Claude Sonnet 4.5 for structure detection
    3. Parses and validates the LLM responses
    4. Flags low-confidence elements for review
    5. Aggregates results across all chunks
    
    The function is resilient to:
    - Malformed LLM responses (with retry)
    - Missing or invalid fields
    - Bedrock API failures (with retry)
    
    Args:
        blocks: List of text blocks from text extraction
        document_s3_key: S3 key of the source document (for tracking)
        
    Returns:
        DetectionResult with detected elements, review count, and status
    """
    logger.info(f"Starting structure detection for document: {document_s3_key}")
    logger.info(f"Input: {len(blocks)} text blocks")
    
    if not blocks:
        logger.error("No text blocks provided")
        return DetectionResult(
            document_s3_key=document_s3_key,
            elements=[],
            review_count=0,
            status="error",
            error="No text blocks provided"
        )
    
    try:
        # Chunk the text blocks
        chunks = chunk_text_blocks(blocks)
        logger.info(
            f"Created {len(chunks)} chunks from {len(blocks)} text blocks "
            f"(target: {DEFAULT_TARGET_TOKENS} tokens, overlap: {DEFAULT_OVERLAP_TOKENS} tokens)"
        )
        
        all_elements = []
        
        # Process each chunk
        for chunk_idx, chunk in enumerate(chunks):
            chunk_elements = _process_chunk(chunk, chunk_idx, len(chunks))
            all_elements.extend(chunk_elements)
            
            logger.info(
                f"Progress: {chunk_idx + 1}/{len(chunks)} chunks processed, "
                f"{len(all_elements)} total elements detected so far"
            )
        
        # Count elements needing review
        review_count = sum(1 for elem in all_elements if elem.needs_review)
        
        # Log summary by level
        level_counts = {}
        for elem in all_elements:
            level_counts[elem.level.value] = level_counts.get(elem.level.value, 0) + 1
        
        logger.info(
            f"Detection complete: {len(all_elements)} total elements detected"
        )
        logger.info(f"Elements by level: {level_counts}")
        logger.info(
            f"Review needed: {review_count} elements "
            f"(confidence < {Config.CONFIDENCE_THRESHOLD})"
        )
        
        return DetectionResult(
            document_s3_key=document_s3_key,
            elements=all_elements,
            review_count=review_count,
            status="success",
            error=None
        )
        
    except Exception as e:
        logger.error(f"Structure detection failed: {e}", exc_info=True)
        return DetectionResult(
            document_s3_key=document_s3_key,
            elements=[],
            review_count=0,
            status="error",
            error=str(e)
        )
